#!/usr/bin/env python3
"""
Merge two enriched stores.json files into one.

For each store, prefer an enriched version (has 'lat') from either file.
If both files enriched the same store, top_file wins.

Usage: python3 merge_stores.py <top_file> <bottom_file> <output_file>
"""

import json
import sys


def merge(top_file, bottom_file, output_file):
    with open(top_file) as f:
        top_stores = json.load(f)
    with open(bottom_file) as f:
        bottom_stores = json.load(f)

    bottom_by_id = {s['id']: s for s in bottom_stores}

    merged = []
    for store in top_stores:
        bottom = bottom_by_id.get(store['id'], store)
        if 'lat' in store:
            merged.append(store)
        elif 'lat' in bottom:
            merged.append(bottom)
        else:
            merged.append(store)

    with open(output_file, 'w') as f:
        json.dump(merged, f, indent=2)

    top_enriched = sum(1 for s in top_stores if 'lat' in s)
    bottom_enriched = sum(1 for s in bottom_stores if 'lat' in s)
    merged_enriched = sum(1 for s in merged if 'lat' in s)
    print(f'Top: {top_enriched} enriched, Bottom: {bottom_enriched} enriched, '
          f'Merged: {merged_enriched}/{len(merged)} total enriched')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(f'Usage: {sys.argv[0]} <top_file> <bottom_file> <output_file>')
        sys.exit(1)
    merge(sys.argv[1], sys.argv[2], sys.argv[3])
