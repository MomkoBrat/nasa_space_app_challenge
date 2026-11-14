"""
Look up MGS TES dayside thermal inertia (Putzig & Mellon 2007, PDS data set
MGS-M-TES-5-TIMAP-V1.0) for a point or a square window on Mars.

Files needed (same folder, or pass paths):
  global_ti_day_2007.img      16-bit big-endian integers, 3600 rows x 7200 cols
  global_ti_msk_day_2007.img  8-bit mask, same shape (0 = interpolated)

Facts taken from the PDS labels:
  - simple cylindrical, 20 pixels/degree (~2.96 km/pixel at the equator)
  - planetocentric latitude, EAST-positive longitude, -180..180
  - sphere radius 3396 km
  - row 0 is 90N, column 0 is 180W
  - values 5..5000 J/(m^2 K sqrt(s)); 0 means "no value" (poles)

Usage:
  python ti_lookup.py --lat 18.4 --lon 77.5 --size 10
  python ti_lookup.py --lat 18.4 --lon 77.5 --size 10 --plot check.png
"""
import argparse
import math
import numpy as np
from pathlib import Path

RES = 20.0                    # pixels per degree (from label)
RADIUS_KM = 3396.0            # sphere radius (from label)
KM_PER_DEG = 2 * math.pi * RADIUS_KM / 360.0   # ~59.27 km per degree of latitude
NROWS, NCOLS = 3600, 7200
MAX_LAT = 87.0                # maps are only infilled between 87S and 87N
MIN_VALID_FRACTION = 0.5      # below this the window is flagged (put in shared config)


def load_maps(ti_path="global_ti_day_2007.img", mask_path="global_ti_msk_day_2007.img"):
    """Return (thermal_inertia, mask) arrays. Values are NOT modified here."""
    ti = np.fromfile(ti_path, dtype=">i2").reshape(NROWS, NCOLS)   # big-endian int16
    mask = np.fromfile(mask_path, dtype=np.uint8).reshape(NROWS, NCOLS)
    return ti, mask


def lat_to_row(lat):
    """Planetocentric latitude (deg) -> 0-based row index (clamped)."""
    return int(np.clip(math.floor((90.0 - lat) * RES), 0, NROWS - 1))


def lon_to_col(lon_east):
    """East longitude (any range, deg) -> 0-based column index (wraps)."""
    lon = ((lon_east + 180.0) % 360.0) - 180.0
    return int(math.floor((lon + 180.0) * RES)) % NCOLS


def window_stats(ti, mask, lat, lon_east, size_km=10.0, use_mask=True,
                 min_valid_fraction=MIN_VALID_FRACTION):
    """
    Statistics of thermal inertia in a size_km x size_km window centred on a point.

    A pixel is 'valid' if its value is > 0 and (when use_mask) the mask is 1.
    Pixels that are not valid are excluded, never counted as zeros.
    """
    half_km = size_km / 2.0
    lat_half = half_km / KM_PER_DEG
    coslat = max(math.cos(math.radians(lat)), 1e-3)
    lon_half = lat_half / coslat

    r0 = lat_to_row(min(lat + lat_half, 90.0))     # north edge (smaller row)
    r1 = lat_to_row(max(lat - lat_half, -90.0))    # south edge
    c0 = int(math.floor((lon_east - lon_half + 180.0) * RES))
    c1 = int(math.floor((lon_east + lon_half + 180.0) * RES))
    cols = np.arange(c0, c1 + 1) % NCOLS           # wrap across the +-180 seam
    rows = np.arange(r0, r1 + 1)

    block = ti[np.ix_(rows, cols)].astype(float)
    ok = block > 0
    if use_mask:
        ok &= mask[np.ix_(rows, cols)] == 1
    vals = block[ok]

    n_total = block.size
    n_valid = int(vals.size)
    frac = n_valid / n_total

    if abs(lat) > MAX_LAT:
        status = "outside_coverage"      # poleward of 87 degrees
    elif n_valid == 0:
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
        "mean": float(vals.mean()) if n_valid else nan,
        "median": float(np.median(vals)) if n_valid else nan,
        "min": float(vals.min()) if n_valid else nan,
        "max": float(vals.max()) if n_valid else nan,
        "status": status,
    }


def save_check_plot(ti, mask, path):
    """Plot the map (log colour scale) so you can compare it with the browse JPEG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    data = np.ma.masked_where(ti <= 0, ti.astype(float))
    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(data, cmap="turbo", norm=LogNorm(vmin=5, vmax=5000),
                   extent=[-180, 180, -90, 90], aspect="auto")
    ax.set_xlabel("Longitude (deg East)")
    ax.set_ylabel("Latitude (deg, planetocentric)")
    ax.set_title("TES dayside thermal inertia, read from global_ti_day_2007.img")
    fig.colorbar(im, ax=ax, label="thermal inertia (tiu)")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ti", default=Path(__file__).resolve().parent.parent / "data" / "global_ti_day_2007.img")

    ap.add_argument("--mask", default=Path(__file__).resolve().parent.parent / "data" / "global_ti_msk_day_2007.img")
    ap.add_argument("--lat", type=float, help="planetocentric latitude, degrees")
    ap.add_argument("--lon", type=float, help="EAST longitude, degrees (0-360 or -180..180)")
    ap.add_argument("--size", type=float, default=10.0, help="window size in km (default 10)")
    ap.add_argument("--no-mask", action="store_true", help="keep interpolated pixels")
    ap.add_argument("--plot", help="save a check plot of the whole map to this PNG")
    args = ap.parse_args()

    ti_map, msk = load_maps(args.ti, args.mask)
    if args.plot:
        save_check_plot(ti_map, msk, args.plot)
        print("saved", args.plot)
    if args.lat is not None and args.lon is not None:
        res = window_stats(ti_map, msk, args.lat, args.lon, args.size, use_mask=not args.no_mask)
        for k, v in res.items():
            print(f"{k:15s} {v}")
