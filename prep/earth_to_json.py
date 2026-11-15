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
ATMOSPHERE = Path("data/earth_locations_atmosphere.csv")  # MERRA-2 2025 (Kristiyan)
THERMAL = Path("data/earth_thermal.csv")                  # MODIS LST + albedo 2023 (Albert)
THERMAL_NOQC = Path("data/earth_thermal_noqc_ids.txt")    # cells rerun without the MODIS QC filter
GEOLOGY = Path("data/earth_geology_by_id.csv")            # GLiM lithology (Boris)
# ATI = (1 - albedo) / dT needs a real day/night cycle: invalid near the poles or for tiny dT.
ATI_MIN_DT_K, ATI_MAX_ABS_LAT = 5.0, 60.0
OUTPUT = Path("frontend/public/data/earth_cells.json")
FEATURES = ["median_slope_deg", "steep_fraction", "relief_m", "roughness_m"]
WIND = "mean_wind_speed_ms"  # optional scored feature (slider, default weight 0)
ALBEDO = "albedo"            # optional scored feature (slider, default weight 0); MODIS broadband
DECIMALS = {"median_slope_deg": 3, "steep_fraction": 4, "relief_m": 1, "roughness_m": 2, WIND: 2, ALBEDO: 3}

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
    {"dataset": "NASA MERRA-2 M2TMNXFLX (SPEED) and M2TMNXSLV (U10M, V10M, PS), monthly means 2025",
     "native_resolution_m": 55000, "url": "https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/",
     "used_for": "mean wind speed (scored, optional); wind direction and surface pressure (context)"},
    {"dataset": "MODIS MOD11A2 v061 LST (day/night) and MCD43A3 v061 shortwave black-sky albedo, 2023",
     "native_resolution_m": 1000, "url": "https://doi.org/10.5067/MODIS/MOD11A2.061",
     "used_for": "context: surface temperatures, albedo, apparent thermal inertia (ATI)"},
    {"dataset": "GLiM v1.1 global lithological map (Hartmann & Moosdorf 2012)",
     "native_resolution_m": None, "url": "https://doi.org/10.1029/2012GC004370",
     "used_for": "context: rock type"},
]


def opt(v, nd):
    return round(float(v), nd) if v not in ("", None) else None


def tercile_edges(values):
    v = sorted(values)
    return v[len(v) // 3], v[2 * len(v) // 3]


def is_true(v):
    return str(v).strip() in ("1", "true", "True")


def main():
    with open(CANDIDATES, newline="", encoding="utf-8") as f:
        candidates = {r["id"]: r for r in csv.DictReader(f) if is_true(r["eligible"])}
    with open(TERRAIN, newline="", encoding="utf-8") as f:
        terrain = [r for r in csv.DictReader(f) if r["status"] == "ok"]
    with open(ATMOSPHERE, newline="", encoding="utf-8-sig") as f:
        atmos = {r["id"]: r for r in csv.DictReader(f)}
    with open(THERMAL, newline="", encoding="utf-8-sig") as f:
        thermal = {r["id"]: r for r in csv.DictReader(f) if r["status"] == "ok"}
    noqc = set(THERMAL_NOQC.read_text().split()) if THERMAL_NOQC.exists() else set()
    with open(GEOLOGY, newline="", encoding="utf-8-sig") as f:
        geology = {r["id"]: r for r in csv.DictReader(f)}

    def ati_valid(th):
        return (th is not None and th["ati"] != "" and float(th["dT_k"]) >= ATI_MIN_DT_K
                and abs(float(th["lat"])) <= ATI_MAX_ABS_LAT)
    ati_lo, ati_hi = tercile_edges([float(th["ati"]) for th in thermal.values() if ati_valid(th)])

    cells, skipped = [], 0
    for t in terrain:
        c = candidates.get(t["id"])
        a = atmos.get(t["id"])
        if a is None or a[WIND] == "":
            skipped += 1
            continue
        features = {k: float(t[k]) for k in FEATURES}
        features[WIND] = float(a[WIND])
        if c is None or not all(math.isfinite(v) for v in features.values()):
            skipped += 1
            continue
        barren = float(c["barren_fraction"])
        th, g = thermal.get(t["id"]), geology.get(t["id"], {})
        if th is not None and th["albedo_bsa_sw"] != "":
            features[ALBEDO] = float(th["albedo_bsa_sw"])  # missing -> key absent (never 0)
        flags = []
        ati = None
        if th is None:
            flags.append("thermal_missing")
        else:
            if ati_valid(th):
                ati = float(th["ati"])
            else:
                flags.append("ati_invalid_polar_or_small_day_night_range")
            if th["lst_obs_fraction"] and float(th["lst_obs_fraction"]) < 0.1:
                flags.append("thermal_few_observations")
            if t["id"] in noqc:
                flags.append("thermal_no_quality_filter")
        ati_class = None if ati is None else ("low" if ati < ati_lo else "medium" if ati < ati_hi else "high")
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
            "context": {
                "prevailing_wind_direction_deg": round(float(a["prevailing_wind_direction_deg"]), 1)
                if a["prevailing_wind_direction_deg"] else None,
                "surface_pressure_pa": round(float(a["mean_surface_pressure_pa"]), 0),
                "albedo_shortwave": opt(th and th["albedo_bsa_sw"], 3),
                "lst_day_k": opt(th and th["lst_day_k"], 1),
                "lst_night_k": opt(th and th["lst_night_k"], 1),
                "day_night_range_k": opt(th and th["dT_k"], 1),
                "ati": None if ati is None else round(ati, 4),
                "ati_class": ati_class,
                "geology": g.get("geo_lithology") or None,
                "geology_group": g.get("geo_group") or None,
            },
            "quality": {
                "coverage_fraction": float(t["valid_fraction"]),
                "excluded_landcover_fraction": float(c["excluded_landcover_fraction"]),
                "flags": flags,
                "data_status": "processed",
            },
        })

    out = {
        "schema_version": "1.0",
        "context_notes": {
            "ati": "Apparent thermal inertia (1 - albedo) / day-night LST range, 1/K. Relative index only; "
                   "NOT comparable with Mars thermal inertia (tiu). Strongly affected by soil moisture. "
                   f"Null where |lat| > {ATI_MAX_ABS_LAT:g} deg or day-night range < {ATI_MIN_DT_K:g} K.",
            "ati_class": f"Terciles over valid Earth cells: low < {ati_lo:.4f} <= medium < {ati_hi:.4f} <= high.",
            "albedo_shortwave": "MODIS broadband (0.3-5 um) black-sky albedo; Mars uses OMEGA 1.08 um.",
        },
        "planet": "earth",
        "analysis": {
            "window_size_m": 10000,
            "analysis_resolution_m": 454.5,
            "grid": "22 x 22, average-resampled in a local Transverse Mercator projection per cell",
            "method": "terrain_features() from prep/mars_prep.py (same code as Mars); "
                      "steep threshold 15 deg; roughness sigma 1000 m. Mean wind speed: MERRA-2 "
                      "SPEED, nearest grid point, day-weighted 2025 annual mean (lowest model layer).",
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
    print(f"ATI terciles: {ati_lo:.4f} / {ati_hi:.4f}; "
          f"flags: {sum(1 for c in cells if c['quality']['flags'])} cells flagged")


if __name__ == "__main__":
    main()
