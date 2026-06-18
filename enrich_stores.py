#!/usr/bin/env python3
"""
Enrich stores.json with address, coordinates, phone, and trading hours
fetched from individual store pages.

Usage:
  python3 enrich_stores.py [--limit N] [--delay SECONDS]

Options:
  --limit N       Only process first N stores (for testing)
  --delay SECONDS Sleep between requests (default: 0.5)
"""

import sys
import json
import time
import argparse
from extract_store import extract

STORES_FILE = 'stores.json'


def load_stores():
    with open(STORES_FILE) as f:
        return json.load(f)


def save_stores(stores):
    with open(STORES_FILE, 'w') as f:
        json.dump(stores, f, indent=2)
    print(f"Saved {len(stores)} stores to {STORES_FILE}")


def needs_enrichment(store):
    return 'lat' not in store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None, help='Max stores to process')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay between requests (s)')
    args = parser.parse_args()

    stores = load_stores()
    to_enrich = [s for s in stores if needs_enrichment(s)]

    if args.limit is not None:
        to_enrich = to_enrich[:args.limit]

    total = len(to_enrich)
    print(f"{len(stores)} total stores, {total} need enrichment")

    ok = 0
    failed = 0

    for i, store in enumerate(to_enrich, 1):
        url = store['url']
        print(f"[{i}/{total}] {store['state']} {store['name']} ...", end=' ', flush=True)

        try:
            info = extract(url)
            if info:
                store.update({k: v for k, v in info.items() if k != 'source'})
                print(f"ok ({info.get('source', '?')})")
                ok += 1
            else:
                print("no data found")
                failed += 1
        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1

        # Save every 50 stores so progress isn't lost if the job is interrupted
        if i % 50 == 0:
            save_stores(stores)

        if i < total and args.delay > 0:
            time.sleep(args.delay)

    save_stores(stores)
    print(f"\nDone: {ok} enriched, {failed} failed")


if __name__ == '__main__':
    main()
