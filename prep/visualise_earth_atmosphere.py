
# from pathlib import Path

# import numpy as np
# import xarray as xr
# import matplotlib.pyplot as plt


# # Project paths
# ROOT = Path(__file__).resolve().parent.parent

# INPUT_FILE = (
#     ROOT
#     / "raw_data"
#     / "MERRA2_400.tavgM_2d_slv_Nx.202501.nc4"
# )

# OUTPUT_DIR = ROOT / "data" / "atmosphere"
# OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# # Read NASA MERRA-2 data
# with xr.open_dataset(INPUT_FILE) as ds:
#     print("Dataset information:")
#     print(ds)

#     print("\nAvailable variables:")
#     print(list(ds.data_vars))

#     required = ["U10M", "V10M", "PS"]
#     missing = [name for name in required if name not in ds]

#     if missing:
#         raise ValueError(
#             f"Missing variables: {missing}\n"
#             f"Available variables: {list(ds.data_vars)}"
#         )

#     # Each monthly file contains a monthly mean time step
#     u = ds["U10M"].isel(time=0).transpose("lat", "lon").load()
#     v = ds["V10M"].isel(time=0).transpose("lat", "lon").load()
#     pressure = ds["PS"].isel(time=0).transpose("lat", "lon").load()

#     lat = ds["lat"].values
#     lon = ds["lon"].values


# # Clean missing / invalid values
# def clean(values):
#     arr = np.array(values, dtype=float, copy=True)
#     arr[~np.isfinite(arr) | (np.abs(arr) > 1e10)] = np.nan
#     return arr


# u = clean(u.values)
# v = clean(v.values)
# pressure_pa = clean(pressure.values)

# # Convert Pa to hPa for easier visualization
# pressure_hpa = pressure_pa / 100.0

# # Magnitude of the monthly mean wind vector
# wind_vector_speed = np.hypot(u, v)


# # --------------------------------------------------
# # MAP 1: Surface Atmospheric Pressure
# # --------------------------------------------------
# fig, ax = plt.subplots(figsize=(14, 6))

# plot = ax.pcolormesh(
#     lon,
#     lat,
#     pressure_hpa,
#     shading="auto",
#     cmap="viridis"
# )

# fig.colorbar(
#     plot,
#     ax=ax,
#     label="Surface pressure (hPa)"
# )

# ax.set_title("NASA MERRA-2 | Surface Pressure | January 2025")
# ax.set_xlabel("Longitude (degrees)")
# ax.set_ylabel("Latitude (degrees)")
# ax.set_xlim(-180, 180)
# ax.set_ylim(-90, 90)
# ax.grid(alpha=0.2)

# fig.tight_layout()

# pressure_path = OUTPUT_DIR / "earth_surface_pressure_202501.png"
# fig.savefig(pressure_path, dpi=200)

# print(f"\nSaved: {pressure_path}")


# # --------------------------------------------------
# # MAP 2: Near-Surface Wind
# # --------------------------------------------------
# fig, ax = plt.subplots(figsize=(14, 6))

# plot = ax.pcolormesh(
#     lon,
#     lat,
#     wind_vector_speed,
#     shading="auto",
#     cmap="plasma"
# )

# fig.colorbar(
#     plot,
#     ax=ax,
#     label="Monthly mean wind vector magnitude (m/s)"
# )

# # Display fewer arrows to prevent overcrowding
# step = 24

# ax.quiver(
#     lon[::step],
#     lat[::step],
#     u[::step, ::step],
#     v[::step, ::step],
#     color="white",
#     scale=130,
#     width=0.002
# )

# ax.set_title("NASA MERRA-2 | 10 m Wind | January 2025")
# ax.set_xlabel("Longitude (degrees)")
# ax.set_ylabel("Latitude (degrees)")
# ax.set_xlim(-180, 180)
# ax.set_ylim(-90, 90)
# ax.grid(alpha=0.2)

# fig.tight_layout()

# wind_path = OUTPUT_DIR / "earth_wind_202501.png"
# fig.savefig(wind_path, dpi=200)

# print(f"Saved: {wind_path}")


# # Show both maps
# plt.show()
from pathlib import Path
import xarray as xr

ROOT = Path(__file__).resolve().parent.parent

file = ROOT / "raw_data" / "MERRA2_400.tavgM_2d_slv_Nx.202501.nc4"

with xr.open_dataset(file) as ds:
    print("Available variables:")
    print(sorted(ds.data_vars))

    print("\nSPEED available:", "SPEED" in ds.data_vars)