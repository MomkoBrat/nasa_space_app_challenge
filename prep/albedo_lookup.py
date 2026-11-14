#!/usr/bin/env python3
"""
Look up OMEGA/Mars Express NIR albedo (Ody et al. 2012) for a point or a
square window on Mars.

File needed (GeoTIFF):
  ALBEDO_R1080_EQU_MAP.tif   int16 scaled albedo (x10000), nodata -32768
                             shape 7200 x 14400, 40 ppd, ~1.48 km/pixel
                             simple cylindrical, planetocentric lat,
                             east-positive lon, row 0 = 90N, col 0 = 180W

IMPORTANT — scientific positioning (see project plan, section 6):
  Albedo is CONTEXTUAL INFORMATION ONLY.
  It does NOT enter the default similarity score.  Similar albedo does not
  mean similar composition, and OMEGA NIR is not the same spectral quantity
  as TES bolometric albedo or MODIS on Earth.

Usage:
  python albedo_lookup.py --tif ALBEDO_R1080_EQU_MAP.tif --lat 18.4 --lon 77.5 --size 10
  python albedo_lookup.py --tif ALBEDO_R1080_EQU_MAP.tif --lat 18.4 --lon 77.5 --size 10 --plot check.png
"""
import argparse
import math
import numpy as np
from pathlib import Path

# --- OMEGA albedo map constants (from the GeoTIFF transform) ---
RES = 40.0                    # pixels per degree  (14400 cols / 360 deg)
RADIUS_KM = 3396.0            # sphere radius (matches your TES file)
KM_PER_DEG = 2 * math.pi * RADIUS_KM / 360.0   # ~59.27 km per degree
NROWS, NCOLS = 7200, 14400
SCALE = 10000.0               # int16 value -> albedo (value / 10000)
NODATA = -32768
MIN_VALID_FRACTION = 0.5      # flag windows below this (same convention as ti_lookup)


def load_albedo(tif_path=Path(__file__).resolve().parent.parent / "data" / "ALBEDO_R1080_EQU_MAP.tiff"):
    """Return the albedo array as float32 with NoData set to NaN.

    Raw values are divided by SCALE so the returned array is physical albedo.
    """
    import rasterio
    with rasterio.open(tif_path) as src:
        raw = src.read(1).astype(np.float32)          # (7200, 14400) int16 -> float
        nodata = src.nodata if src.nodata is not None else NODATA
        # sanity checks: dims and orientation must match our constants
        if raw.shape != (NROWS, NCOLS):
            raise ValueError(f"Unexpected shape {raw.shape}, expected {(NROWS, NCOLS)}")
    albedo = raw / SCALE
    albedo[raw == nodata] = np.nan                    # exclude fill BEFORE scaling
    return albedo


def lat_to_row(lat):
    """Planetocentric latitude (deg) -> 0-based row index (clamped)."""
    return int(np.clip(math.floor((90.0 - lat) * RES), 0, NROWS - 1))


def lon_to_col(lon_east):
    """East longitude (any range, deg) -> 0-based column index (wraps)."""
    lon = ((lon_east + 180.0) % 360.0) - 180.0
    return int(math.floor((lon + 180.0) * RES)) % NCOLS


def window_stats(albedo, lat, lon_east, size_km=10.0,
                 min_valid_fraction=MIN_VALID_FRACTION):
    """Albedo statistics in a size_km x size_km window centred on a point.

    A pixel is valid if it is finite (i.e. not NoData).  Fill values are never
    counted as zero albedo.
    """
    half_km = size_km / 2.0
    lat_half = half_km / KM_PER_DEG
    coslat = max(math.cos(math.radians(lat)), 1e-3)
    lon_half = lat_half / coslat

    r0 = lat_to_row(min(lat + lat_half, 90.0))
    r1 = lat_to_row(max(lat - lat_half, -90.0))
    c0 = int(math.floor((lon_east - lon_half + 180.0) * RES))
    c1 = int(math.floor((lon_east + lon_half + 180.0) * RES))
    cols = np.arange(c0, c1 + 1) % NCOLS
    rows = np.arange(r0, r1 + 1)

    block = albedo[np.ix_(rows, cols)]
    vals = block[np.isfinite(block)]

    n_total = block.size
    n_valid = int(vals.size)
    frac = n_valid / n_total if n_total else 0.0

    if n_valid == 0:
        status = "no_data"
    elif frac < min_valid_fraction:
        status = "low_coverage"
    else:
        status = "ok"

    nan = float("nan")
    return {
        "lat": lat, "lon_east": lon_east, "window_km": size_km,
        "pixels_total": n_total, "pixels_valid": n_valid,
        "valid_fraction": round(frac, 3),
        "mean_albedo": float(vals.mean()) if n_valid else nan,
        "median_albedo": float(np.median(vals)) if n_valid else nan,
        "min_albedo": float(vals.min()) if n_valid else nan,
        "max_albedo": float(vals.max()) if n_valid else nan,
        "status": status,
        "note": "contextual information only — not used in similarity score",
    }


def save_check_plot(albedo, path):
    """Plot the map so you can eyeball it against the ESA browse image."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = np.ma.masked_invalid(albedo)
    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(data, cmap="gray", vmin=0.0, vmax=0.6,
                   extent=[-180, 180, -90, 90], aspect="auto")
    ax.set_xlabel("Longitude (deg East)")
    ax.set_ylabel("Latitude (deg, planetocentric)")
    ax.set_title("OMEGA NIR albedo (1.08 um), Ody et al. 2012")
    fig.colorbar(im, ax=ax, label="albedo")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tif", default=Path(__file__).resolve().parent.parent / "data" / "ALBEDO_R1080_EQU_MAP.tiff",
                    help="OMEGA albedo GeoTIFF")
    ap.add_argument("--lat", type=float, help="planetocentric latitude, degrees")
    ap.add_argument("--lon", type=float, help="EAST longitude, degrees")
    ap.add_argument("--size", type=float, default=10.0, help="window size in km (default 10)")
    ap.add_argument("--plot", help="save a check plot of the whole map to this PNG")
    args = ap.parse_args()

    alb = load_albedo(args.tif)
    if args.plot:
        save_check_plot(alb, args.plot)
        print("saved", args.plot)
    if args.lat is not None and args.lon is not None:
        res = window_stats(alb, args.lat, args.lon, args.size)
        for k, v in res.items():
            print(f"{k:15s} {v}")