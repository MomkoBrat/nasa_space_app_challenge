"""Write a shareable CSV with only the eligible Earth candidate locations.

Input:  data/earth_candidates.csv  (+ frontend/public/data/countries.geojson for country names)
Output: data/earth_eligible_locations.csv

Usage: python prep/export_eligible.py
"""

import csv
import json
from pathlib import Path

CANDIDATES = Path("data/earth_candidates.csv")
COUNTRIES = Path("frontend/public/data/countries.geojson")  # Natural Earth 1:110m, approximate
OUTPUT = Path("data/earth_eligible_locations.csv")
COLUMNS = ["id", "region", "country", "lat", "lon", "nonvegetated_fraction",
           "barren_fraction", "excluded_landcover_fraction", "dem_coverage_fraction"]


def inside_ring(lon, lat, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def load_countries():
    data = json.loads(COUNTRIES.read_text(encoding="utf-8"))
    out = []
    for feat in data["features"]:
        geom = feat["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        xs = [p[0] for poly in polys for p in poly[0]]
        ys = [p[1] for poly in polys for p in poly[0]]
        out.append((feat["properties"]["name"], polys, (min(xs), min(ys), max(xs), max(ys))))
    return out


def country_of(lat, lon, countries):
    for name, polys, (w, s, e, n) in countries:
        if not (w <= lon <= e and s <= lat <= n):
            continue
        for poly in polys:
            if inside_ring(lon, lat, poly[0]) and not any(inside_ring(lon, lat, h) for h in poly[1:]):
                return name
    return ""  # outside the coarse 1:110m outlines (e.g. very close to a coast)


def main():
    countries = load_countries()
    with open(CANDIDATES, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r["eligible"].strip() in ("1", "true", "True")]
    rows.sort(key=lambda r: (r["region"], r["id"]))

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                **{k: r[k] for k in COLUMNS if k != "country"},
                "country": country_of(float(r["lat"]), float(r["lon"]), countries),
            })
    unknown = sum(1 for r in csv.DictReader(open(OUTPUT, encoding="utf-8")) if not r["country"])
    print(f"Wrote {len(rows)} eligible locations -> {OUTPUT} ({unknown} without a country name)")


if __name__ == "__main__":
    main()
