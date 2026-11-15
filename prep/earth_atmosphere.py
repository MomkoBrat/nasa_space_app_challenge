"""Append NASA MERRA-2 2025 monthly wind and pressure fields to Earth cells.

Save as: prep/earth_atmosphere.py
Input:   data/earth_eligible_locations.csv
         raw_data/MERRA2_400.tavgM_2d_slv_Nx.2025MM.nc4 (12 files)
         raw_data/MERRA2_400.tavgM_2d_flx_Nx.2025MM.nc4 (12 files)
Output:  data/earth_locations_atmosphere.csv
Run:     py prep/earth_atmosphere.py

M2TMNXSLV supplies U10M/V10M (10 m wind components) and PS (pressure).
M2TMNXFLX supplies SPEED (mean wind speed at the lowest model layer,
not necessarily 10 m). All fields are matched by nearest grid point.
Monthly values are weighted by days in each month. The original CSV is
not modified. This cannot reconstruct hourly P95 or hourly variability.
"""

import calendar
import csv
import math
import re
from pathlib import Path

import numpy as np
import xarray as xr


ROOT = Path(__file__).resolve().parent.parent
INPUT_CSV = ROOT / "data" / "earth_eligible_locations.csv"
RAW_DIR = ROOT / "raw_data"
OUTPUT_CSV = ROOT / "data" / "earth_locations_atmosphere.csv"
YEAR = 2025

NEW_COLUMNS = [
    "mean_wind_speed_ms",
    "mean_u_ms",
    "mean_v_ms",
    "mean_wind_vector_strength_ms",
    "prevailing_wind_direction_deg",
    "mean_surface_pressure_pa",
    "atmosphere_grid_lat",
    "atmosphere_grid_lon",
    "valid_wind_months",
    "valid_speed_months",
    "valid_pressure_months",
]


def find_monthly_files(collection):
    """Find precisely one file per month for an MERRA-2 monthly collection."""
    if not RAW_DIR.is_dir():
        raise FileNotFoundError(f"Missing data directory: {RAW_DIR}")

    monthly_files = {}
    # Accept standard names and NASA-customized files such as YYYYMM.SUB.nc4.
    regex = re.compile(rf"tavgM_2d_{collection}_Nx\.(\d{{6}})(?=\.|$)")

    for path in RAW_DIR.iterdir():
        if not path.is_file() or path.suffix.lower() not in {".nc", ".nc4"}:
            continue
        match = regex.search(path.name)
        if not match or not match.group(1).startswith(str(YEAR)):
            continue
        month = int(match.group(1)[4:])
        if not 1 <= month <= 12:
            continue
        if month in monthly_files:
            raise ValueError(
                f"More than one {collection} file for {YEAR}-{month:02d}:\n"
                f"  {monthly_files[month].name}\n  {path.name}\n"
                "Keep only one version of each monthly file in raw_data/."
            )
        monthly_files[month] = path

    missing = [f"{YEAR}-{month:02d}" for month in range(1, 13)
               if month not in monthly_files]
    if missing:
        raise FileNotFoundError(
            f"Missing {collection.upper()} MERRA-2 monthly files for: "
            + ", ".join(missing)
            + "\nExpected filenames like "
            + f"MERRA2_400.tavgM_2d_{collection}_Nx.{YEAR}01.nc4 "
            + "directly inside raw_data/."
        )
    return monthly_files


