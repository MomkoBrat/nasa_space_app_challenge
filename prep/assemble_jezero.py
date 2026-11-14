
#!/usr/bin/env python3
r"""Assemble Jezero terrain + geology + minerals + thermal + wind + albedo.

Run from the repository root:
    .\.venv\Scripts\python.exe prep/assemble_jezero.py

Inputs:
    data/jezero_features.json
    data/jezero_rim_features.json
    data/parts/jezero_01/*.json
    data/parts/jezero_rim_01/*.json
    data/jezero_rim_01_ti.json
    data/jezero_rim_01_albedo.json
    data/jezero_crater.json

Outputs:
    data/combined/jezero_01.json
    data/combined/jezero_rim_01.json
    data/combined/jezero_sites.json

Dust is excluded. Albedo is contextual only,
not part of Earth similarity scoring.
"""

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

EXCLUDED_MODULES = {"dust"}

EXPECTED_MODULES = {
    "geology",
    "minerals",
    "thermal",
    "wind",
    "albedo",
}


def read_json(path):
    if not path.is_file():
        raise FileNotFoundError(f"Missing file: {path}")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")

    return data


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        f.write("\n")

    print(f"Saved: {path.relative_to(ROOT)}")


def finite_number(value):
    if isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if math.isfinite(number) else None


def geographic_center(data):
    coords = data.get("center_geographic")

    if not isinstance(coords, dict):
        coords = data

    lat = finite_number(
        coords.get("lat", coords.get("latitude"))
    )

    lon = finite_number(
        coords.get(
            "lon_east",
            coords.get("lon", coords.get("longitude"))
        )
    )

    if lat is None or lon is None or not -90 <= lat <= 90:
        raise ValueError(
            "Source JSON is missing valid Mars geographic coordinates"
        )

    return lat, lon


def mars_distance_km(lat1, lon1, lat2, lon2):
    a = math.radians(lat1)
    b = math.radians(lat2)

    dlat = b - a

    dlon = math.radians(
        ((lon2 - lon1 + 180) % 360) - 180
    )

    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(a)
        * math.cos(b)
        * math.sin(dlon / 2) ** 2
    )

    return (
        2
        * MARS_RADIUS_KM
        * math.asin(min(1, math.sqrt(h)))
    )


def load_environment(category, filename):
    """
    Read thermal inertia or albedo JSON.

    Both use nested:
        regional.features
        detailed.features
        context.features
    """

    path = DATA / filename
    original = read_json(path)

    site_id = original.get(
        "location_id",
        original.get("id")
    )

    if site_id != RIM_ID:
        raise ValueError(
            f"{path.name}: expected location ID "
            f"{RIM_ID}, got {site_id}"
        )

    lat, lon = geographic_center(original)

    distance = mars_distance_km(
        lat, lon, RIM_LAT, RIM_LON
    )

    if distance > 0.5:
        raise ValueError(
            f"{path.name}: center is "
            f"{distance:.2f} km from Jezero rim"
        )

    suffix = (
        "_albedo"
        if category == "albedo"
        else "_ti"
    )

    scales = {}

    for scale in ("regional", "detailed", "context"):
        block = original.get(scale)

        if block is None:
            continue

        if (
            not isinstance(block, dict)
            or not isinstance(block.get("features"), dict)
        ):
            raise ValueError(
                f"{path.name}: {scale}.features "
                "must be an object"
            )

        features = {}

        for key, value in block["features"].items():

            if not key.endswith(suffix):
                continue

            number = finite_number(value)

            if category == "albedo":
                is_valid = (
                    number is not None
                    and 0 <= number <= 1
                )
            else:
                is_valid = (
                    number is not None
                    and number > 0
                )

            if not is_valid:
                raise ValueError(
                    f"{path.name}: INVALID "
                    f"{scale}.{key}={value}. "
                    + (
                        "Albedo must be between 0 and 1."
                        if category == "albedo"
                        else "Thermal inertia must be positive."
                    )
                )

            features[key] = number

        if not features:
            raise ValueError(
                f"{path.name}: no recognized "
                f"{category} values for {scale}"
            )

        quality = block.get("quality", {})

        if not isinstance(quality, dict):
            raise ValueError(
                f"{path.name}: {scale}.quality "
                "must be an object"
            )

        scales[scale] = {
            "region_km": block.get("region_km"),
            "grid_width": block.get("grid_width"),
            "grid_height": block.get("grid_height"),
            "effective_pixel_size_m": deepcopy(
                block.get("effective_pixel_size_m")
            ),
            "features": features,
            "quality": deepcopy(quality),
            "data_status": "processed",
        }

    if (
        "regional" not in scales
        or "detailed" not in scales
    ):
        raise ValueError(
            f"{path.name}: regional and detailed "
            "measurements are required"
        )

    is_albedo = category == "albedo"

    flags = [
        "coarse_resolution",
        "not_used_in_default_terrain_similarity",
    ]

    flags.append(
        "nir_albedo_contextual_only"
        if is_albedo
        else "requires_comparable_earth_thermal_data"
    )

    result = {
        "location_id": RIM_ID,
        "category": category,
        "data_status": "processed",

        "features": deepcopy(
            scales["detailed"]["features"]
        ),

        "analysis": {
            "center_geographic": {
                "lat": lat,
                "lon_east": lon,
            },
            "source_resolution_m": original.get(
                "source_resolution_m"
            ),
            "measurement_type": "coarse_satellite_context",
        },

        "quality": {
            "flags": flags,
            "detailed_valid_fraction": (
                scales["detailed"]["quality"].get(
                    "valid_fraction"
                )
            ),
        },

        "source": {
            "dataset": original.get("source"),
            "source_file": original.get("source_file"),
            "source_mask_file": original.get(
                "source_mask_file"
            ),
            "unit": original.get(
                "methods", {}
            ).get("unit"),
            "input_json": path.relative_to(
                ROOT
            ).as_posix(),
            "role": "contextual_only",
        },

        **scales,
    }

    print(
        f"{category.capitalize()} loaded: "
        f"{len(result['features'])} detailed measurements"
    )

    return result


