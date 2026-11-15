"""Extract reproducible TES dayside thermal inertia context for a Mars site.

Sibling to albedo_prep.py and mars_prep.py.  Input is the MGS TES dayside
thermal inertia map (Putzig & Mellon 2007, PDS MGS-M-TES-5-TIMAP-V1.0):
  - 16-bit big-endian int16, shape 3600 x 7200, 20 ppd (~2.96 km/pixel)
  - simple cylindrical, planetocentric lat, east-positive lon, -180..180
  - sphere radius 3396 km, row 0 = 90N, col 0 = 180W
  - values 5..5000 J/(m^2 K sqrt(s)); 0 = no value (poles)
  - companion mask: 8-bit, same shape, 0 = interpolated pixel

Scientific role (project plan, section 6):
  Thermal inertia is a real surface feature and MAY enter the similarity
  score if the Earth side has an equivalent (e.g. MODIS-derived apparent
  thermal inertia).  For now, treat it as a quantitative surface feature
  to be compared only when a defensible cross-dataset comparison exists.

Install: python -m pip install numpy matplotlib
Examples:
  # single site (unchanged behaviour)
  python prep/ti_prep.py --id jezero_rim_01 --name "Jezero Western Rim" \
      --lat 18.392333 --lon 77.260676 --output data/jezero_rim_01_ti.json

  # batch: one JSON per site in the SITES table below
  python prep/ti_prep.py --batch --output-dir data/ti

Writes a JSON whose layout matches albedo_prep.py and mars_prep.py
(regional / detailed / context / quality / methods) so downstream tooling
reads all three files the same way.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np

# --- TES thermal inertia map constants (from the PDS label) ---
RES = 20.0                    # pixels per degree (3600 rows / 180 deg)
RADIUS_KM = 3396.0            # sphere radius from the PDS label
KM_PER_DEG = 2 * math.pi * RADIUS_KM / 360.0   # ~59.27 km per degree
NROWS, NCOLS = 3600, 7200
MAX_LAT = 87.0                # maps are only infilled between 87S and 87N
MIN_VALID_FRACTION = 0.5      # flag windows below this (shared convention)

# Default data paths (same convention as albedo_prep.py)
_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "prep" / "rawFiles"
DEFAULT_TI = _DEFAULT_DIR / "global_ti_day_2007.img"
DEFAULT_MASK = _DEFAULT_DIR / "global_ti_msk_day_2007.img"

# --- Batch targets -------------------------------------------------------
# Coordinates are planetocentric lat (deg) and east-positive lon (deg).
# Names/comments record the terrain motivation from the project brief.
SITES = [
    {
        "id": "jezero_crater",
        "name": "Jezero Crater",
        "terrain": "rocky/sedimentary terrain",
        "lat": 18.855,
        "lon": 77.519,
    },
    {
        "id": "gale_crater",
        "name": "Gale Crater",
        "terrain": "layered and mountainous terrain",
        "lat": -5.400,
        "lon": 137.800,
    },
    {
        "id": "nili_patera",
        "name": "Nili Patera",
        "terrain": "sand dunes",
        "lat": 8.900,
        "lon": 67.200,
    },
    {
        "id": "athabasca_valles",
        "name": "Athabasca Valles",
        "terrain": "volcanic lava terrain",
        "lat": 8.600,
        "lon": 156.500,
    },
    {
        "id": "victoria_crater",
        "name": "Victoria Crater",
        "terrain": "crater slopes and impact terrain",
        "lat": -2.050,
        "lon": -5.500,
    },
]


def load_maps(ti_path=DEFAULT_TI, mask_path=DEFAULT_MASK):
    """Return (thermal_inertia, mask) arrays. Values are NOT modified here."""
    ti = np.fromfile(ti_path, dtype=">i2").reshape(NROWS, NCOLS)
    mask = np.fromfile(mask_path, dtype=np.uint8).reshape(NROWS, NCOLS)
    if ti.shape != (NROWS, NCOLS):
        raise ValueError(
            f"Unexpected TI shape {ti.shape}, expected {(NROWS, NCOLS)}. "
            "Check that this is the 20 ppd TES dayside thermal inertia map."
        )
    return ti, mask


def lat_to_row(lat):
    """Planetocentric latitude (deg) -> 0-based row index (clamped)."""
    return int(np.clip(math.floor((90.0 - lat) * RES), 0, NROWS - 1))


def lon_to_col(lon_east):
    """East longitude (any range, deg) -> 0-based column index (wraps)."""
    lon = ((lon_east + 180.0) % 360.0) - 180.0
    return int(math.floor((lon + 180.0) * RES)) % NCOLS


def _window(ti, mask, lat, lon_east, size_km):
    """Slice a square window centred on the point. Returns (ti_block, mask_block)."""
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

    ti_block = ti[np.ix_(rows, cols)].astype(float)
    mask_block = mask[np.ix_(rows, cols)]
    return ti_block, mask_block


def _stats(ti_block, mask_block, lat):
    """Thermal inertia statistics for a window block.

    A pixel is valid if its value is > 0 AND the mask is 1.
    Interpolated pixels (mask == 0) are excluded, never counted as zeros.
    """
    ok = (ti_block > 0) & (mask_block == 1)
    vals = ti_block[ok]

    n_total = int(ti_block.size)
    n_valid = int(vals.size)
    frac = n_valid / n_total if n_total else 0.0

    if abs(lat) > MAX_LAT:
        status = "outside_coverage"
    elif n_valid == 0:
        status = "no_data"
    elif frac < MIN_VALID_FRACTION:
        status = "low_coverage"
    else:
        status = "ok"

    nan = float("nan")
    if n_valid:
        features = {
            "median_ti": float(np.median(vals)),
            "mean_ti": float(vals.mean()),
            "p10_ti": float(np.percentile(vals, 10)),
            "p90_ti": float(np.percentile(vals, 90)),
            "min_ti": float(vals.min()),
            "max_ti": float(vals.max()),
        }
    else:
        features = {k: nan for k in (
            "median_ti", "mean_ti", "p10_ti", "p90_ti",
            "min_ti", "max_ti",
        )}

    return features, {
        "samples": n_total,
        "samples_valid": n_valid,
        "valid_fraction": round(frac, 3),
        "status": status,
    }


def window_context(ti, mask, lat, lon_east, size_km):
    """Full stats block for one window size, mirroring albedo_prep.py layout."""
    ti_block, mask_block = _window(ti, mask, lat, lon_east, size_km)
    features, quality = _stats(ti_block, mask_block, lat)

    lat_half = (size_km / 2.0) / KM_PER_DEG
    coslat = max(math.cos(math.radians(lat)), 1e-3)
    lon_half = lat_half / coslat
    gw = int(round(2 * lon_half * RES)) + 1
    gh = int(round(2 * lat_half * RES)) + 1

    px_m = 2 * math.pi * RADIUS_KM * 1000.0 / (360.0 * RES)  # ~2964 m
    return {
        "region_km": size_km,
        "grid_width": gw,
        "grid_height": gh,
        "effective_pixel_size_m": [round(px_m, 1), round(px_m, 1)],
        "features": features,
        "quality": quality,
        "role": "quantitative_feature",
    }


def save_check_plot(ti, mask, path):
    """Plot the map (log colour scale) so you can compare it with the PDS browse JPEG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    data = np.ma.masked_where((ti <= 0) | (mask != 1), ti.astype(float))
    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(data, cmap="turbo", norm=LogNorm(vmin=5, vmax=5000),
                   extent=[-180, 180, -90, 90], aspect="auto")
    ax.set_xlabel("Longitude (deg East)")
    ax.set_ylabel("Latitude (deg, planetocentric)")
    ax.set_title("TES dayside thermal inertia, Putzig & Mellon 2007")
    fig.colorbar(im, ax=ax, label="thermal inertia (tiu)")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def build_result(ti, mask, site_id, site_name, lat, lon,
                 detail_km, regional_km, context_km,
                 ti_path, mask_path):
    """Build the per-site result dict (shared by single and batch modes)."""
    regional = window_context(ti, mask, lat, lon, regional_km)
    detailed = window_context(ti, mask, lat, lon, detail_km)

    px_m = 2 * math.pi * RADIUS_KM * 1000.0 / (360.0 * RES)
    result = {
        "id": site_id,
        "name": site_name,
        "source": "MGS TES dayside thermal inertia (Putzig & Mellon 2007)",
        "source_file": Path(ti_path).name,
        "source_mask_file": Path(mask_path).name,
        "source_resolution_m": round(px_m, 1),
        "source_grid": {"rows": NROWS, "cols": NCOLS, "ppd": RES},
        "center_geographic": {"lat": lat, "lon_east": lon},
        "regional": regional,
        "detailed": detailed,
        "methods": {
            "unit": "thermal inertia, J m^-2 K^-1 s^-0.5 (tiu); raw int16 used as-is",
            "validity": "value > 0 AND mask == 1 (interpolated pixels excluded)",
            "statistics": "median, mean, p10, p90, min, max over valid pixels",
            "window": "square in km; latitude/longitude half-widths from KM_PER_DEG and cos(lat)",
            "coverage_limit": f"|lat| > {MAX_LAT:g} deg is flagged outside_coverage",
        },
        "role": "quantitative_feature",
        "note": (
            "Thermal inertia is a physical surface property.  It may enter the "
            "similarity score only when a defensible Earth-side equivalent "
            "(e.g. MODIS-derived apparent thermal inertia) is available and the "
            "cross-dataset comparison is validated.  Until then, treat as a "
            "quantitative context feature, not a default ranking input."
        ),
    }

    if context_km > 0:
        result["context"] = window_context(ti, mask, lat, lon, context_km)

    return result