def read_candidates():
    """Load cell coordinates, accepting common latitude/longitude header names."""
    if not INPUT_CSV.is_file():
        raise FileNotFoundError(
            f"Missing {INPUT_CSV}\n"
            "Place earth_eligible_locations.csv inside the repository's data/ folder."
        )

    with INPUT_CSV.open("r", newline="", encoding="utf-8-sig") as file:
        sample = file.read(8192)
        file.seek(0)
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
        except csv.Error:
            delimiter = ","
        reader = csv.DictReader(file, delimiter=delimiter)
        columns = list(reader.fieldnames or [])
        if not columns:
            raise ValueError(f"CSV has no header: {INPUT_CSV}")

        # Keep the original header and all original columns in the output.
        # Only normalize names to identify the coordinate columns.
        normalized = {
            str(name).strip().lower().replace(" ", "_").replace("-", "_"): name
            for name in columns
        }

        def find_column(aliases):
            for alias in aliases:
                if alias in normalized:
                    return normalized[alias]
            return None

        latitude_column = find_column((
            "lat", "latitude", "center_lat", "centre_lat", "lat_center",
            "latitude_center", "center_latitude", "centroid_lat",
            "latitude_deg", "lat_deg", "cell_lat", "cell_center_lat",
        ))
        longitude_column = find_column((
            "lon", "lng", "long", "longitude", "center_lon", "centre_lon",
            "lon_center", "longitude_center", "center_longitude",
            "centroid_lon", "longitude_deg", "lon_deg", "cell_lon",
            "cell_center_lon", "center_lng",
        ))
        if latitude_column is None or longitude_column is None:
            raise ValueError(
                f"Could not identify latitude/longitude columns in {INPUT_CSV.name}.\n"
                f"Actual columns: {columns}\n"
                "Expected e.g. lat/lon, latitude/longitude, or center_lat/center_lon.\n"
                "The script needs one latitude and one longitude per Earth cell."
            )

        rows = list(reader)

    if not rows:
        raise ValueError("The candidate CSV has no rows.")

    def read_coordinate(row, column, row_number):
        try:
            return float(str(row[column]).strip().replace(",", "."))
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Invalid {column!r} value on CSV row {row_number}: {row.get(column)!r}"
            ) from exc

    lat = np.array([
        read_coordinate(row, latitude_column, i + 2)
        for i, row in enumerate(rows)
    ], dtype=float)
    lon = np.array([
        read_coordinate(row, longitude_column, i + 2)
        for i, row in enumerate(rows)
    ], dtype=float)
    if (not np.isfinite(lat).all() or not np.isfinite(lon).all()
            or np.any((lat < -90) | (lat > 90))
            or np.any((lon < -180) | (lon > 360))):
        raise ValueError("The candidate CSV contains invalid latitude/longitude values.")

    print(f"Reading {len(rows):,} Earth cells from {INPUT_CSV.name}.")
    print(f"Coordinate columns: {latitude_column!r}, {longitude_column!r}")
    return columns, rows, lat, lon


def nearest_indices(grid, requested, cyclic=False):
    """Efficient nearest-grid lookup for many points, including longitude wrap."""
    answer = np.empty(requested.size, dtype=np.int32)
    for start in range(0, requested.size, 1500):
        end = min(start + 1500, requested.size)
        differences = grid[:, None] - requested[None, start:end]
        if cyclic:
            differences = (differences + 180.0) % 360.0 - 180.0
        answer[start:end] = np.abs(differences).argmin(axis=0)
    return answer


def load_month_field(dataset, name, lat_idx, lon_idx):
    if name not in dataset:
        raise ValueError(
            f"Variable {name} is missing from the monthly file. "
            f"Found: {list(dataset.data_vars)}\n"
            "Download U10M, V10M and PS."
        )
    field = dataset[name]
    if "time" in field.dims:
        if field.sizes["time"] != 1:
            raise ValueError(f"Expected one monthly time step for {name}.")
        field = field.isel(time=0, drop=True)
    field = field.transpose("lat", "lon")
    # Select only the requested coordinate indices, avoiding a huge merged dataset.
    values = np.asarray(field.values[lat_idx, lon_idx], dtype=float)
    values[~np.isfinite(values) | (np.abs(values) > 1e10)] = np.nan
    return values


def format_number(value):
    return f"{value:.6f}" if math.isfinite(float(value)) else ""


