"""Extract wind and surface pressure at five Mars sites from local MACDA NetCDF files.

Run from the repository root:
    python prep/mars_atmosphere.py

Reads raw_data/mgs-tes-reanalysis_mars_*.nc and writes six JSON files
into data/. No downloads; location coordinates are defined below.
"""

import argparse
import json
import math
import re
from pathlib import Path

import numpy as np
import xarray as xr


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "raw_data"
DEFAULT_OUTPUT = REPO_ROOT / "data"

# Approximate reference coordinates, not exact 10 x 10 km region centers.
MARS_SITES = [
    {"id": "jezero_crater", "name": "Jezero Crater", "lat": 18.4, "lon": 77.5},
    {"id": "gale_crater", "name": "Gale Crater", "lat": -5.4, "lon": 137.8},
    {"id": "nili_patera", "name": "Nili Patera", "lat": 8.8, "lon": 67.3},
    {"id": "athabasca_valles", "name": "Athabasca Valles", "lat": 9.0, "lon": 155.0},
    {"id": "victoria_crater", "name": "Victoria Crater", "lat": -2.1, "lon": -5.5},
]


def _finite_or_none(value):
    number = float(value)
    return number if math.isfinite(number) and abs(number) < 1e20 else None


def _clean_1d(values):
    """Return a writable, 1-D float array with missing values set to NaN."""
    masked = np.ma.asarray(values, dtype=np.float64)
    # CRITICAL FIX: NetCDF/xarray sometimes returns read-only arrays.
    arr = np.array(np.ma.filled(masked, np.nan), dtype=np.float64, copy=True)
    arr = arr.reshape(-1)
    arr[~np.isfinite(arr) | (np.abs(arr) >= 1e20)] = np.nan
    return arr


def _nearest_grid_coordinate(latitudes, longitudes, lat, lon):
    lat_idx = int(np.nanargmin(np.abs(latitudes - lat)))
    # Handle both -180..180 and 0..360 longitude conventions.
    lon_diffs = (longitudes - lon + 180.0) % 360.0 - 180.0
    lon_idx = int(np.nanargmin(np.abs(lon_diffs)))
    return lat_idx, lon_idx


def _mars_distance_km(lat_a, lon_a, lat_b, lon_b):
    lat_a, lat_b = math.radians(lat_a), math.radians(lat_b)
    dlat = lat_b - lat_a
    dlon = math.radians(((lon_b - lon_a + 180) % 360) - 180)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(dlon / 2) ** 2
    )
    return 3389.5 * 2 * math.asin(min(1, math.sqrt(a)))


def wind_from_direction(u, v):
    """Meteorological direction (degrees clockwise from north, wind FROM)."""
    if math.hypot(u, v) < 1e-10:
        return None
    return (270.0 - math.degrees(math.atan2(v, u))) % 360.0


def summarize(samples):
    valid_wind = [s for s in samples if s["wind_speed_ms"] is not None]
    valid_pressure = [
        s["surface_pressure_pa"]
        for s in samples
        if s["surface_pressure_pa"] is not None
    ]
    speeds = np.array([s["wind_speed_ms"] for s in valid_wind], dtype=float)

    direction = None
    if valid_wind:
        mean_u = float(np.mean([s["u_ms"] for s in valid_wind]))
        mean_v = float(np.mean([s["v_ms"] for s in valid_wind]))
        direction = wind_from_direction(mean_u, mean_v)

    return {
        "sample_count": len(samples),
        "valid_wind_samples": len(valid_wind),
        "valid_pressure_samples": len(valid_pressure),
        "mean_wind_speed_ms": float(np.mean(speeds)) if len(speeds) else None,
        "p95_wind_speed_ms": float(np.percentile(speeds, 95)) if len(speeds) else None,
        "wind_speed_std_ms": float(np.std(speeds)) if len(speeds) else None,
        "prevailing_wind_direction_deg": direction,
        "mean_surface_pressure_pa": (
            float(np.mean(valid_pressure)) if valid_pressure else None
        ),
    }


def _period_from_name(filename):
    match = re.search(r"MY(\d+)SOY(\d+)_MY(\d+)SOY(\d+)", filename)
    if match is None:
        return {}
    return {
        "start_mars_year": int(match[1]),
        "start_sol_of_year": int(match[2]),
        "end_mars_year": int(match[3]),
        "end_sol_of_year": int(match[4]),
    }


