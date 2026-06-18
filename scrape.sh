#!/bin/bash
./download.sh 'https://www.coles.com.au/sitemap/sitemap-stores.xml'
./convert.sh coles.com.au-sitemap-sitemap-stores.xml.xml stores.json

# Weekly on Sundays (or when ENRICH_FORCE=1), re-enrich all stores.
# Every other day, only enrich new stores.
ENRICH_FLAGS=""
if [ "${ENRICH_FORCE}" = "1" ] || [ "$(date +%u)" = "7" ]; then
  echo "Full enrichment run"
  ENRICH_FLAGS="$ENRICH_FLAGS --force"
else
  echo "Incremental enrichment run (new stores only)"
fi

python3 enrich_stores.py $ENRICH_FLAGS
