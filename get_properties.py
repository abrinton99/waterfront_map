"""
Export the parcel polygons listed in measure_J_sites.txt (by APN) from the
Marin County parcels layer to a GeoJSON file.

Source layer: https://share-open-data-marincounty.hub.arcgis.com/datasets/marincounty::parcels

The APN field on this layer ("Parcel") stores 8 digits with no dashes, e.g.
"06316204", while measure_J_sites.txt lists them dashed ("063-162-04"), so we
strip the dashes before querying.

Run:
    python get_properties.py

Output:
    measure_j.geojson  (in the current directory)
"""

import json
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
SERVICE_URL = "https://services6.arcgis.com/T8eS7sop5hLmgRRH/arcgis/rest/services/Parcels/FeatureServer/0"
APN_FIELD = "Parcel"           # 8-digit APN, no dashes
SITES_FILE = "measure_J_sites.txt"
OUTPUT_FILE = "measure_j.geojson"
INSPECT_FIELDS = False         # set True to list fields, then exit
PAGE_SIZE = 2000               # this layer's maxRecordCount is 2000
# ---------------------------------------------------------------------------


def fetch_json(url):
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def get_layer_metadata(service_url):
    return fetch_json(f"{service_url}?f=json")


def read_apns(path):
    """Read APNs from `path`, stripping dashes/whitespace and skipping blanks."""
    apns = []
    with open(path) as f:
        for line in f:
            apn = line.strip().replace("-", "")
            if apn:
                apns.append(apn)
    return apns


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
        return

    apns = read_apns(SITES_FILE)
    print(f"Read {len(apns)} APNs from {SITES_FILE}")

    where = build_where_clause(APN_FIELD, apns)
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

    # Report any APNs that didn't come back, so missing parcels are visible.
    found = {feat["properties"].get(APN_FIELD) for feat in all_features}
    missing = [a for a in apns if a not in found]
    print(f"\nWrote {len(all_features)} features to {OUTPUT_FILE}")
    if missing:
        print(f"WARNING: no parcel found for {len(missing)} APN(s): {', '.join(missing)}")


if __name__ == "__main__":
    main()
