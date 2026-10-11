"""Build the small local Natural Earth map asset and exact country registry."""
from pathlib import Path
import hashlib
import json
import re

import country_converter as coco
import requests

URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
TARGET = Path(__file__).resolve().parents[1] / "source/_static/data/world-country-map.json"


def svg_path(geometry):
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    return "".join("M" + "L".join(f"{(lon + 180) * 2.5:.2f},{(85 - lat) * 2.5:.2f}" for lon, lat, *_ in ring) + "Z"
                   for polygon in polygons for ring in polygon)



def border_mesh(features):
    """Draw shared boundaries once, joining segments through non-junction nodes."""
    edges = set()
    for feature in features:
        for ring in re.findall(r"M([^M]+?)Z", feature["path"]):
            points = [tuple(round(float(v), 2) for v in point.split(",")) for point in ring.split("L")]
            for left, right in zip(points, points[1:] + points[:1]):
                if left != right:
                    edges.add(tuple(sorted((left, right))))
    adjacent = {}
    for left, right in edges:
        adjacent.setdefault(left, set()).add(right)
        adjacent.setdefault(right, set()).add(left)
    unused = set(edges)

    def walk(start, following):
        points = [start]
        previous = start
        while True:
            unused.remove(tuple(sorted((previous, following))))
            points.append(following)
            if following == start or len(adjacent[following]) != 2:
                return points
            candidates = [point for point in adjacent[following]
                          if tuple(sorted((following, point))) in unused]
            if not candidates:
                return points
            previous, following = following, candidates[0]

    paths = []
    for point in sorted(adjacent):
        if len(adjacent[point]) != 2:
            for neighbor in sorted(adjacent[point]):
                if tuple(sorted((point, neighbor))) in unused:
                    paths.append(walk(point, neighbor))
    while unused:
        paths.append(walk(*min(unused)))

    def path(points):
        closed = points[-1] == points[0]
        coordinates = points[:-1] if closed else points
        return "M" + "L".join(f"{x:.2f},{y:.2f}" for x, y in coordinates) + ("Z" if closed else "")
    return "".join(path(points) for points in paths)


def main():
    response = requests.get(URL, timeout=60)
    response.raise_for_status()
    shapes = []
    for feature in response.json()["features"]:
        props = feature["properties"]
        code = props.get("ISO_A3_EH") or props["ADM0_A3"]
        if code == "-99":
            code = props["ADM0_A3"]
        if code != "ATA":
            # Natural Earth's KOS identifies Kosovo, stored as XKX in the registry.
            code = {"KOS": "XKX", "SOL": "SOM"}.get(code, code)
            shapes.append({"iso3": code, "name": "Somalia" if code == "SOM" else props["NAME_LONG"], "path": svg_path(feature["geometry"])})
    countries = []
    for row in coco.CountryConverter().data.to_dict("records"):
        country = {"iso3": row["ISO3"], "iso2": row["ISO2"], "name": row["name_short"], "official_name": row["name_official"]}
        # The packaged ISO2 entries for these countries are regex alternatives.
        if country["iso3"] in {"GRC", "GBR"}:
            country["iso2"] = "GR" if country["iso3"] == "GRC" else "GB"
            country["iso2_aliases"] = ["EL"] if country["iso3"] == "GRC" else ["UK"]
        countries.append(country)
    countries.sort(key=lambda row: row["name"])
    data = {"schema_version": 1, "viewbox": "0 0 900 365", "features": shapes, "borders": border_mesh(shapes), "countries": countries,
            "source": {"name": "Natural Earth · 1:110m", "url": "https://www.naturalearthdata.com/downloads/110m-cultural-vectors/110m-admin-0-countries/",
                       "download": URL, "sha256": hashlib.sha256(response.content).hexdigest(),
                       "boundary_processing": "Shared undirected segments are deduplicated and joined into a single border mesh.",
                       "geometry_code_aliases": {"KOS": "XKX", "SOL": "SOM"}},
            "registry_source": {"name": "country_converter packaged country registry", "version": coco.__version__,
                                "normalization": "Canonical GR and GB, with EL and UK recorded as exact alternatives."}}
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")
    print(f"Wrote {len(shapes)} map shapes and {len(countries)} country/territory identifiers.")


if __name__ == "__main__":
    main()
