#!/usr/bin/env python3
r"""Assemble Gale/Bradbury Landing science data into the Jezero-style profile.

Run from repository root:
    .\.venv\Scripts\python.exe prep/assemble_gale.py

No external dependencies. Requires all six source JSON files. Satellite data
centered away from Bradbury Landing are included in full as Gale-region context,
with source coordinates and distances clearly recorded. They are not treated as
site-level scores without reprocessing at the Bradbury Landing location.
"""

import json
import math
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE_ID = "gale_01"
MARS_RADIUS_KM = 3396.190
FILES = {
    "terrain": DATA / "gale_features.json",
    "geology": DATA / "parts" / SITE_ID / "geology.json",
    "minerals": DATA / "parts" / SITE_ID / "minerals.json",
    "thermal": DATA / "ti" / "gale_crater_ti.json",
    "albedo": DATA / "albedo" / "gale_crater_albedo.json",
    "wind": DATA / "atmosphere" / "gale_crater.json",
}


def load(path):
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path.relative_to(ROOT)}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def distance_km(lat1, lon1, lat2, lon2):
    p, q = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lat2 - lat1)
    dn = math.radians(((lon2 - lon1 + 180) % 360) - 180)
    h = math.sin(dl / 2) ** 2 + math.cos(p) * math.cos(q) * math.sin(dn / 2) ** 2
    return 2 * MARS_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def source_center(source):
    point = source.get("center_geographic") or source
    lat = point.get("lat")
    lon = point.get("lon_east", point.get("lon"))
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        raise ValueError("Missing numeric source latitude/longitude")
    if not (-90 <= lat <= 90):
        raise ValueError("Invalid source latitude")
    return float(lat), float(lon)


def assert_same_site(module, name, terrain):
    if module.get("location_id") != SITE_ID or module.get("category") != name:
        raise ValueError(f"{name} module must have location_id={SITE_ID} and category={name}")
    if module.get("analysis", {}).get("center_projected_m") != terrain.get("center_projected_m"):
        raise ValueError(f"{name} module was prepared for a different terrain center")


def environment(category, raw, center, path):
    original_id = raw.get("id", raw.get("location_id"))
    if original_id not in {"gale_crater", SITE_ID}:
        raise ValueError(f"{path.name} has unexpected source site ID: {original_id}")
    lat, lon = source_center(raw)
    dist = distance_km(center["lat"], center["lon_east"], lat, lon)
    source_res = raw.get("source_resolution_m")
    if not isinstance(source_res, (float, int)) or source_res <= 0:
        raise ValueError(f"{category}: invalid source resolution")
    for scale in ("regional", "detailed"):
        section = raw.get(scale)
        if not isinstance(section, dict) or not isinstance(section.get("features"), dict):
            raise ValueError(f"{category}: missing {scale} satellite statistics")
    key = "median_ti" if category == "thermal" else "median_albedo"
    for scale in ("regional", "detailed"):
        v = raw[scale]["features"].get(key)
        if not isinstance(v, (float, int)) or not math.isfinite(v):
            raise ValueError(f"{category}: missing or invalid {scale}.{key}")
        if not (v > 0 if category == "thermal" else 0 <= v <= 1):
            raise ValueError(f"{category}: out-of-range {scale}.{key}={v}")
    # Source window of detailed extraction is only 5 km wide. A different
    # center beyond its half-width cannot describe the selected 5 km location.
    within_site = dist <= 2.5
    source_info = {
        "dataset": raw.get("source"),
        "original_source_id": original_id,
        "source_file": raw.get("source_file"),
        "source_mask_file": raw.get("source_mask_file"),
        "unit": raw.get("methods", {}).get("unit"),
        "original_role": raw.get("role"),
        "input_json": path.relative_to(ROOT).as_posix(),
        "role": "contextual_only" if category == "albedo" else "conditional_quantitative_context",
    }
    result = {
        "location_id": SITE_ID,
        "category": category,
        "data_status": "processed" if within_site else "processed_regional_context",
        "features": deepcopy(raw["detailed"]["features"]),
        "analysis": {
            "center_geographic": deepcopy(center),
            "source_center_geographic": {"lat": lat, "lon_east": lon},
            "source_center_distance_km": round(dist, 3),
            "source_resolution_m": source_res,
            "measurement_type": "coarse_satellite_context" if within_site else "offsite_satellite_reference",
        },
        "quality": {
            "detailed_valid_fraction": raw["detailed"].get("quality", {}).get("valid_fraction"),
            "flags": (["coarse_resolution", "not_used_in_default_terrain_similarity"]
                      + (["nir_albedo_not_directly_comparable_to_earth_albedo"] if category == "albedo"
                         else ["requires_validated_earth_thermal_equivalent"])
                      + ([] if within_site else ["satellite_center_outside_site_footprint", "reprocess_at_bradbury_landing"])),
        },
        "source": source_info,
        "scoring_eligible": False,  # Requires Earth comparison and shared feature definitions.
    }
    # Preserve ALL observed numbers in standard Jezero-style fields so the UI
    # can display Gale-region science. The centre offset and eligibility flags
    # distinguish them from measurements at Bradbury Landing.
    for scale in ("regional", "detailed", "context"):
        if isinstance(raw.get(scale), dict):
            result[scale] = deepcopy(raw[scale])
            result[scale]["data_status"] = "processed"
    return result, dist