def write_json(result, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return output


def run_single(args, ti, mask):
    result = build_result(
        ti, mask, args.id, args.name, args.lat, args.lon,
        args.detail_km, args.regional_km, args.context_km,
        args.ti, args.mask,
    )
    output = write_json(result, args.output)

    print(f"Regional ({args.regional_km:g} km) TI features:",
          json.dumps(result["regional"]["features"], indent=2))
    print(f"Detailed ({args.detail_km:g} km) TI features:",
          json.dumps(result["detailed"]["features"], indent=2))
    print(f"Regional valid fraction: {result['regional']['quality']['valid_fraction']} "
          f"({result['regional']['quality']['status']})")
    print(f"Saved: {output}")


def run_batch(args, ti, mask):
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for site in SITES:
        result = build_result(
            ti, mask, site["id"], site["name"], site["lat"], site["lon"],
            args.detail_km, args.regional_km, args.context_km,
            args.ti, args.mask,
        )
        # Record the terrain motivation so the JSON is self-describing.
        result["terrain"] = site["terrain"]
        result["site_index"] = SITES.index(site) + 1

        output = out_dir / f"{site['id']}_ti.json"
        write_json(result, output)
        written.append((site["id"], output, result["regional"]["quality"]))
        print(f"[{site['id']}] saved {output} "
              f"(status={result['regional']['quality']['status']}, "
              f"valid_fraction={result['regional']['quality']['valid_fraction']})")

    print(f"\nWrote {len(written)} JSON files to {out_dir}")
    return written


def main():
    p = argparse.ArgumentParser(
        description="Extract TES dayside thermal inertia context for Mars sites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--ti", default=DEFAULT_TI,
                   help="TES dayside thermal inertia .img (default: prep/rawFiles/global_ti_day_2007.img)")
    p.add_argument("--mask", default=DEFAULT_MASK,
                   help="TES mask .img (default: prep/rawFiles/global_ti_msk_day_2007.img)")

    # Batch mode
    p.add_argument("--batch", action="store_true",
                   help="process the built-in SITES list and write one JSON per site")
    p.add_argument("--output-dir", default="data/ti",
                   help="directory for batch JSON outputs (default: data/ti)")

    # Single-site mode
    p.add_argument("--id", help="Site identifier, e.g. jezero_rim_01")
    p.add_argument("--name", help="Site name")
    p.add_argument("--lat", type=float, help="Planetocentric latitude (deg)")
    p.add_argument("--lon", type=float, help="East-positive longitude (deg)")
    p.add_argument("--output", help="JSON output path (single-site mode)")

    p.add_argument("--detail-km", type=float, default=5.0,
                   help="Detailed window size in km (default 5, matches albedo_prep)")
    p.add_argument("--regional-km", type=float, default=10.0,
                   help="Regional window size in km (default 10, matches albedo_prep)")
    p.add_argument("--context-km", type=float, default=50.0,
                   help="Extra-wide context window in km (default 50; -1 to skip)")
    p.add_argument("--no-mask", action="store_true",
                   help="keep interpolated pixels (mask == 0)")
    p.add_argument("--plot", help="save a check plot of the whole map to this PNG")
    args = p.parse_args()

    # Validate mode
    if args.batch:
        if args.id or args.name or args.lat is not None or args.lon is not None or args.output:
            p.error("--batch cannot be combined with --id/--name/--lat/--lon/--output")
    else:
        missing = [f for f in ("id", "name", "lat", "lon", "output")
                   if getattr(args, f) is None]
        if missing:
            p.error("single-site mode requires: " + ", ".join("--" + m for m in missing))

    ti, mask = load_maps(args.ti, args.mask)
    if args.no_mask:
        mask = np.ones_like(mask, dtype=np.uint8)

    if args.plot:
        save_check_plot(ti, mask, args.plot)
        print("saved", args.plot)

    if args.batch:
        run_batch(args, ti, mask)
    else:
        run_single(args, ti, mask)


if __name__ == "__main__":
    main()