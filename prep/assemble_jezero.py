
#!/usr/bin/env python3
"""
Assemble final Jezero scientific profiles.

Included:
    - Terrain
    - Geology
    - Minerals
    - Thermal inertia
    - Wind

Excluded:
    - Albedo
    - Dust

Run:
    .\\.venv\\Scripts\\python.exe prep/assemble_jezero.py

Outputs:
    data/combined/jezero_01.json
    data/combined/jezero_rim_01.json
    data/combined/jezero_sites.json
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path

from merge_mars import merge


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUT = DATA / "combined"

RIM_ID = "jezero_rim_01"
FLOOR_ID = "jezero_01"

RIM_LAT = 18.392333
RIM_LON = 77.260676

MARS_RADIUS_KM = 3396.190

EXCLUDED_MODULES = {"albedo", "dust"}

EXPECTED_MODULES = {
    "geology",
    "minerals",
    "thermal",
    "wind",
}


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing required file: {path}"
        )

    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)

    if not isinstance(obj, dict):
        raise ValueError(
            f"Expected JSON object: {path}"
        )

    return obj


def save_json(path: Path, obj: dict):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            obj,
            f,
            indent=2,
            ensure_ascii=False,
            allow_nan=False
        )
        f.write("\n")

    print(f"Saved: {path.relative_to(ROOT)}")


def valid_number(value):
    if isinstance(value, bool):
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    return result if math.isfinite(result) else None


def mars_distance_km(lat1, lon1, lat2, lon2):
    """
    Great-circle distance on Mars.
    """

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    dlat = lat2 - lat1

    dlon = math.radians(
        ((lon2 - lon1 + 180) % 360) - 180
    )

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return (
        2
        * MARS_RADIUS_KM
        * math.asin(min(1.0, math.sqrt(a)))
    )


def geographic_center(obj):
    """
    Accept either:
        center_geographic: {lat, lon_east}
    or:
        lat, lon
    """

    center = obj.get("center_geographic")

    if not isinstance(center, dict):
        center = obj

    lat = valid_number(
        center.get(
            "lat",
            center.get("latitude")
        )
    )

    lon = valid_number(
        center.get(
            "lon_east",
            center.get("lon")
        )
    )

    if lat is None or lon is None:
        raise ValueError(
            "Missing geographic coordinates"
        )

    if not -90 <= lat <= 90:
        raise ValueError("Invalid latitude")

    return lat, lon


def load_thermal():
    """
    Read teammate's TES thermal inertia JSON.
    Preserve detailed, regional and context statistics.
    """

    path = DATA / "jezero_rim_01_ti.json"
    raw = read_json(path)

    source_id = raw.get(
        "location_id",
        raw.get("id")
    )

    if source_id != RIM_ID:
        raise ValueError(
            f"Thermal location mismatch: {source_id}"
        )

    lat, lon = geographic_center(raw)

    distance = mars_distance_km(
        lat,
        lon,
        RIM_LAT,
        RIM_LON
    )

    if distance > 0.5:
        raise ValueError(
            f"Thermal center is {distance:.2f} km "
            "away from the selected rim location"
        )

    scales = {}

    for scale in ("regional", "detailed", "context"):
        block = raw.get(scale)

        if not isinstance(block, dict):
            continue

        source_features = block.get(
            "features", {}
        )

        if not isinstance(source_features, dict):
            raise ValueError(
                f"Thermal {scale}: features must be an object"
            )

        features = {}

        for key, value in source_features.items():
            if not key.endswith("_ti"):
                continue

            number = valid_number(value)

            if number is None or number <= 0:
                raise ValueError(
                    f"Invalid thermal inertia: "
                    f"{scale}.{key}={value}"
                )

            features[key] = number

        quality = block.get("quality", {})

        if not isinstance(quality, dict):
            quality = {}

        scales[scale] = {
            "region_km": block.get("region_km"),
            "grid_width": block.get("grid_width"),
            "grid_height": block.get("grid_height"),
            "effective_pixel_size_m": deepcopy(
                block.get("effective_pixel_size_m")
            ),
            "features": features,
            "quality": deepcopy(quality),
            "data_status": (
                "processed" if features
                else "no_valid_features"
            )
        }

    detailed = scales.get("detailed")

    if not detailed or not detailed["features"]:
        raise ValueError(
            "Missing valid detailed thermal measurements"
        )

    module = {
        "location_id": RIM_ID,
        "category": "thermal",
        "data_status": "processed",

        "features": deepcopy(
            detailed["features"]
        ),

        "analysis": {
            "center_geographic": {
                "lat": lat,
                "lon_east": lon
            },
            "source_resolution_m": raw.get(
                "source_resolution_m"
            ),
            "measurement_type": (
                "coarse_satellite_thermal_inertia"
            )
        },

        "quality": {
            "flags": [
                "coarse_resolution",
                "not_used_in_default_terrain_similarity",
                "requires_comparable_earth_thermal_data"
            ],
            "detailed_valid_fraction": (
                detailed["quality"].get(
                    "valid_fraction"
                )
            )
        },

        "source": {
            "dataset": raw.get("source"),
            "source_file": raw.get("source_file"),
            "source_mask_file": raw.get(
                "source_mask_file"
            ),
            "unit": raw.get(
                "methods", {}
            ).get("unit"),
            "input_json": str(
                path.relative_to(ROOT)
            )
        },

        **scales
    }

    print(
        "Thermal inertia loaded:",
        module["features"].get("median_ti"),
        "tiu"
    )

    return module


def load_wind():
    """
    Read MACDA modeled wind data.

    The source coordinates are different from the
    exact Jezero Western Rim center, so preserve them.
    """

    path = DATA / "jezero_crater.json"
    raw = read_json(path)

    dataset = str(
        raw.get("source_dataset", "")
    )

    if "MACDA" not in dataset.upper():
        raise ValueError(
            "Wind source is not identified as MACDA"
        )

    lat, lon = geographic_center(raw)

    distance = mars_distance_km(
        lat,
        lon,
        RIM_LAT,
        RIM_LON
    )

    if distance > 50:
        raise ValueError(
            f"Wind source is {distance:.2f} km away. "
            "Review before attaching to Jezero Rim."
        )

    summary = raw.get("summary", {})

    if not isinstance(summary, dict):
        raise ValueError(
            "Invalid MACDA summary"
        )

    keys = (
        "mean_wind_speed_ms",
        "p95_wind_speed_ms",
        "wind_speed_std_ms",
        "prevailing_wind_direction_deg",
        "mean_surface_pressure_pa"
    )

    features = {}

    for key in keys:
        if key not in summary:
            raise ValueError(
                f"Missing MACDA feature: {key}"
            )

        value = valid_number(summary[key])

        if value is None:
            raise ValueError(
                f"Invalid MACDA feature: {key}"
            )

        features[key] = value

    if (
        features["mean_wind_speed_ms"] < 0
        or features["p95_wind_speed_ms"] < 0
        or features["wind_speed_std_ms"] < 0
        or features["mean_surface_pressure_pa"] <= 0
        or not (
            0 <= features[
                "prevailing_wind_direction_deg"
            ] <= 360
        )
    ):
        raise ValueError(
            "MACDA contains physically invalid summary values"
        )

    module = {
        "location_id": RIM_ID,
        "category": "wind",
        "data_status": "processed_regional_context",

        "features": features,

        "analysis": {
            "requested_center": {
                "lat": RIM_LAT,
                "lon_east": RIM_LON
            },
            "source_model_point": {
                "lat": lat,
                "lon_east": lon
            },
            "distance_from_site_km": round(
                distance, 3
            ),
            "measurement_type": (
                "nearby_modeled_atmospheric_data"
            )
        },

        "quality": {
            "sample_count": summary.get(
                "sample_count"
            ),
            "valid_wind_samples": summary.get(
                "valid_wind_samples"
            ),
            "flags": [
                "model_not_direct_observation",
                "source_location_differs_from_site",
                "sampled_periods_not_full_martian_year",
                "not_used_in_default_terrain_similarity"
            ]
        },

        "source": {
            "dataset": dataset,
            "data_type": raw.get(
                "data_type"
            ),
            "source_location_id": raw.get("id"),
            "sampled_period_count": raw.get(
                "sampled_period_count"
            ),
            "mars_years_sampled": raw.get(
                "mars_years_sampled"
            ),
            "wind_height_note": raw.get(
                "wind_height_note"
            ),
            "sampling_note": raw.get(
                "sampling_note"
            ),
            "input_json": str(
                path.relative_to(ROOT)
            )
        }
    }

    print(
        "Wind loaded:",
        f"{features['mean_wind_speed_ms']:.2f} m/s"
    )

    print(
        "Wind source distance:",
        f"{distance:.2f} km"
    )

    return module


def clean_profile(profile):
    """
    Remove all excluded modules and references.
    """

    modules = profile.setdefault("modules", {})

    for category in EXCLUDED_MODULES:
        modules.pop(category, None)

    missing = set(
        profile.get("missing_modules", [])
    )

    missing -= EXCLUDED_MODULES

    for category in EXPECTED_MODULES:
        if category not in modules:
            missing.add(category)
        else:
            missing.discard(category)

    profile["missing_modules"] = sorted(missing)

    profile["invalid_modules"] = sorted(
        name
        for name, module in modules.items()
        if module.get("data_status") in (
            "invalid_values",
            "error"
        )
    )

    return profile


def assemble_rim():
    """
    Western Rim: all five chosen categories.
    """

    print("\n=== JEZERO WESTERN RIM ===")

    rim = merge(
        DATA / "jezero_rim_features.json",
        DATA / "parts" / RIM_ID
    )

    if rim.get("location_id") != RIM_ID:
        raise ValueError(
            "Unexpected western-rim location ID"
        )

    # Force current validated module versions.
    rim.setdefault("modules", {})

    rim["modules"]["thermal"] = load_thermal()
    rim["modules"]["wind"] = load_wind()

    rim = clean_profile(rim)

    save_json(
        OUTPUT / "jezero_rim_01.json",
        rim
    )

    return rim


def assemble_floor():
    """
    Original Jezero crater floor.

    This location has terrain and geology.
    The mineral map has no coverage here.
    """

    print("\n=== JEZERO CRATER FLOOR ===")

    terrain_path = DATA / "jezero_features.json"

    if not terrain_path.is_file():
        print(
            "WARNING: jezero_features.json not found; "
            "skipping crater-floor profile"
        )
        return None

    floor = merge(
        terrain_path,
        DATA / "parts" / FLOOR_ID
    )

    if floor.get("location_id") != FLOOR_ID:
        raise ValueError(
            "Unexpected crater-floor location ID"
        )

    floor = clean_profile(floor)

    save_json(
        OUTPUT / "jezero_01.json",
        floor
    )

    return floor


def main():
    OUTPUT.mkdir(
        parents=True,
        exist_ok=True
    )

    rim = assemble_rim()
    floor = assemble_floor()

    sites = []

    if floor is not None:
        sites.append({
            "location_id": FLOOR_ID,
            "name": floor.get(
                "name",
                "Jezero Crater"
            ),
            "profile": floor
        })

    sites.append({
        "location_id": RIM_ID,
        "name": rim.get(
            "name",
            "Jezero Western Rim"
        ),
        "profile": rim
    })

    database = {
        "planet": "mars",
        "sites": sites,

        "scientific_categories": [
            "terrain",
            "geology",
            "minerals",
            "thermal",
            "wind"
        ],

        "excluded_categories": [
            "albedo",
            "dust"
        ],

        "notes": (
            "Jezero crater floor and western rim are "
            "separate terrain regions. Wind represents "
            "nearby modeled atmospheric conditions. "
            "Thermal inertia is coarse-resolution context. "
            "Only compatible terrain metrics are used "
            "in the default Earth similarity ranking."
        )
    }

    save_json(
        OUTPUT / "jezero_sites.json",
        database
    )

    print("\n=== FINAL RESULTS ===")

    for site in sites:
        profile = site["profile"]

        categories = ["terrain"] + list(
            profile.get("modules", {}).keys()
        )

        print(
            f"\n{site['location_id']}"
        )

        print(
            "Categories:",
            categories
        )

        print(
            "Missing:",
            profile.get("missing_modules", [])
        )

        print(
            "Invalid:",
            profile.get("invalid_modules", [])
        )

    print("\nJezero assembly complete.")


if __name__ == "__main__":
    main()
