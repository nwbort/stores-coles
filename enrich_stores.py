#!/usr/bin/env python3
"""
Enrich stores.json with address, coordinates, phone, and trading hours
fetched from individual store pages.

Usage:
  python3 enrich_stores.py [--force] [--workers N] [--limit N]

Options:
  --force       Re-enrich all stores, not just new ones
  --workers N   Concurrent requests (default: 5)
  --limit N     Only process first N stores (for testing)
"""

import sys
import json
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from extract_store import extract

STORES_FILE = 'stores.json'
SAVE_INTERVAL = 50


def load_stores():
    with open(STORES_FILE) as f:
        return json.load(f)


def save_stores(stores):
    with open(STORES_FILE, 'w') as f:
        json.dump(stores, f, indent=2)
    print(f"  -> saved {STORES_FILE}", flush=True)


def fetch_one(store):
    try:
        info = extract(store['url'])
        return store['id'], info, None
    except Exception as e:
        return store['id'], None, str(e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='Re-enrich all stores')
    parser.add_argument('--workers', type=int, default=5, help='Concurrent requests')
    parser.add_argument('--limit', type=int, default=None, help='Max stores to process')
    args = parser.parse_args()

    stores = load_stores()
    store_by_id = {s['id']: s for s in stores}

    if args.force:
        to_enrich = list(stores)
    else:
        to_enrich = [s for s in stores if 'lat' not in s]

    if args.limit is not None:
        to_enrich = to_enrich[:args.limit]

    total = len(to_enrich)
    mode = 'full re-enrich' if args.force else 'new stores only'
    print(f"{len(stores)} total stores, {total} to enrich ({mode}, {args.workers} workers)")

    if total == 0:
        print("Nothing to do.")
        return

    ok = 0
    failed = 0
    done = 0
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(fetch_one, store): store for store in to_enrich}

        for future in as_completed(futures):
            store_id, info, error = future.result()
            store = store_by_id[store_id]

            with lock:
                done += 1
                if info:
                    store.update({k: v for k, v in info.items() if k != 'source'})
                    print(f"[{done}/{total}] {store['state']} {store['name']} ok", flush=True)
                    ok += 1
                else:
                    msg = error or 'no data'
                    print(f"[{done}/{total}] {store['state']} {store['name']} FAIL: {msg}", flush=True)
                    failed += 1

                if done % SAVE_INTERVAL == 0:
                    save_stores(stores)

    save_stores(stores)
    print(f"\nDone: {ok} enriched, {failed} failed out of {total}")


if __name__ == '__main__':
    main()
