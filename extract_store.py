#!/usr/bin/env python3
"""
Extract address, opening hours, and coordinates from a Coles store page.
Usage: python3 extract_store.py <url>

Tries, in order:
  1. JSON-LD structured data (application/ld+json)
  2. Next.js __NEXT_DATA__ embedded JSON
"""

import sys
import json
import re
import urllib.request
import urllib.error

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-AU,en;q=0.9',
    'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}


def fetch_page(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode('utf-8', errors='replace')


def find_json_ld(html_content):
    pattern = r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    results = []
    for raw in re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE):
        try:
            results.append(json.loads(raw.strip()))
        except json.JSONDecodeError:
            pass
    return results


def find_next_data(html_content):
    m = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html_content, re.DOTALL | re.IGNORECASE
    )
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    return None


def parse_address(addr):
    if isinstance(addr, str):
        return addr
    if isinstance(addr, dict):
        return {
            'street': addr.get('streetAddress', ''),
            'suburb': addr.get('addressLocality', ''),
            'state': addr.get('addressRegion', ''),
            'postcode': addr.get('postalCode', ''),
            'country': addr.get('addressCountry', ''),
        }
    return addr


def extract_from_json_ld(items):
    store_types = {'GroceryStore', 'Store', 'LocalBusiness', 'FoodEstablishment', 'Supermarket'}
    for item in items:
        objs = item if isinstance(item, list) else [item]
        for obj in objs:
            if obj.get('@type') in store_types:
                return obj
    return None


def extract_from_next_data(data):
    """Walk __NEXT_DATA__ looking for store-shaped objects."""
    page_props = data.get('props', {}).get('pageProps', {})

    # Common key names Coles might use
    for key in ('store', 'storeDetails', 'storeInfo', 'storeData', 'findStoresResult'):
        if key in page_props:
            return page_props[key]

    # Broader search: look for an object with address + geo fields anywhere in pageProps
    def find_store_obj(obj, depth=0):
        if depth > 6:
            return None
        if isinstance(obj, dict):
            has_address = any(k in obj for k in ('address', 'streetAddress', 'addressLine1'))
            has_geo = any(k in obj for k in ('geo', 'latitude', 'lat', 'coordinates'))
            if has_address and has_geo:
                return obj
            for v in obj.values():
                found = find_store_obj(v, depth + 1)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = find_store_obj(item, depth + 1)
                if found:
                    return found
        return None

    return find_store_obj(page_props)


def summarise(result):
    """Print a clean summary of what was extracted."""
    print("=== EXTRACTION RESULT ===")
    print(json.dumps(result, indent=2, default=str))


def main(url):
    print(f"Fetching: {url}", file=sys.stderr)
    html_content = fetch_page(url)
    print(f"Page size: {len(html_content):,} bytes", file=sys.stderr)

    result = {'url': url, 'source': None}

    # --- Try JSON-LD ---
    json_ld_items = find_json_ld(html_content)
    print(f"JSON-LD blocks found: {len(json_ld_items)}", file=sys.stderr)
    store_obj = extract_from_json_ld(json_ld_items)

    if store_obj:
        result['source'] = 'json-ld'
        result['name'] = store_obj.get('name')
        if 'address' in store_obj:
            result['address'] = parse_address(store_obj['address'])
        if 'geo' in store_obj:
            geo = store_obj['geo']
            result['coordinates'] = {
                'lat': geo.get('latitude'),
                'lng': geo.get('longitude'),
            }
        if 'openingHoursSpecification' in store_obj:
            result['opening_hours'] = store_obj['openingHoursSpecification']
        elif 'openingHours' in store_obj:
            result['opening_hours'] = store_obj['openingHours']
        if 'telephone' in store_obj:
            result['phone'] = store_obj['telephone']

    # --- Try __NEXT_DATA__ ---
    next_data = find_next_data(html_content)
    if next_data:
        print("__NEXT_DATA__ found", file=sys.stderr)
        page_props = next_data.get('props', {}).get('pageProps', {})
        result['_next_data_page_props_keys'] = list(page_props.keys())

        store_from_next = extract_from_next_data(next_data)
        if store_from_next:
            result['_next_data_store_raw'] = store_from_next
            if result['source'] is None:
                result['source'] = 'next-data'
    else:
        print("No __NEXT_DATA__ found", file=sys.stderr)
        # Save a snippet of the HTML to help diagnose
        result['_html_snippet'] = html_content[:3000]

    summarise(result)
    return result


if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else 'https://www.coles.com.au/find-stores/coles/act/amaroo-5784'
    main(url)
