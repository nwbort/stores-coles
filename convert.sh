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

    stores.append({
        "id": store_id,
        "name": name,
        "state": state,
        "url": href,
    })

stores.sort(key=lambda s: (s['state'], s['name']))

with open(output_file, 'w') as f:
    json.dump(stores, f, indent=2)

print(f"Wrote {len(stores)} stores to {output_file}")
EOF