def load_wind():
    """
    Read MACDA atmospheric data.

    Wind measurements are modeled regional context,
    not exact measurements at Jezero Western Rim.
    """

    path = DATA / "jezero_crater.json"
    raw = read_json(path)

    source_dataset = str(
        raw.get("source_dataset", "")
    )

    if "MACDA" not in source_dataset.upper():
        raise ValueError(
            "jezero_crater.json is not identified "
            "as MACDA wind data"
        )

    lat, lon = geographic_center(raw)

    separation = mars_distance_km(
        lat, lon, RIM_LAT, RIM_LON
    )

    if separation > 50:
        raise ValueError(
            f"Wind model point is {separation:.1f} km "
            "away; review location"
        )

    summary = raw.get("summary", {})

    if not isinstance(summary, dict):
        raise ValueError(
            "MACDA summary must be an object"
        )

    keys = (
        "mean_wind_speed_ms",
        "p95_wind_speed_ms",
        "wind_speed_std_ms",
        "prevailing_wind_direction_deg",
        "mean_surface_pressure_pa",
    )

    features = {}

    for key in keys:
        value = finite_number(
            summary.get(key)
        )

        if value is None:
            raise ValueError(
                f"MACDA missing/invalid: {key}"
            )

        features[key] = value

    if (
        min(
            features["mean_wind_speed_ms"],
            features["p95_wind_speed_ms"],
            features["wind_speed_std_ms"],
        ) < 0
        or not 0 <= features[
            "prevailing_wind_direction_deg"
        ] <= 360
        or features["mean_surface_pressure_pa"] <= 0
    ):
        raise ValueError(
            "MACDA wind summary contains "
            "out-of-range physical values"
        )

    print(
        f"Wind loaded: "
        f"{features['mean_wind_speed_ms']:.2f} m/s"
    )

    print(
        f"Wind source distance: "
        f"{separation:.2f} km"
    )

    return {
        "location_id": RIM_ID,
        "category": "wind",
        "data_status": "processed_regional_context",

        "features": features,

        "analysis": {
            "requested_center": {
                "lat": RIM_LAT,
                "lon_east": RIM_LON,
            },
            "source_model_point": {
                "lat": lat,
                "lon_east": lon,
            },
            "distance_from_site_km": round(
                separation, 3
            ),
            "measurement_type": (
                "nearby_modeled_atmospheric_data"
            ),
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
                "not_used_in_default_terrain_similarity",
            ],
        },

        "source": {
            "dataset": source_dataset,
            "data_type": raw.get("data_type"),
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
            "input_json": path.relative_to(
                ROOT
            ).as_posix(),
        },
    }


