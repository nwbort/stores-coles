#!/usr/bin/env bash
#
# convert - Parse Coles store sitemap XML into structured JSON
# Usage: ./convert.sh <xml-file> [output-json-file]

set -e

XML_FILE="${1}"
OUTPUT_FILE="${2:-stores.json}"

if [ -z "$XML_FILE" ] || [ ! -f "$XML_FILE" ]; then
  echo "Usage: $0 <xml-file> [output-json-file]"
  exit 1
fi

# Extract <loc> values and build JSON array
python3 - "$XML_FILE" "$OUTPUT_FILE" <<'EOF'
import sys
import json
import xml.etree.ElementTree as ET
import re

xml_file = sys.argv[1]
output_file = sys.argv[2]

tree = ET.parse(xml_file)
root = tree.getroot()

# Handle XML namespace
ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

# Preserve enrichment from the existing output file if present
existing_enrichment = {}
try:
    with open(output_file) as fh:
        for s in json.load(fh):
            if 'lat' in s:
                existing_enrichment[s['id']] = {
                    k: v for k, v in s.items()
                    if k not in ('id', 'name', 'state', 'url')
                }
except (FileNotFoundError, json.JSONDecodeError):
    pass

stores = []
for url_el in root.findall('sm:url', ns):
    loc = url_el.find('sm:loc', ns)
    if loc is None:
        continue
    href = loc.text.strip()

    # URL pattern: /find-stores/coles/{state}/{name}-{id}
    m = re.search(r'/find-stores/coles/([^/]+)/(.+)-(\d+)$', href)
    if not m:
        continue

    state = m.group(1).upper()
    # name may contain hyphens; everything before the trailing -<digits>
    name = m.group(2).replace('-', ' ').title()
    store_id = int(m.group(3))

    store = {"id": store_id, "name": name, "state": state, "url": href}
    if store_id in existing_enrichment:
        store.update(existing_enrichment[store_id])
    stores.append(store)

stores.sort(key=lambda s: (s['state'], s['name']))

with open(output_file, 'w') as f:
    json.dump(stores, f, indent=2)

need_enrich = sum(1 for s in stores if 'lat' not in s)
print(f"Wrote {len(stores)} stores to {output_file} ({need_enrich} need enrichment)")
EOF