def main():
    columns, rows, latitudes, longitudes = read_candidates()
    slv_files = find_monthly_files("slv")
    flx_files = find_monthly_files("flx")
    count = len(rows)

    # Separate weighting for wind and pressure in case some values are missing.
    total_u = np.zeros(count, dtype=float)
    total_v = np.zeros(count, dtype=float)
    wind_days = np.zeros(count, dtype=float)
    wind_months = np.zeros(count, dtype=np.int16)
    total_speed = np.zeros(count, dtype=float)
    speed_days = np.zeros(count, dtype=float)
    speed_months = np.zeros(count, dtype=np.int16)
    total_pressure = np.zeros(count, dtype=float)
    pressure_days = np.zeros(count, dtype=float)
    pressure_months = np.zeros(count, dtype=np.int16)

    model_lat = None
    model_lon = None
    grid_lat = None
    grid_lon = None
    lat_idx = None
    lon_idx = None

    for month in range(1, 13):
        slv_path = slv_files[month]
        flx_path = flx_files[month]
        days = calendar.monthrange(YEAR, month)[1]

        with xr.open_dataset(slv_path) as ds:
            if "lat" not in ds.coords or "lon" not in ds.coords:
                raise ValueError(f"Missing lat/lon coordinates in {slv_path.name}")
            current_lat = np.asarray(ds["lat"].values, dtype=float)
            current_lon = np.asarray(ds["lon"].values, dtype=float)

            if lat_idx is None:
                lat_idx = nearest_indices(current_lat, latitudes)
                lon_idx = nearest_indices(current_lon, longitudes, cyclic=True)
                grid_lat, grid_lon = current_lat, current_lon
                model_lat = grid_lat[lat_idx]
                model_lon = grid_lon[lon_idx]

                # Do not silently match a distant point if files were cropped
                # to a geographic area smaller than the candidate catalog.
                latitude_error = np.abs(model_lat - latitudes)
                longitude_error = np.abs(
                    (model_lon - longitudes + 180.0) % 360.0 - 180.0
                )
                if (np.any(latitude_error > 0.51)
                        or np.any(longitude_error > 0.64)):
                    raise ValueError(
                        "Some candidate locations are outside the downloaded MERRA-2 "
                        "geographic coverage. Download GLOBAL monthly files (or "
                        "files covering every region in your CSV)."
                    )
            elif (not np.array_equal(grid_lat, current_lat)
                  or not np.array_equal(grid_lon, current_lon)):
                raise ValueError(
                    f"Grid coordinates differ in {slv_path.name}; "
                    "monthly files must have matching geographic coverage."
                )

            u = load_month_field(ds, "U10M", lat_idx, lon_idx)
            v = load_month_field(ds, "V10M", lat_idx, lon_idx)
            pressure = load_month_field(ds, "PS", lat_idx, lon_idx)

        with xr.open_dataset(flx_path) as ds:
            if "lat" not in ds.coords or "lon" not in ds.coords:
                raise ValueError(f"Missing lat/lon coordinates in {flx_path.name}")
            if (not np.array_equal(grid_lat, np.asarray(ds["lat"].values, dtype=float))
                    or not np.array_equal(grid_lon, np.asarray(ds["lon"].values, dtype=float))):
                raise ValueError(
                    f"Grid coordinates differ in {flx_path.name}; "
                    "FLX and SLV files must use the same geographic grid."
                )
            speed = load_month_field(ds, "SPEED", lat_idx, lon_idx)

        valid_speed = np.isfinite(speed) & (speed >= 0)
        total_speed[valid_speed] += speed[valid_speed] * days
        speed_days[valid_speed] += days
        speed_months[valid_speed] += 1

        valid_wind = np.isfinite(u) & np.isfinite(v)
        total_u[valid_wind] += u[valid_wind] * days
        total_v[valid_wind] += v[valid_wind] * days
        wind_days[valid_wind] += days
        wind_months[valid_wind] += 1

        valid_pressure = np.isfinite(pressure)
        total_pressure[valid_pressure] += pressure[valid_pressure] * days
        pressure_days[valid_pressure] += days
        pressure_months[valid_pressure] += 1

        print(f"Read {month:02d}/12: {slv_path.name} + {flx_path.name}")

    # Annual weighted average of monthly mean components and pressure.
    mean_u = np.divide(total_u, wind_days, out=np.full(count, np.nan),
                       where=wind_days > 0)
    mean_v = np.divide(total_v, wind_days, out=np.full(count, np.nan),
                       where=wind_days > 0)
    mean_pressure = np.divide(
        total_pressure, pressure_days,
        out=np.full(count, np.nan), where=pressure_days > 0
    )
    mean_speed = np.divide(
        total_speed, speed_days,
        out=np.full(count, np.nan), where=speed_days > 0
    )

    resultant = np.hypot(mean_u, mean_v)
    # Meteorological direction: where wind COMES FROM, clockwise from north.
    direction = (270.0 - np.degrees(np.arctan2(mean_v, mean_u))) % 360.0
    direction[(resultant < 1e-10) | ~np.isfinite(resultant)] = np.nan

    # Keep all original columns and rows; append atmospheric fields only.
    out_columns = columns + [name for name in NEW_COLUMNS if name not in columns]
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=out_columns)
        writer.writeheader()
        for i, row in enumerate(rows):
            row.update({
                "mean_wind_speed_ms": format_number(mean_speed[i]),
                "mean_u_ms": format_number(mean_u[i]),
                "mean_v_ms": format_number(mean_v[i]),
                "mean_wind_vector_strength_ms": format_number(resultant[i]),
                "prevailing_wind_direction_deg": format_number(direction[i]),
                "mean_surface_pressure_pa": format_number(mean_pressure[i]),
                "atmosphere_grid_lat": format_number(model_lat[i]),
                "atmosphere_grid_lon": format_number(model_lon[i]),
                "valid_wind_months": int(wind_months[i]),
                "valid_speed_months": int(speed_months[i]),
                "valid_pressure_months": int(pressure_months[i]),
            })
            writer.writerow(row)

    print(f"\nProcessed {count:,} Earth locations.")
    print(f"10 m wind components for {int(np.sum(wind_months == 12)):,} cells in all 12 months.")
    print(f"Mean wind speed for {int(np.sum(speed_months == 12)):,} cells in all 12 months.")
    print(f"Pressure data for {int(np.sum(pressure_months == 12)):,} cells in all 12 months.")
    print(f"Saved: {OUTPUT_CSV}")
    print("NOTE: mean_wind_speed_ms comes from FLX SPEED (lowest model layer).")
    print("      Wind direction comes from SLV U10M/V10M (10 m level).")


if __name__ == "__main__":
    main()