def atmosphere(raw, center, path):
    if raw.get("id") not in {"gale_crater", SITE_ID}:
        raise ValueError(f"Atmosphere source ID is unexpected: {raw.get('id')}")
    lat, lon = source_center(raw)
    dist = distance_km(center["lat"], center["lon_east"], lat, lon)
    summary = raw.get("summary", {})
    fields = ("mean_wind_speed_ms", "p95_wind_speed_ms", "wind_speed_std_ms",
              "prevailing_wind_direction_deg", "mean_surface_pressure_pa")
    features = {}
    for field in fields:
        value = summary.get(field)
        if not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError(f"Missing or invalid atmosphere field: {field}")
        features[field] = value
    if (min(features["mean_wind_speed_ms"], features["p95_wind_speed_ms"],
            features["wind_speed_std_ms"]) < 0
            or not 0 <= features["prevailing_wind_direction_deg"] <= 360
            or features["mean_surface_pressure_pa"] <= 0):
        raise ValueError("Out-of-range MACDA atmosphere values")
    return {
        "location_id": SITE_ID,
        "category": "wind",
        "data_status": "processed_regional_context",
        "features": features,
        "analysis": {
            "requested_center": deepcopy(center),
            "source_reference_center": {"lat": lat, "lon_east": lon},
            "distance_from_site_km": round(dist, 3),
            "measurement_type": "regional_modeled_atmospheric_context",
        },
        "quality": {
            "sample_count": summary.get("sample_count"),
            "valid_wind_samples": summary.get("valid_wind_samples"),
            "valid_pressure_samples": summary.get("valid_pressure_samples"),
            "flags": ["model_not_direct_observation", "source_reference_differs_from_site",
                      "source_model_grid_point_not_confirmed", "sampled_periods_not_full_martian_year",
                      "not_used_in_any_similarity_score"],
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
    }, dist


def main():
    inputs = {name: load(path) for name, path in FILES.items()}
    terrain = inputs["terrain"]
    if terrain.get("id") != SITE_ID:
        raise ValueError("Gale terrain ID is not gale_01")
    coords = terrain.get("center_geographic", {})
    if not isinstance(coords.get("lat"), (int, float)) or not isinstance(coords.get("lon_east"), (int, float)):
        raise ValueError("Gale terrain must contain computed center_geographic lat/lon")
    center = {"lat": float(coords["lat"]), "lon_east": float(coords["lon_east"])}
    if not (-90 <= center["lat"] <= 90):
        raise ValueError("Invalid terrain center latitude")
    for scale in ("regional", "detailed"):
        feats = terrain.get(scale, {}).get("features", {})
        if not all(isinstance(feats.get(key), (int, float)) and math.isfinite(feats[key])
                   for key in ("median_slope_deg", "steep_fraction", "relief_m", "roughness_m")):
            raise ValueError(f"Terrain missing finite {scale} features")

    geology = inputs["geology"]
    minerals = inputs["minerals"]
    assert_same_site(geology, "geology", terrain)
    assert_same_site(minerals, "minerals", terrain)

    thermal, ti_distance = environment("thermal", inputs["thermal"], center, FILES["thermal"])
    albedo, albedo_distance = environment("albedo", inputs["albedo"], center, FILES["albedo"])
    wind, wind_distance = atmosphere(inputs["wind"], center, FILES["wind"])

    # All six categories are present. Source centre mismatch is a documented
    # spatial limitation, not malformed or missing data.
    invalid = []
    missing = []
    if minerals.get("data_status") not in {"processed", "literature_supported"}:
        missing.append("minerals")
    if geology.get("data_status") != "processed":
        missing.append("geology")
    profile = {
        "location_id": SITE_ID,
        "name": terrain.get("name", "Gale Crater - Bradbury Landing"),
        "center_geographic": center,
        "terrain": terrain,
        "modules": {
            "geology": geology,
            "minerals": minerals,
            "thermal": thermal,
            "albedo": albedo,
            "wind": wind,
        },
        "missing_modules": sorted(missing),
        "invalid_modules": sorted(invalid),
        "similarity_readiness": {
            "stage_1_terrain": True,
            "stage_2_surface_material": False,
            "stage_2_geology": False,
            "stage_2_minerals": False,
            "note": "Stage 2 requires equivalent Earth features and scientifically defensible class mappings. Literature mineral observations are not polygon area fractions.",
        },
        "scientific_limitations": [
            "Geology is based on a coarse 1:20,000,000 global map, unlike Jezero's local geologic map.",
            "Minerals come from qualitative literature observations; no measured 5 km mineral area fractions exist.",
            "Wind and pressure are regional MACDA modeled context, not local in-situ measurements.",
            "OMEGA NIR albedo is not directly comparable to Earth broadband albedo.",
        ],
    }
    if max(ti_distance, albedo_distance) > 2.5:
        profile["scientific_limitations"].append(
            "Thermal inertia and albedo values are real Gale-region measurements centered roughly 52 km from Bradbury Landing. "
            "These should be displayed with their source locations and not scored as local 5 km surface similarity without recalculation."
        )

    output = DATA / "combined" / "gale_01.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Created: {output.relative_to(ROOT)}")
    print(f"Gale center: {center['lat']:.4f}°, {center['lon_east']:.4f}°E")
    print(f"TI center offset: {ti_distance:.2f} km | albedo center offset: {albedo_distance:.2f} km")
    print(f"Atmosphere reference offset: {wind_distance:.2f} km (context only)")
    print("Included modules:", ", ".join(profile["modules"]))
    print("Missing modules:", profile["missing_modules"])
    print("Invalid modules:", profile["invalid_modules"])
    print("Stage 1 terrain matching: READY")
    if max(ti_distance, albedo_distance) > 2.5:
        print("NOTE: TI and albedo values are from Gale Crater, but not the Bradbury Landing footprint.")
    if minerals.get("data_status") == "literature_supported":
        print("NOTE: qualitative mineral observations are context only, not measured map fractions.")


if __name__ == "__main__":
    main()
