#!/bin/bash
./download.sh 'https://www.coles.com.au/sitemap/sitemap-stores.xml'
./convert.sh coles.com.au-sitemap-sitemap-stores.xml.xml stores.json