def clean_profile(profile):
    """
    Exclude dust and recalculate missing/invalid modules.
    """

    modules = profile.setdefault("modules", {})

    for name in EXCLUDED_MODULES:
        modules.pop(name, None)

    missing = (
        set(profile.get("missing_modules", []))
        - EXCLUDED_MODULES
    )

    missing.update(
        EXPECTED_MODULES - set(modules)
    )

    missing.difference_update(modules)

    profile["missing_modules"] = sorted(missing)

    profile["invalid_modules"] = sorted(
        name
        for name, module in modules.items()
        if module.get("data_status") in {
            "invalid_values",
            "error",
        }
    )

    return profile


def assemble_rim():
    print("\n=== JEZERO WESTERN RIM ===")

    rim = merge(
        DATA / "jezero_rim_features.json",
        DATA / "parts" / RIM_ID,
    )

    if rim.get("location_id") != RIM_ID:
        raise ValueError(
            "Wrong location ID in western-rim terrain"
        )

    modules = rim.setdefault("modules", {})

    # Thermal inertia
    modules["thermal"] = load_environment(
        "thermal",
        "jezero_rim_01_ti.json",
    )

    # Corrected albedo
    modules["albedo"] = load_environment(
        "albedo",
        "jezero_rim_01_albedo.json",
    )

    # MACDA wind
    modules["wind"] = load_wind()

    rim = clean_profile(rim)

    if rim["missing_modules"] or rim["invalid_modules"]:
        raise ValueError(
            "Rim profile incomplete: "
            f"missing={rim['missing_modules']}, "
            f"invalid={rim['invalid_modules']}"
        )

    save_json(
        OUTPUT / "jezero_rim_01.json",
        rim,
    )

    return rim


def assemble_floor():
    print("\n=== JEZERO CRATER FLOOR ===")

    path = DATA / "jezero_features.json"

    if not path.is_file():
        print(
            "WARNING: Jezero crater-floor terrain "
            "missing; skipping"
        )
        return None

    floor = merge(
        path,
        DATA / "parts" / FLOOR_ID,
    )

    if floor.get("location_id") != FLOOR_ID:
        raise ValueError(
            "Wrong location ID in crater-floor terrain"
        )

    floor = clean_profile(floor)

    save_json(
        OUTPUT / "jezero_01.json",
        floor,
    )

    return floor


def main():
    rim = assemble_rim()
    floor = assemble_floor()

    sites = []

    if floor is not None:
        sites.append({
            "location_id": FLOOR_ID,
            "name": floor.get(
                "name",
                "Jezero Crater",
            ),
            "profile": floor,
        })

    sites.append({
        "location_id": RIM_ID,
        "name": rim.get(
            "name",
            "Jezero Western Rim",
        ),
        "profile": rim,
    })

    database = {
        "planet": "mars",
        "sites": sites,

        "scientific_categories": [
            "terrain",
            "geology",
            "minerals",
            "thermal",
            "wind",
            "albedo",
        ],

        "excluded_categories": [
            "dust",
        ],

        "notes": (
            "Crater floor and western rim are distinct "
            "terrain sites. MACDA wind is nearby modeled "
            "context; thermal inertia and NIR albedo are "
            "coarser satellite context. Only compatible "
            "terrain metrics are used for default Earth "
            "similarity ranking."
        ),
    }

    save_json(
        OUTPUT / "jezero_sites.json",
        database,
    )

    print("\n=== FINAL RESULTS ===")

    for site in sites:
        profile = site["profile"]

        print(f"\n{site['location_id']}")

        print(
            "Categories:",
            ["terrain"] + list(
                profile.get("modules", {})
            ),
        )

        print(
            "Missing:",
            profile.get("missing_modules", []),
        )

        print(
            "Invalid:",
            profile.get("invalid_modules", []),
        )

    print("\nJezero assembly complete.")


if __name__ == "__main__":
    main()