def process_file(path, sites, results):
    # Retain the nonstandard Martian calendar numeric time coordinate.
    with xr.open_dataset(path, decode_times=False) as ds:
        required = ["lat", "lon", "lev", "time", "uwind", "vwind", "psurf", "Ls"]
        missing = [name for name in required if name not in ds.variables]
        if missing:
            raise ValueError(f"{path.name}: missing variables: {missing}")

        latitudes = _clean_1d(ds["lat"].values)
        longitudes = _clean_1d(ds["lon"].values)
        sigma_levels = _clean_1d(ds["lev"].values)
        surface_level_idx = int(np.nanargmin(np.abs(sigma_levels - 1.0)))
        times = _clean_1d(ds["time"].values)
        ls_values = _clean_1d(ds["Ls"].values)
        period_index = len(results[sites[0]["id"]]["periods"])

        for site in sites:
            lat_idx, lon_idx = _nearest_grid_coordinate(
                latitudes, longitudes, site["lat"], site["lon"]
            )
            selection = {"lat": lat_idx, "lon": lon_idx}

            # Read only the selected location/time series (not the entire dataset).
            u = _clean_1d(
                ds["uwind"].isel(**selection, lev=surface_level_idx).values
            )
            v = _clean_1d(
                ds["vwind"].isel(**selection, lev=surface_level_idx).values
            )
            p = _clean_1d(ds["psurf"].isel(**selection).values)

            if not len(u) == len(v) == len(p) == len(times) == len(ls_values):
                raise ValueError(f"{path.name}: inconsistent time dimensions")

            samples = []
            for t, ls, uu, vv, pp in zip(times, ls_values, u, v, p):
                u_value = _finite_or_none(uu)
                v_value = _finite_or_none(vv)
                p_value = _finite_or_none(pp)
                if u_value is not None and v_value is not None:
                    speed = math.hypot(u_value, v_value)
                    direction = wind_from_direction(u_value, v_value)
                else:
                    speed = None
                    direction = None

                samples.append(
                    {
                        "period_index": period_index,
                        "model_time_days": _finite_or_none(t),
                        "ls_deg": _finite_or_none(ls),
                        "u_ms": u_value,
                        "v_ms": v_value,
                        "wind_speed_ms": speed,
                        "wind_direction_from_deg": direction,
                        "surface_pressure_pa": p_value,
                    }
                )

            grid_lat = float(latitudes[lat_idx])
            grid_lon = float(longitudes[lon_idx])
            period_info = {
                "source_file": path.name,
                **_period_from_name(path.name),
                "wind_level_index": surface_level_idx,
                "wind_level_sigma": float(sigma_levels[surface_level_idx]),
                "model_grid_lat": grid_lat,
                "model_grid_lon": grid_lon,
                "grid_distance_km": round(
                    _mars_distance_km(
                        site["lat"], site["lon"], grid_lat, grid_lon
                    ),
                    2,
                ),
                "ls_start_deg": _finite_or_none(ls_values[0]),
                "ls_end_deg": _finite_or_none(ls_values[-1]),
                "summary": summarize(samples),
            }
            results[site["id"]]["periods"].append(period_info)
            results[site["id"]]["samples"].extend(samples)
            print(
                f"  {site['name']}: {len(samples)} samples "
                f"at grid ({grid_lat:.1f}, {grid_lon:.1f})"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Extract MACDA wind and pressure for five Mars locations"
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--pattern", default="mgs-tes-reanalysis_mars_*.nc")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    files = sorted(args.input_dir.glob(args.pattern))
    if not files:
        raise SystemExit(
            f"No matching .nc files in {args.input_dir} "
            f"(pattern: {args.pattern})"
        )

    results = {}
    for site in MARS_SITES:
        results[site["id"]] = {
            "schema_version": "1.0",
            "planet": "mars",
            "id": site["id"],
            "name": site["name"],
            "lat": site["lat"],
            "lon": site["lon"],
            "coordinate_source": "hardcoded_project_reference",
            "coordinate_quality": "approximate_reference",
            "source_dataset": "MACDA v2.0",
            "data_type": "modeled atmospheric reanalysis",
            "data_status": "processed",
            "wind_height_note": (
                "Lowest model sigma level; not necessarily 10 m above ground"
            ),
            "sampling_note": (
                "Selected 30-sol windows only; not a full Martian annual climatology"
            ),
            "periods": [],
            "samples": [],
        }

    for file in files:
        print(f"Processing {file.name}...")
        process_file(file, MARS_SITES, results)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    index = {
        "schema_version": "1.0",
        "planet": "mars",
        "source_dataset": "MACDA v2.0",
        "sites": [],
    }

    for site in MARS_SITES:
        doc = results[site["id"]]
        # Use every extracted sample for the overall statistics first.
        doc["summary"] = summarize(doc["samples"])
        # Keep only site and period summaries in the JSON, not raw time samples.
        del doc["samples"]
        filename = re.sub(r"[^A-Za-z0-9_-]+", "_", site["id"]).strip("_") + ".json"
        out_path = args.output_dir / filename
        with out_path.open("w", encoding="utf-8") as handle:
            json.dump(doc, handle, indent=2, allow_nan=False)
        index["sites"].append(
            {
                "id": site["id"],
                "name": site["name"],
                "path": filename,
                "summary": doc["summary"],
            }
        )
        print(f"Saved: {out_path} ({doc['summary']['sample_count']} samples)")

    with (args.output_dir / "index.json").open("w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2, allow_nan=False)
    print("Done. Check the JSON results before deleting any source .nc files.")


if __name__ == "__main__":
    main()
