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

# After fetching, cut the Measure J site shapes out of these zones so the zoning
# polygons route around the overlay sites (which are drawn on top in the map).
# Requires shapely; if it or the site files are missing, this step is skipped.
CUT_SITES_FROM_ZONES = ["I"]
MEASURE_J_PARCELS_FILE = "measure_j.geojson"
MEASURE_J_OVERLAYS_FILE = "measure_j_overlays.geojson"
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


def load_measure_j_shapes():
    """Union of the Measure J shapes as drawn on the map: full parcels, but with
    any APN present in the overlays file replaced by its approximate sub-area.
    Returns a shapely geometry, or None if the files / shapely are unavailable."""
    try:
        from shapely.geometry import shape
        from shapely.ops import unary_union
    except ImportError:
        print("  shapely not installed; skipping Measure J cutout")
        return None

    try:
        parcels = json.load(open(MEASURE_J_PARCELS_FILE))
        overlays = json.load(open(MEASURE_J_OVERLAYS_FILE))
    except FileNotFoundError as e:
        print(f"  {e.filename} not found; skipping Measure J cutout")
        return None

    overridden = {f["properties"].get("Parcel") for f in overlays["features"]}
    geoms = [shape(f["geometry"]) for f in parcels["features"]
             if f["properties"].get("Parcel") not in overridden]
    geoms += [shape(f["geometry"]) for f in overlays["features"]]
    return unary_union(geoms)


def cut_sites_from_zones(features):
    """Subtract the Measure J shapes from every feature whose zone is in
    CUT_SITES_FROM_ZONES, so those zoning polygons go around the sites."""
    from shapely.geometry import shape, mapping

    sites = load_measure_j_shapes()
    if sites is None or sites.is_empty:
        return features

    out = []
    for f in features:
        if f["properties"].get(ZONE_FIELD) in CUT_SITES_FROM_ZONES:
            geom = shape(f["geometry"]).difference(sites)
            if geom.is_empty:
                continue
            f = {**f, "geometry": mapping(geom)}
        out.append(f)
    print(f"  cut Measure J sites out of {CUT_SITES_FROM_ZONES} zones")
    return out


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

    if CUT_SITES_FROM_ZONES:
        all_features = cut_sites_from_zones(all_features)

    geojson = {
        "type": "FeatureCollection",
        "features": all_features,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(geojson, f)

    print(f"\nWrote {len(all_features)} features to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()