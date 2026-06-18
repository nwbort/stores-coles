#!/usr/bin/env python3
"""
Enrich stores.json with address, coordinates, phone, and trading hours
fetched from individual store pages.

Usage:
  python3 enrich_stores.py [--force] [--workers N] [--delay SECONDS] [--limit N]

Options:
  --force         Re-enrich all stores, not just new ones
  --workers N     Concurrent workers (default: 3)
  --delay SECONDS Minimum seconds between requests globally (default: 0.5)
  --limit N       Only process first N stores (for testing)
"""

import json
import time
import random
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from extract_store import extract, BotBlockedError

STORES_FILE = 'stores.json'
SAVE_INTERVAL = 50


class RateLimiter:
    """Ensures a minimum gap between request dispatches across all threads."""
    def __init__(self, min_interval):
        self._lock = threading.Lock()
        self._last = 0.0
        self._interval = min_interval

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()


def load_stores():
    with open(STORES_FILE) as f:
        return json.load(f)


def save_stores(stores):
    with open(STORES_FILE, 'w') as f:
        json.dump(stores, f, indent=2)
    print(f'  -> saved {STORES_FILE}', flush=True)


BOTBLOCK_WAIT = 60  # seconds to pause after a bot-block before retrying


def fetch_one(store, rate_limiter, retries=2):
    for attempt in range(retries + 1):
        rate_limiter.acquire()
        try:
            info = extract(store['url'])
            return store['id'], info, None
        except BotBlockedError:
            if attempt < retries:
                wait = BOTBLOCK_WAIT * (attempt + 1) + random.uniform(0, 30)
                print(f"  [bot-block] {store['name']} – retry {attempt + 1}/{retries} in {wait:.0f}s",
                      flush=True)
                time.sleep(wait)
            else:
                return store['id'], None, 'bot-blocked'
        except Exception as e:
            return store['id'], None, str(e)
    return store['id'], None, 'bot-blocked'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='Re-enrich all stores')
    parser.add_argument('--workers', type=int, default=1, help='Concurrent workers (default: 1)')
    parser.add_argument('--delay', type=float, default=2.0,
                        help='Min seconds between requests globally (default: 2.0)')
    parser.add_argument('--limit', type=int, default=None, help='Max stores to process')
    args = parser.parse_args()

    stores = load_stores()
    store_by_id = {s['id']: s for s in stores}

    to_enrich = list(stores) if args.force else [s for s in stores if 'lat' not in s]
    if args.limit is not None:
        to_enrich = to_enrich[:args.limit]

    total = len(to_enrich)
    mode = 'full re-enrich' if args.force else 'new stores only'
    print(f'{len(stores)} total stores, {total} to enrich '
          f'({mode}, {args.workers} workers, {args.delay}s delay)')

    if total == 0:
        print('Nothing to do.')
        return

    rate_limiter = RateLimiter(args.delay)
    ok = 0
    failed = 0
    done = 0
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_one, store, rate_limiter): store
            for store in to_enrich
        }

        for future in as_completed(futures):
            store_id, info, error = future.result()
            store = store_by_id[store_id]

            with lock:
                done += 1
                if info:
                    store.update({k: v for k, v in info.items() if k != 'source'})
                    print(f'[{done}/{total}] {store["state"]} {store["name"]} ok', flush=True)
                    ok += 1
                else:
                    msg = error or 'no data'
                    print(f'[{done}/{total}] {store["state"]} {store["name"]} FAIL: {msg}',
                          flush=True)
                    failed += 1

                if done % SAVE_INTERVAL == 0:
                    save_stores(stores)

    save_stores(stores)
    print(f'\nDone: {ok} enriched, {failed} failed out of {total}')


if __name__ == '__main__':
    main()
