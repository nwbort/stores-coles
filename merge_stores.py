#!/usr/bin/env python3
"""
Merge enriched store slices into one output file.

The first input is the base: the full store list, carrying whatever enrichment
previous runs produced. Every later input is a patch — the slice a single
enrichment chunk processed. A patch entry replaces the base entry when it is
enriched (has 'lat'), so a forced re-enrich overwrites stale values; a chunk
that was bot-blocked leaves the base entry alone. Stores absent from every
patch keep their base version.

Usage: python3 merge_stores.py <output_file> <base> [<patch> ...]
"""

import json
import sys


def merge(output_file, input_files):
    if not input_files:
        print('No input files provided.')
        sys.exit(1)

    with open(input_files[0]) as f:
        base = json.load(f)

    patches = []
    for path in input_files[1:]:
        with open(path) as f:
            patches.append(json.load(f))

    by_id = [{s['id']: s for s in patch} for patch in patches]

    merged = []
    for store in base:
        sid = store['id']
        winner = next((lookup[sid] for lookup in by_id if 'lat' in lookup.get(sid, {})), None)
        merged.append(winner if winner is not None else store)

    with open(output_file, 'w') as f:
        json.dump(merged, f, indent=2)

    patched = sum(1 for lookup in by_id for sid in lookup if 'lat' in lookup[sid])
    merged_enriched = sum(1 for s in merged if 'lat' in s)
    print(f'base: {sum(1 for s in base if "lat" in s)}/{len(base)} enriched, '
          f'{len(patches)} patches contributing {patched} stores '
          f'-> merged: {merged_enriched}/{len(merged)} enriched')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f'Usage: {sys.argv[0]} <output_file> <base> [<patch> ...]')
        sys.exit(1)
    merge(sys.argv[1], sys.argv[2:])
