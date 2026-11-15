#!/usr/bin/env python3
r"""Assemble the Nili Patera Mars profile using the Jezero/Gale schema.

Run from the project root (PowerShell):
    .\.venv\Scripts\python.exe prep/assemble_nili_patera.py

No external Python dependencies. Loads all scientific data from the repository.
Qualitative mineral evidence is included as context, not as mapped mineral fractions.
Wind and pressure are contextual MACDA model measurements, not similarity inputs.
"""

import json
import math
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE_ID = "nili_patera_01"
SOURCE_ID = "nili_patera"
MARS_RADIUS_KM = 3396.19
EXPECTED_LAT = 8.9
EXPECTED_LON = 67.2

PATHS = {
    "terrain": DATA / "nili_patera_features.json",
    "geology": DATA / "parts" / SITE_ID / "geology.json",
    "minerals": DATA / "parts" / SITE_ID / "minerals.json",
    "thermal": DATA / "ti" / "nili_patera_ti.json",
    "albedo": DATA / "albedo" / "nili_patera_albedo.json",
    "wind": DATA / "atmosphere" / "nili_patera.json",
}


def load_json(path):
    if not path.is_file():
        raise FileNotFoundError(f"Missing input: {path.relative_to(ROOT)}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def coords_from(data):
    geo = data.get("center_geographic")
    if not isinstance(geo, dict):
        geo = data
    lat = geo.get("lat")
    lon = geo.get("lon_east", geo.get("lon"))
    if not numeric(lat) or not numeric(lon) or not -90 <= lat <= 90:
        raise ValueError("Missing or invalid geographic coordinates")
    return float(lat), float(lon) % 360


def distance_km(a_lat, a_lon, b_lat, b_lon):
    dlat = math.radians(b_lat - a_lat)
    dlon = math.radians(((b_lon - a_lon + 180) % 360) - 180)
    x = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.sin(dlon / 2) ** 2
    return 2 * MARS_RADIUS_KM * math.asin(min(1, math.sqrt(x)))


def check_terrain(terrain):
    if terrain.get("id") != SITE_ID:
        raise ValueError(f"Terrain ID should be {SITE_ID!r}")
    lat, lon = coords_from(terrain)
    if distance_km(lat, lon, EXPECTED_LAT, EXPECTED_LON) > 0.1:
        raise ValueError("Terrain is not centered at our selected 8.9 N, 67.2 E site")
    center = {"lat": lat, "lon_east": lon}
    for scale, wanted_km in (("regional", 10), ("detailed", 5)):
        block = terrain.get(scale, {})
        if block.get("region_km") != wanted_km:
            raise ValueError(f"Incorrect terrain {scale} footprint size")
        for feature in ("median_slope_deg", "steep_fraction", "relief_m", "roughness_m"):
            if not numeric(block.get("features", {}).get(feature)):
                raise ValueError(f"Invalid {scale} terrain metric: {feature}")
        res = block.get("effective_pixel_size_m", [])
        if len(res) != 2 or not all(numeric(v) and v > 0 for v in res):
            raise ValueError(f"Terrain {scale} has invalid pixel resolution")
    return center


def check_local_module(module, category, terrain):
    if module.get("location_id") != SITE_ID or module.get("category") != category:
        raise ValueError(f"{category} must have location_id={SITE_ID} and category={category}")
    center = module.get("analysis", {}).get("center_projected_m")
    if not isinstance(center, dict):
        raise ValueError(f"{category} is missing projected analysis center")
    true_center = terrain.get("center_projected_m", {})
    if any(not numeric(center.get(axis)) or abs(center[axis] - true_center[axis]) > 1 for axis in ("x", "y")):
        raise ValueError(f"{category} is not centered on Nili terrain reference point")
    if category == "geology" and module.get("data_status") != "processed":
        raise ValueError("Nili geology was not processed")
    if category == "minerals" and module.get("data_status") not in ("literature_supported", "processed", "no_coverage"):
        raise ValueError("Unexpected mineral module data_status")


def convert_surface(raw, category, center, path):
    source_id = raw.get("id")
    if source_id not in (SOURCE_ID, SITE_ID):
        raise ValueError(f"{category}: unexpected source ID {source_id!r}")
    lat, lon = coords_from(raw)
    offset = distance_km(center["lat"], center["lon_east"], lat, lon)
    res = raw.get("source_resolution_m")
    if not numeric(res) or res <= 0:
        raise ValueError(f"{category}: invalid satellite source resolution")
    metric = "median_ti" if category == "thermal" else "median_albedo"
    for scale in ("regional", "detailed"):
        v = raw.get(scale, {}).get("features", {}).get(metric)
        if not numeric(v) or (v <= 0 if category == "thermal" else not 0 <= v <= 1):
            raise ValueError(f"{category}: missing/out-of-range {scale}.{metric}")
    matched = offset < 0.1
    flags = ["coarse_resolution", "not_used_in_default_terrain_similarity"]
    if category == "thermal":
        flags.append("requires_comparable_earth_thermal_data_for_stage2")
    else:
        flags.append("nir_albedo_not_directly_equivalent_to_earth_broadband_albedo")
    if not matched:
        flags += ["source_location_differs_from_site", "reprocess_at_nili_reference_point"]
    result = {
        "location_id": SITE_ID,
        "category": category,
        "data_status": "processed" if matched else "processed_regional_context",
        "features": deepcopy(raw["detailed"]["features"]),
        "analysis": {
            "center_geographic": deepcopy(center),
            "source_center_geographic": {"lat": lat, "lon_east": lon},
            "source_center_distance_km": round(offset, 3),
            "source_resolution_m": res,
            "measurement_type": "coarse_satellite_context" if matched else "offsite_satellite_reference",
        },
        "quality": {
            "detailed_valid_fraction": raw["detailed"].get("quality", {}).get("valid_fraction"),
            "flags": flags,
        },
        "source": {
            "dataset": raw.get("source"),
            "original_source_id": source_id,
            "source_file": raw.get("source_file"),
            "source_mask_file": raw.get("source_mask_file"),
            "unit": raw.get("methods", {}).get("unit"),
            "original_role": raw.get("role"),
            "input_json": path.relative_to(ROOT).as_posix(),
            "role": "contextual_only" if category == "albedo" else "conditional_quantitative_context",
        },
        "scoring_eligible": False,  # No verified comparable Earth measurement in hand
    }
    for scale in ("regional", "detailed", "context"):
        if isinstance(raw.get(scale), dict):
            result[scale] = deepcopy(raw[scale])
            result[scale]["data_status"] = "processed"
    return result, offset


def convert_wind(raw, center, path):
    if raw.get("id") not in (SOURCE_ID, SITE_ID):
        raise ValueError(f"Wind source ID should be {SOURCE_ID!r} or {SITE_ID!r}")
    lat, lon = coords_from(raw)
    offset = distance_km(center["lat"], center["lon_east"], lat, lon)
    summary = raw.get("summary", {})
    fields = ("mean_wind_speed_ms", "p95_wind_speed_ms", "wind_speed_std_ms",
              "prevailing_wind_direction_deg", "mean_surface_pressure_pa")
    measurements = {}
    for field in fields:
        v = summary.get(field)
        if not numeric(v):
            raise ValueError(f"Wind/pressure: missing or invalid {field}")
        measurements[field] = v
    if (min(measurements[f] for f in fields[:3]) < 0
        or not 0 <= measurements["prevailing_wind_direction_deg"] <= 360
        or measurements["mean_surface_pressure_pa"] <= 0):
        raise ValueError("Invalid wind or pressure values")
    flags = ["model_not_direct_observation", "source_model_grid_point_not_confirmed",
             "sampled_periods_not_full_martian_year", "not_used_in_any_similarity_score"]
    if offset > 0.1:
        flags.append("source_reference_differs_from_site")
    return {
        "location_id": SITE_ID,
        "category": "wind",
        "data_status": "processed_regional_context",
        "features": measurements,
        "analysis": {
            "requested_center": deepcopy(center),
            "source_reference_center": {"lat": lat, "lon_east": lon},
            "distance_from_site_km": round(offset, 3),
            "measurement_type": "regional_modeled_atmospheric_context",
        },
        "quality": {
            "sample_count": summary.get("sample_count"),
            "valid_wind_samples": summary.get("valid_wind_samples"),
            "valid_pressure_samples": summary.get("valid_pressure_samples"),
            "flags": flags,
        },
        "source": {
            "dataset": raw.get("source_dataset"),
            "source_location_id": raw.get("id"),
            "data_type": raw.get("data_type"),
            "coordinate_quality": raw.get("coordinate_quality"),
            "sampled_period_count": raw.get("sampled_period_count"),
            "mars_years_sampled": deepcopy(raw.get("mars_years_sampled")),
            "wind_height_note": raw.get("wind_height_note"),
            "sampling_note": raw.get("sampling_note"),
            "input_json": path.relative_to(ROOT).as_posix(),
        },
        "scoring_eligible": False,
    }, offset


def main():
    inputs = {name: load_json(path) for name, path in PATHS.items()}
    terrain = inputs["terrain"]
    center = check_terrain(terrain)
    geology = inputs["geology"]
    minerals = inputs["minerals"]
    check_local_module(geology, "geology", terrain)
    check_local_module(minerals, "minerals", terrain)
    thermal, td = convert_surface(inputs["thermal"], "thermal", center, PATHS["thermal"])
    albedo, ad = convert_surface(inputs["albedo"], "albedo", center, PATHS["albedo"])
    wind, wd = convert_wind(inputs["wind"], center, PATHS["wind"])
    if max(td, ad) > 1.0:
        print("WARNING: Satellite source center is more than 1 km from Nili reference point")

    missing = []
    if minerals["data_status"] == "no_coverage":
        missing.append("minerals")
    profile = {
        "location_id": SITE_ID,
        "name": terrain.get("name", "Nili Patera"),
        "center_geographic": center,
        "terrain": terrain,
        "modules": {
            "geology": geology,
            "minerals": minerals,
            "thermal": thermal,
            "albedo": albedo,
            "wind": wind,
        },
        "missing_modules": missing,
        "invalid_modules": [],
        "similarity_readiness": {
            "stage_1_terrain": True,
            "stage_2_surface_material": False,
            "stage_2_geology": False,
            "stage_2_minerals": False,
            "note": "Stage 2 depends on validated comparable Earth TI/albedo and shared geological/mineral class mappings. The Nili mineral module is literature-based and not quantified.",
        },
        "scientific_limitations": [
            "Regional and detailed MOLA terrain have approximately 460 m pixel resolution; detailed is not 30 m terrain.",
            "Global USGS geological mapping (1:20,000,000) cannot resolve local volcanic units within a 5 km site.",
            "Mineral classes are literature-based occurrences across Nili Patera, not verified 5 km mapped mineral-area fractions.",
            "MGS/TES thermal inertia is coarse and needs a comparable Earth-side product before similarity scoring.",
            "OMEGA near-infrared 1.08 micrometre albedo cannot be directly scored against Earth's broadband albedo.",
            "MACDA wind and pressure are modeled atmospheric context, never part of Earth similarity scores.",
        ],
    }
    if td > 0.1 or ad > 0.1:
        profile["scientific_limitations"].append(
            f"TI source center offset {td:.2f} km and albedo source center offset {ad:.2f} km from Nili terrain reference."
        )
    if wd > 0.1:
        profile["scientific_limitations"].append(
            f"Atmospheric reference coordinates are {wd:.2f} km from Nili terrain center; they are not confirmed model cell coordinates."
        )

    target = DATA / "combined" / (SITE_ID + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(profile, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print("Created:", target.relative_to(ROOT))
    print(f"Nili center: {center['lat']:.4f} N, {center['lon_east']:.4f} E")
    print(f"TI center offset: {td:.2f} km | Albedo center offset: {ad:.2f} km")
    print(f"Atmosphere reference offset: {wd:.2f} km (context only)")
    print("Included modules:", ", ".join(profile["modules"]))
    print("Missing modules:", profile["missing_modules"])
    print("Invalid modules:", profile["invalid_modules"])
    print("Stage 1 terrain matching: READY")
    if minerals.get("data_status") == "literature_supported":
        print("NOTE: Mineral observations are qualitative context, not mapped fractions.")


if __name__ == "__main__":
    main()
