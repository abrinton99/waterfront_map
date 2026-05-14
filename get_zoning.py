"""
Export W and I zoning features from the City of Sausalito zoning layer
to a GeoJSON file.

Source layer: https://www.arcgis.com/home/item.html?id=4eebe0887029428f8cc8da77910f77c6

Run:
    python export_zoning.py

Output:
    zoning_W_I.geojson  (in the current directory)
"""

import json
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
SERVICE_URL = "https://services6.arcgis.com/T8eS7sop5hLmgRRH/arcgis/rest/services/Zoning_of_Sausalito/FeatureServer/123"
ZONE_FIELD = "Zoning"          # confirmed field name for this layer
ZONE_VALUES = ["W", "I"]       # zoning codes to keep
OUTPUT_FILE = "zoning_W_I.geojson"
INSPECT_FIELDS = False         # set True to list fields and unique zone values, then exit
PAGE_SIZE = 2000               # this layer's maxRecordCount is 5000, so 2000 is safe
# ---------------------------------------------------------------------------


def fetch_json(url):
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def get_layer_metadata(service_url):
    return fetch_json(f"{service_url}?f=json")


def get_unique_values(service_url, field):
    """Return the distinct values present in `field`."""
    params = {
        "where": "1=1",
        "outFields": field,
        "returnGeometry": "false",
        "returnDistinctValues": "true",
        "f": "json",
    }
    url = f"{service_url}/query?{urllib.parse.urlencode(params)}"
    data = fetch_json(url)
    return sorted({f["attributes"][field] for f in data.get("features", [])})


def query_page(service_url, where, offset, page_size):
    params = {
        "where": where,
        "outFields": "*",
        "outSR": 4326,            # WGS84 lat/lon
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": page_size,
    }
    url = f"{service_url}/query?{urllib.parse.urlencode(params)}"
    return fetch_json(url)


def build_where_clause(field, values):
    quoted = ",".join(f"'{v}'" for v in values)
    return f"{field} IN ({quoted})"


def main():
    if INSPECT_FIELDS:
        meta = get_layer_metadata(SERVICE_URL)
        print(f"Layer name:     {meta.get('name')}")
        print(f"Geometry type:  {meta.get('geometryType')}")
        print(f"Max records:    {meta.get('maxRecordCount')}")
        print("\nFields:")
        for f in meta.get("fields", []):
            print(f"  {f['name']:30s} ({f['type']})  alias: {f.get('alias')}")
        print(f"\nUnique values in '{ZONE_FIELD}':")
        for v in get_unique_values(SERVICE_URL, ZONE_FIELD):
            print(f"  {v!r}")
        return

    where = build_where_clause(ZONE_FIELD, ZONE_VALUES)
    print(f"Querying: {where}")

    all_features = []
    offset = 0
    while True:
        page = query_page(SERVICE_URL, where, offset, PAGE_SIZE)
        features = page.get("features", [])
        if not features:
            break
        all_features.extend(features)
        print(f"  fetched {len(features)} features (total: {len(all_features)})")

        if not page.get("exceededTransferLimit") and len(features) < PAGE_SIZE:
            break
        offset += len(features)

    geojson = {
        "type": "FeatureCollection",
        "features": all_features,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(geojson, f)

    print(f"\nWrote {len(all_features)} features to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()