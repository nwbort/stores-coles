#!/usr/bin/env python3
"""
Enrich stores.json with address, coordinates, phone, and trading hours
fetched from individual store pages.

Usage:
  python3 enrich_stores.py [--force] [--workers N] [--delay SECONDS] [--limit N]

Options:
  --force         Re-enrich all stores, not just new ones
  --workers N     Concurrent workers (default: 1)
  --delay SECONDS Minimum seconds between requests globally (default: 2.0)
  --limit N       Only process first N stores (for testing)

Bot-blocking behaviour:
  Coles uses Akamai bot protection that blocks an IP after ~4 requests per
  session. On first block the script saves progress and exits cleanly so that
  the next run (with a fresh GitHub Actions IP) can continue from where this
  one left off.
"""

import json
import time
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


def fetch_one(store, rate_limiter, stop_flag):
    if stop_flag.is_set():
        return store['id'], None, 'cancelled'
    rate_limiter.acquire()
    if stop_flag.is_set():
        return store['id'], None, 'cancelled'
    try:
        info = extract(store['url'])
        return store['id'], info, None
    except BotBlockedError:
        return store['id'], None, 'bot-blocked'
    except Exception as e:
        return store['id'], None, str(e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='Re-enrich all stores')
    parser.add_argument('--workers', type=int, default=1, help='Concurrent workers (default: 1)')
    parser.add_argument('--delay', type=float, default=2.0,
                        help='Min seconds between requests globally (default: 2.0)')
    parser.add_argument('--limit', type=int, default=None, help='Max stores to process')
    parser.add_argument('--chunk', default=None, metavar='INDEX/TOTAL',
                        help='Process a slice of stores, e.g. --chunk 2/5 for the third of five chunks')
    args = parser.parse_args()

    chunk_index, chunk_total = None, None
    if args.chunk:
        try:
            idx, total_chunks = args.chunk.split('/')
            chunk_index, chunk_total = int(idx), int(total_chunks)
            if not (0 <= chunk_index < chunk_total):
                raise ValueError
        except (ValueError, AttributeError):
            parser.error('--chunk must be INDEX/TOTAL with 0 <= INDEX < TOTAL')

    stores = load_stores()
    store_by_id = {s['id']: s for s in stores}

    to_enrich = list(stores) if args.force else [s for s in stores if 'lat' not in s]
    if chunk_total is not None:
        n = len(to_enrich)
        size = (n + chunk_total - 1) // chunk_total
        to_enrich = to_enrich[chunk_index * size:(chunk_index + 1) * size]
    if args.limit is not None:
        to_enrich = to_enrich[:args.limit]

    total = len(to_enrich)
    chunk_desc = f'chunk {chunk_index}/{chunk_total}' if chunk_total is not None else 'all'
    mode = 'full re-enrich' if args.force else 'new stores only'
    print(f'{len(stores)} total stores, {total} to enrich '
          f'({mode}, {chunk_desc}, {args.workers} workers, {args.delay}s delay)')

    if total == 0:
        print('Nothing to do.')
        return

    rate_limiter = RateLimiter(args.delay)
    stop_flag = threading.Event()
    ok = 0
    failed = 0
    done = 0
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_one, store, rate_limiter, stop_flag): store
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
                elif error == 'cancelled':
                    pass
                elif error == 'bot-blocked':
                    print(f'[{done}/{total}] {store["state"]} {store["name"]} FAIL: bot-blocked'
                          f' – saving progress and stopping (re-run to continue)', flush=True)
                    failed += 1
                    stop_flag.set()
                else:
                    msg = error or 'no data'
                    print(f'[{done}/{total}] {store["state"]} {store["name"]} FAIL: {msg}',
                          flush=True)
                    failed += 1

                if done % SAVE_INTERVAL == 0:
                    save_stores(stores)

    save_stores(stores)
    enriched_total = sum(1 for s in stores if 'lat' in s)
    print(f'\nDone: {ok} enriched this run, {failed} failed, {enriched_total}/{len(stores)} total enriched')


if __name__ == '__main__':
    main()
