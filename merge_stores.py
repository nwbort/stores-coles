#!/usr/bin/env python3
"""
Merge N enriched stores.json files into one output file.

For each store, the first input file that has an enriched version (has 'lat')
wins. Stores not enriched in any input fall back to the version from the
first input file.

Usage: python3 merge_stores.py <output_file> <input1> [<input2> ...]
"""

import json
import sys


def merge(output_file, input_files):
    if not input_files:
        print('No input files provided.')
        sys.exit(1)

    chunks = []
    for path in input_files:
        with open(path) as f:
            chunks.append(json.load(f))

    base = chunks[0]
    by_id = [{s['id']: s for s in chunk} for chunk in chunks]

    merged = []
    for store in base:
        sid = store['id']
        winner = next((lookup[sid] for lookup in by_id if 'lat' in lookup.get(sid, {})), None)
        merged.append(winner if winner is not None else store)

    with open(output_file, 'w') as f:
        json.dump(merged, f, indent=2)

    per_chunk = [sum(1 for s in chunk if 'lat' in s) for chunk in chunks]
    merged_enriched = sum(1 for s in merged if 'lat' in s)
    chunk_summary = ', '.join(f'chunk {i}: {n}' for i, n in enumerate(per_chunk))
    print(f'{chunk_summary} -> merged: {merged_enriched}/{len(merged)} enriched')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f'Usage: {sys.argv[0]} <output_file> <input1> [<input2> ...]')
        sys.exit(1)
    merge(sys.argv[1], sys.argv[2:])
