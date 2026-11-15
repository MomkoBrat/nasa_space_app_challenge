"""Build frontend/public/data/earth_cells.json (DATA_CONTRACT §4 shape) from the Earth pipeline.

Inputs:  data/earth_candidates.csv (step 1, Earth Engine)  +  data/earth_terrain.csv (step 2)
Output:  frontend/public/data/earth_cells.json

Only cells that are eligible AND have status "ok" are written. Dataset-level provenance is stored
once at the top level (contract allows omitting per-row `sources` for production rows).

Usage: python prep/earth_to_json.py
"""

import csv
import json
import math
from pathlib import Path

CANDIDATES = Path("data/earth_candidates.csv")
TERRAIN = Path("data/earth_terrain.csv")
OUTPUT = Path("frontend/public/data/earth_cells.json")
FEATURES = ["median_slope_deg", "steep_fraction", "relief_m", "roughness_m"]
DECIMALS = {"median_slope_deg": 3, "steep_fraction": 4, "relief_m": 1, "roughness_m": 2}

SOURCES = [
    {"dataset": "Copernicus DEM GLO-30 (ESA / Airbus), AWS Open Data copernicus-dem-30m",
     "native_resolution_m": 30, "url": "https://registry.opendata.aws/copernicus-dem/",
     "used_for": "terrain features"},
    {"dataset": "MODIS MOD44B v061 Vegetation Continuous Fields (Percent_NonVegetated), mean 2022-2024",
     "native_resolution_m": 250, "url": "https://doi.org/10.5067/MODIS/MOD44B.061",
     "used_for": "eligibility: non-vegetated fraction"},
    {"dataset": "MODIS MCD12Q1 v061 Land Cover (LC_Type1, IGBP), mosaic of 2020-2025, newest on top",
     "native_resolution_m": 500, "url": "https://doi.org/10.5067/MODIS/MCD12Q1.061",
     "used_for": "eligibility: excluded land cover, barren fraction"},
]


def is_true(v):
    return str(v).strip() in ("1", "true", "True")


def main():
    with open(CANDIDATES, newline="", encoding="utf-8") as f:
        candidates = {r["id"]: r for r in csv.DictReader(f) if is_true(r["eligible"])}
    with open(TERRAIN, newline="", encoding="utf-8") as f:
        terrain = [r for r in csv.DictReader(f) if r["status"] == "ok"]

    cells, skipped = [], 0
    for t in terrain:
        c = candidates.get(t["id"])
        features = {k: float(t[k]) for k in FEATURES}
        if c is None or not all(math.isfinite(v) for v in features.values()):
            skipped += 1
            continue
        barren = float(c["barren_fraction"])
        cells.append({
            "id": t["id"],
            "region": t["region"],
            "lat": round(float(t["lat"]), 5),
            "lon": round(float(t["lon"]), 5),
            "features": {k: round(v, DECIMALS[k]) for k, v in features.items()},
            "surface": {
                "nonvegetated_fraction": float(c["nonvegetated_fraction"]),
                "barren_fraction": barren,
                # Majority IGBP class 16 => "barren"; otherwise sparse vegetation passed the filter.
                "landcover": "barren" if barren >= 0.5 else "sparsely_vegetated",
            },
            "quality": {
                "coverage_fraction": float(t["valid_fraction"]),
                "excluded_landcover_fraction": float(c["excluded_landcover_fraction"]),
                "flags": [],
                "data_status": "processed",
            },
        })

    out = {
        "schema_version": "1.0",
        "planet": "earth",
        "analysis": {
            "window_size_m": 10000,
            "analysis_resolution_m": 454.5,
            "grid": "22 x 22, average-resampled in a local Transverse Mercator projection per cell",
            "method": "terrain_features() from prep/mars_prep.py (same code as Mars); "
                      "steep threshold 15 deg; roughness sigma 1000 m",
        },
        "eligibility": {
            "min_nonvegetated_fraction": 0.70,
            "min_dem_coverage_fraction": 0.90,
            "max_excluded_landcover_fraction": 0.10,
            "excluded_igbp_classes": [12, 13, 14, 15, 17],
            "note": "Excluded land-cover threshold is provisional. Cells are region centres, "
                    "not verified access points.",
        },
        "sources": SOURCES,
        "cells": cells,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(out, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    regions = {}
    for c in cells:
        regions[c["region"]] = regions.get(c["region"], 0) + 1
    print(f"Wrote {len(cells)} cells ({skipped} skipped) -> {OUTPUT} "
          f"({OUTPUT.stat().st_size / 1e6:.2f} MB)")
    print("Per region:", regions)


if __name__ == "__main__":
    main()
