# """Add NASA MERRA-2 monthly wind and surface-pressure data to Earth candidates.

# Place this script in: prep/earth_atmosphere.py
# Place the CSV in:   data/earth_eligible_locations.csv
# Place 2025 monthly MERRA-2 .nc4 files directly in: raw_data/

# Run from the repository root:
#     py prep/earth_atmosphere.py

# Creates: data/earth_locations_atmosphere.csv
# The original candidate CSV is not modified.

# MERRA-2 collection: M2TMNXSLV (monthly mean single-level diagnostics).
# Uses U10M, V10M (m/s) and PS (Pa) at the closest MERRA-2 grid point.
# The resultant wind-vector strength is NOT mean hourly wind speed.
# """

# import calendar
# import csv
# import math
# import re
# from pathlib import Path

# import numpy as np
# import xarray as xr


# ROOT = Path(__file__).resolve().parent.parent
# INPUT_CSV = ROOT / "data" / "earth_eligible_locations.csv"
# RAW_DIR = ROOT / "raw_data"
# OUTPUT_CSV = ROOT / "data" / "earth_locations_atmosphere.csv"
# YEAR = 2025

# NEW_COLUMNS = [
#     "mean_u_ms",
#     "mean_v_ms",
#     "mean_wind_vector_strength_ms",
#     "prevailing_wind_direction_deg",
#     "mean_surface_pressure_pa",
#     "atmosphere_grid_lat",
#     "atmosphere_grid_lon",
#     "valid_wind_months",
#     "valid_pressure_months",
# ]


# def find_monthly_files():
#     """Find exactly one MERRA-2 monthly single-level file for each month."""
#     if not RAW_DIR.is_dir():
#         raise FileNotFoundError(f"Missing data directory: {RAW_DIR}")

#     monthly_files = {}
#     # Also supports customized names such as ...202501.SUB.nc4.
#     regex = re.compile(r"tavgM_2d_slv_Nx\.(\d{6})(?=\.|$)")

#     for path in RAW_DIR.iterdir():
#         if not path.is_file() or path.suffix.lower() not in {".nc", ".nc4"}:
#             continue
#         match = regex.search(path.name)
#         if not match or not match.group(1).startswith(str(YEAR)):
#             continue
#         month = int(match.group(1)[4:])
#         if not 1 <= month <= 12:
#             continue
#         if month in monthly_files:
#             raise ValueError(
#                 f"More than one MERRA-2 file for {YEAR}-{month:02d}:\n"
#                 f"  {monthly_files[month].name}\n  {path.name}\n"
#                 "Keep only one version of each monthly file in raw_data/."
#             )
#         monthly_files[month] = path

#     missing = [f"{YEAR}-{month:02d}" for month in range(1, 13)
#                if month not in monthly_files]
#     if missing:
#         raise FileNotFoundError(
#             "Missing MERRA-2 monthly files for: " + ", ".join(missing)
#             + "\nExpected filenames similar to "
#             + f"MERRA2_400.tavgM_2d_slv_Nx.{YEAR}01.nc4 "
#             + "directly inside raw_data/."
#         )
#     return monthly_files


# def read_candidates():
#     if not INPUT_CSV.is_file():
#         raise FileNotFoundError(
#             f"Missing {INPUT_CSV}\n"
#             "Place earth_eligible_locations.csv inside the repository's data/ folder."
#         )
#     with INPUT_CSV.open("r", newline="", encoding="utf-8-sig") as file:
#         reader = csv.DictReader(file)
#         columns = list(reader.fieldnames or [])
#         required = {"id", "lat", "lon"}
#         if not required.issubset(columns):
#             raise ValueError(f"CSV is missing columns: {sorted(required - set(columns))}")
#         rows = list(reader)

#     if not rows:
#         raise ValueError("The candidate CSV has no rows.")

#     lat = np.array([float(row["lat"]) for row in rows], dtype=float)
#     lon = np.array([float(row["lon"]) for row in rows], dtype=float)
#     if (not np.isfinite(lat).all() or not np.isfinite(lon).all()
#             or np.any((lat < -90) | (lat > 90))):
#         raise ValueError("The candidate CSV contains invalid latitude/longitude values.")

#     return columns, rows, lat, lon


# def nearest_indices(grid, requested, cyclic=False):
#     """Efficient nearest-grid lookup for many points, including longitude wrap."""
#     answer = np.empty(requested.size, dtype=np.int32)
#     for start in range(0, requested.size, 1500):
#         end = min(start + 1500, requested.size)
#         differences = grid[:, None] - requested[None, start:end]
#         if cyclic:
#             differences = (differences + 180.0) % 360.0 - 180.0
#         answer[start:end] = np.abs(differences).argmin(axis=0)
#     return answer


# def load_month_field(dataset, name, lat_idx, lon_idx):
#     if name not in dataset:
#         raise ValueError(
#             f"Variable {name} is missing from the monthly file. "
#             f"Found: {list(dataset.data_vars)}\n"
#             "Download U10M, V10M and PS."
#         )
#     field = dataset[name]
#     if "time" in field.dims:
#         if field.sizes["time"] != 1:
#             raise ValueError(f"Expected one monthly time step for {name}.")
#         field = field.isel(time=0, drop=True)
#     field = field.transpose("lat", "lon")
#     # Select only the requested coordinate indices, avoiding a huge merged dataset.
#     values = np.asarray(field.values[lat_idx, lon_idx], dtype=float)
#     values[~np.isfinite(values) | (np.abs(values) > 1e10)] = np.nan
#     return values


