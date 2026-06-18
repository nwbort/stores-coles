#!/usr/bin/env python3
"""
Extract address, opening hours, and coordinates from a Coles store page.
Usage: python3 extract_store.py <url>

Primary source: __NEXT_DATA__ (richer, human-readable trading hours)
Fallback:       JSON-LD structured data
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


def find_json_ld(html_content):
    results = []
    for raw in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_content, re.DOTALL | re.IGNORECASE
    ):
        try:
            results.append(json.loads(raw.strip()))
        except json.JSONDecodeError:
            pass
    return results


def extract_from_next_data(data):
    page_props = data.get('props', {}).get('pageProps', {})
    store = page_props.get('store')
    if not store:
        return None

    result = {}

    if 'latitude' in store and 'longitude' in store:
        result['lat'] = store['latitude']
        result['lng'] = store['longitude']

    if 'address' in store:
        result['address'] = store['address']
    if 'suburb' in store:
        result['suburb'] = store['suburb']
    if 'state' in store:
        result['state'] = store['state']
    if 'postcode' in store:
        result['postcode'] = store['postcode']
    if 'phone' in store:
        result['phone'] = store['phone']

    if 'tradingHours' in store and store['tradingHours']:
        result['trading_hours'] = store['tradingHours']

    if 'services' in store and store['services']:
        result['services'] = store['services']

    return result if result else None


def extract_from_json_ld(items):
    store_types = {'GroceryStore', 'Store', 'LocalBusiness', 'FoodEstablishment', 'Supermarket'}
    for item in items:
        for obj in (item if isinstance(item, list) else [item]):
            if obj.get('@type') not in store_types:
                continue
            result = {}
            addr = obj.get('address', {})
            if isinstance(addr, dict):
                result['address'] = addr.get('streetAddress', '')
                result['suburb'] = addr.get('addressLocality', '')
                result['state'] = addr.get('addressRegion', '')
                result['postcode'] = addr.get('postalCode', '')
            geo = obj.get('geo', {})
            if geo:
                result['lat'] = geo.get('latitude')
                result['lng'] = geo.get('longitude')
            hours = obj.get('openingHoursSpecification') or obj.get('openingHours')
            if hours:
                result['trading_hours'] = hours
            if 'telephone' in obj:
                result['phone'] = obj['telephone']
            return result
    return None


def extract(url, verbose=False):
    html_content = fetch_page(url)
    if verbose:
        print(f"Page size: {len(html_content):,} bytes", file=sys.stderr)

    # Try __NEXT_DATA__ first (richer data)
    next_data = find_next_data(html_content)
    if next_data:
        result = extract_from_next_data(next_data)
        if result:
            result['source'] = 'next-data'
            return result

    # Fall back to JSON-LD
    json_ld = find_json_ld(html_content)
    if json_ld:
        result = extract_from_json_ld(json_ld)
        if result:
            result['source'] = 'json-ld'
            return result

    # Log diagnostic so we can identify bot-block pages
    print(f"  [extract fail] url={url} size={len(html_content)} "
          f"snippet={html_content[:200]!r}", file=sys.stderr)
    return None


if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else 'https://www.coles.com.au/find-stores/coles/act/amaroo-5784'
    info = extract(url, verbose=True)
    print(json.dumps(info, indent=2))
