"""Extract reproducible OMEGA NIR albedo context for a Mars site.

Sibling to mars_prep.py.  Input is the OMEGA/MEx albedo GeoTIFF
(ALBEDO_R1080_EQU_MAP.tiff): int16 scaled albedo (x10000), nodata -32768,
shape 7200 x 14400, 40 ppd (~1.48 km/pixel), simple cylindrical,
planetocentric lat, east-positive lon, row 0 = 90N, col 0 = 180W.

Scientific role (project plan, section 6):
  Albedo is CONTEXTUAL INFORMATION ONLY.  It does NOT enter the similarity
  score.  Similar albedo does not mean similar composition.  OMEGA NIR is
  not the same spectral quantity as TES bolometric albedo or Earth MODIS.

Install: python -m pip install rasterio numpy matplotlib
Example:
  python prep/albedo_prep.py --id jezero_01 --name "Jezero Crater" \
      --lat 18.4 --lon 77.5 --output data/jezero_albedo.json

Writes a JSON whose layout matches mars_prep.py (regional / detailed /
quality / methods) so downstream tooling reads both files the same way.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np

# --- OMEGA albedo map constants (from the GeoTIFF transform) ---
RES = 40.0                    # pixels per degree (14400 cols / 360 deg)
NROWS, NCOLS = 7200, 14400
SCALE = 10000.0               # int16 -> albedo
NODATA = -32768
RADIUS_KM = 3396.0
KM_PER_DEG = 2 * math.pi * RADIUS_KM / 360.0   # ~59.27 km per degree

MIN_VALID_FRACTION = 0.5      # flag below this (matches ti_lookup.py convention)

# Default data path (same convention as albedo_lookup.py)
DEFAULT_TIF = (
    Path(__file__).resolve().parent.parent / "prep" / "rawFiles"
    / "ALBEDO_R1080_EQU_MAP.tiff"
)


def load_albedo(tif_path=DEFAULT_TIF):
    """Return albedo as float32 with NoData set to NaN."""
    import rasterio
    with rasterio.open(tif_path) as src:
        raw = src.read(1).astype(np.float32)
        nodata = src.nodata if src.nodata is not None else NODATA
        if raw.shape != (NROWS, NCOLS):
            raise ValueError(
                f"Unexpected shape {raw.shape}, expected {(NROWS, NCOLS)}. "
                "Check that this is the 40 ppd OMEGA global albedo map."
            )
    albedo = raw / SCALE
    albedo[raw == nodata] = np.nan
    return albedo


def lat_to_row(lat):
    return int(np.clip(math.floor((90.0 - lat) * RES), 0, NROWS - 1))


def lon_to_col(lon_east):
    lon = ((lon_east + 180.0) % 360.0) - 180.0
    return int(math.floor((lon + 180.0) * RES)) % NCOLS


def _window(albedo, lat, lon_east, size_km):
    """Slice a square window centred on the point. Returns the 2-D block."""
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
    return albedo[np.ix_(rows, cols)]


def _stats(block):
    """Albedo statistics for a window block (already masked to NaN)."""
    vals = block[np.isfinite(block)]
    n_total = int(block.size)
    n_valid = int(vals.size)
    frac = n_valid / n_total if n_total else 0.0

    if n_valid == 0:
        status = "no_data"
    elif frac < MIN_VALID_FRACTION:
        status = "low_coverage"
    else:
        status = "ok"

    nan = float("nan")
    if n_valid:
        features = {
            "median_albedo": float(np.median(vals)),
            "mean_albedo": float(vals.mean()),
            "p10_albedo": float(np.percentile(vals, 10)),
            "p90_albedo": float(np.percentile(vals, 90)),
            "min_albedo": float(vals.min()),
            "max_albedo": float(vals.max()),
        }
    else:
        features = {k: nan for k in (
            "median_albedo", "mean_albedo", "p10_albedo", "p90_albedo",
            "min_albedo", "max_albedo",
        )}

    return features, {
        "samples": n_total,
        "samples_valid": n_valid,
        "valid_fraction": round(frac, 3),
        "status": status,
    }


def window_context(albedo, lat, lon_east, size_km):
    """Full stats block for one window size, mirroring mars_prep.py layout."""
    block = _window(albedo, lat, lon_east, size_km)
    features, quality = _stats(block)

    lat_half = (size_km / 2.0) / KM_PER_DEG
    coslat = max(math.cos(math.radians(lat)), 1e-3)
    lon_half = lat_half / coslat
    gw = int(round(2 * lon_half * RES)) + 1
    gh = int(round(2 * lat_half * RES)) + 1

    px_m = 2 * math.pi * RADIUS_KM * 1000.0 / (360.0 * RES)  # ~1481.8 m
    return {
        "region_km": size_km,
        "grid_width": gw,
        "grid_height": gh,
        "effective_pixel_size_m": [round(px_m, 1), round(px_m, 1)],
        "features": features,
        "quality": quality,
        "role": "contextual_only",
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


def main():
    p = argparse.ArgumentParser(
        description="Extract OMEGA NIR albedo context for a Mars site",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("tif", nargs="?", default=DEFAULT_TIF,
                   help="OMEGA albedo GeoTIFF (default: prep/rawFiles/ALBEDO_R1080_EQU_MAP.tiff)")
    p.add_argument("--id", required=True, help="Site identifier, e.g. jezero_01")
    p.add_argument("--name", required=True, help="Site name")
    p.add_argument("--lat", type=float, required=True, help="Planetocentric latitude (deg)")
    p.add_argument("--lon", type=float, required=True, help="East-positive longitude (deg)")
    p.add_argument("--output", required=True, help="JSON output path")
    p.add_argument("--detail-km", type=float, default=5.0,
                   help="Detailed window size in km (default 5, matches mars_prep)")
    p.add_argument("--regional-km", type=float, default=10.0,
                   help="Regional window size in km (default 10, matches mars_prep)")
    p.add_argument("--context-km", type=float, default=50.0,
                   help="Extra-wide context window in km (default 50; -1 to skip)")
    p.add_argument("--plot", help="save a check plot of the whole map to this PNG")
    args = p.parse_args()

    albedo = load_albedo(args.tif)

    if args.plot:
        save_check_plot(albedo, args.plot)
        print("saved", args.plot)

    regional = window_context(albedo, args.lat, args.lon, args.regional_km)
    detailed = window_context(albedo, args.lat, args.lon, args.detail_km)

    px_m = 2 * math.pi * RADIUS_KM * 1000.0 / (360.0 * RES)
    result = {
        "id": args.id,
        "name": args.name,
        "source": "OMEGA/MEx NIR albedo (Ody et al. 2012), 1.08 um",
        "source_file": Path(args.tif).name,
        "source_resolution_m": round(px_m, 1),
        "source_grid": {"rows": NROWS, "cols": NCOLS, "ppd": RES},
        "center_geographic": {"lat": args.lat, "lon_east": args.lon},
        "regional": regional,
        "detailed": detailed,
        "methods": {
            "unit": "albedo (dimensionless, 0-1); raw int16 divided by 10000",
            "validity": "finite (NoData -32768 excluded; real albedo near 0 is valid)",
            "statistics": "median, mean, p10, p90, min, max over valid pixels",
            "window": "square in km; latitude/longitude half-widths from KM_PER_DEG and cos(lat)",
        },
        "role": "contextual_only",
        "note": (
            "Albedo is CONTEXTUAL INFORMATION ONLY and is NOT used in the "
            "similarity score (project plan section 6).  Similar albedo does "
            "not mean similar composition.  OMEGA NIR is not the same spectral "
            "quantity as TES bolometric albedo or Earth MODIS."
        ),
    }

    if args.context_km > 0:
        result["context"] = window_context(albedo, args.lat, args.lon, args.context_km)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")

    print(f"Regional ({args.regional_km:g} km) albedo features:",
          json.dumps(regional["features"], indent=2))
    print(f"Detailed ({args.detail_km:g} km) albedo features:",
          json.dumps(detailed["features"], indent=2))
    print(f"Regional valid fraction: {regional['quality']['valid_fraction']} "
          f"({regional['quality']['status']})")
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()