# def format_number(value):
#     return f"{value:.6f}" if math.isfinite(float(value)) else ""


# def main():
#     columns, rows, latitudes, longitudes = read_candidates()
#     files = find_monthly_files()
#     count = len(rows)

#     # Separate weighting for wind and pressure in case some values are missing.
#     total_u = np.zeros(count, dtype=float)
#     total_v = np.zeros(count, dtype=float)
#     wind_days = np.zeros(count, dtype=float)
#     wind_months = np.zeros(count, dtype=np.int16)
#     total_pressure = np.zeros(count, dtype=float)
#     pressure_days = np.zeros(count, dtype=float)
#     pressure_months = np.zeros(count, dtype=np.int16)

#     model_lat = None
#     model_lon = None
#     grid_lat = None
#     grid_lon = None
#     lat_idx = None
#     lon_idx = None

#     for month in range(1, 13):
#         path = files[month]
#         days = calendar.monthrange(YEAR, month)[1]

#         with xr.open_dataset(path) as ds:
#             if "lat" not in ds.coords or "lon" not in ds.coords:
#                 raise ValueError(f"Missing lat/lon coordinates in {path.name}")
#             current_lat = np.asarray(ds["lat"].values, dtype=float)
#             current_lon = np.asarray(ds["lon"].values, dtype=float)

#             if lat_idx is None:
#                 lat_idx = nearest_indices(current_lat, latitudes)
#                 lon_idx = nearest_indices(current_lon, longitudes, cyclic=True)
#                 grid_lat, grid_lon = current_lat, current_lon
#                 model_lat = grid_lat[lat_idx]
#                 model_lon = grid_lon[lon_idx]

#                 # Do not silently match a distant point if files were cropped
#                 # to a geographic area smaller than the candidate catalog.
#                 latitude_error = np.abs(model_lat - latitudes)
#                 longitude_error = np.abs(
#                     (model_lon - longitudes + 180.0) % 360.0 - 180.0
#                 )
#                 if (np.any(latitude_error > 0.51)
#                         or np.any(longitude_error > 0.64)):
#                     raise ValueError(
#                         "Some candidate locations are outside the downloaded MERRA-2 "
#                         "geographic coverage. Download GLOBAL monthly files (or "
#                         "files covering every region in your CSV)."
#                     )
#             elif (not np.array_equal(grid_lat, current_lat)
#                   or not np.array_equal(grid_lon, current_lon)):
#                 raise ValueError(
#                     f"Grid coordinates differ in {path.name}; "
#                     "monthly files must have matching geographic coverage."
#                 )

#             u = load_month_field(ds, "U10M", lat_idx, lon_idx)
#             v = load_month_field(ds, "V10M", lat_idx, lon_idx)
#             pressure = load_month_field(ds, "PS", lat_idx, lon_idx)

#         valid_wind = np.isfinite(u) & np.isfinite(v)
#         total_u[valid_wind] += u[valid_wind] * days
#         total_v[valid_wind] += v[valid_wind] * days
#         wind_days[valid_wind] += days
#         wind_months[valid_wind] += 1

#         valid_pressure = np.isfinite(pressure)
#         total_pressure[valid_pressure] += pressure[valid_pressure] * days
#         pressure_days[valid_pressure] += days
#         pressure_months[valid_pressure] += 1

#         print(f"Read {month:02d}/12: {path.name}")

#     # Annual weighted average of monthly mean components and pressure.
#     mean_u = np.divide(total_u, wind_days, out=np.full(count, np.nan),
#                        where=wind_days > 0)
#     mean_v = np.divide(total_v, wind_days, out=np.full(count, np.nan),
#                        where=wind_days > 0)
#     mean_pressure = np.divide(
#         total_pressure, pressure_days,
#         out=np.full(count, np.nan), where=pressure_days > 0
#     )

#     resultant = np.hypot(mean_u, mean_v)
#     # Meteorological direction: where wind COMES FROM, clockwise from north.
#     direction = (270.0 - np.degrees(np.arctan2(mean_v, mean_u))) % 360.0
#     direction[(resultant < 1e-10) | ~np.isfinite(resultant)] = np.nan

#     # Keep all original columns and rows; append atmospheric fields only.
#     out_columns = columns + [name for name in NEW_COLUMNS if name not in columns]
#     OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
#     with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as file:
#         writer = csv.DictWriter(file, fieldnames=out_columns)
#         writer.writeheader()
#         for i, row in enumerate(rows):
#             row.update({
#                 "mean_u_ms": format_number(mean_u[i]),
#                 "mean_v_ms": format_number(mean_v[i]),
#                 "mean_wind_vector_strength_ms": format_number(resultant[i]),
#                 "prevailing_wind_direction_deg": format_number(direction[i]),
#                 "mean_surface_pressure_pa": format_number(mean_pressure[i]),
#                 "atmosphere_grid_lat": format_number(model_lat[i]),
#                 "atmosphere_grid_lon": format_number(model_lon[i]),
#                 "valid_wind_months": int(wind_months[i]),
#                 "valid_pressure_months": int(pressure_months[i]),
#             })
#             writer.writerow(row)

#     print(f"\nProcessed {count:,} eligible Earth locations.")
#     print(f"Wind data for {int(np.sum(wind_months == 12)):,} cells in all 12 months.")
#     print(f"Pressure data for {int(np.sum(pressure_months == 12)):,} cells in all 12 months.")
#     print(f"Saved: {OUTPUT_CSV}")
#     print("NOTE: Resultant wind-vector strength is not mean hourly wind speed.")


# if __name__ == "__main__":
#     main()
