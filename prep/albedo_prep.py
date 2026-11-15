"""Extract reproducible OMEGA NIR albedo context for Mars sites.

Sibling to mars_prep.py.  Input is the OMEGA/MEx albedo map
(ALBEDO_R1080_EQU_MAP.tiff) from the ESA PSA Mars Maps page:
int16 samples, nodata -32768, shape 7200 x 14400, 40 ppd (~1.48 km/pixel),
simple cylindrical, planetocentric lat, east-positive lon,
row 0 = 90N, col 0 = 180W.

SCALING (from the PDS label ALBEDO_R1080_EQU_MAP.LBL)
  albedo = raw * SCALING_FACTOR + OFFSET
  SCALING_FACTOR = 1.4522365285e-05, OFFSET = 5.2414565669e-01
  -> raw -32767..+32767 maps to albedo ~0.048..1.000
  (label MIN 0.048, MAX 1.000, MEAN 0.294).
  This is NOT "x10000"; dividing by 10000 gives values in -3.3..+3.3.
  If the GeoTIFF carries its own scale/offset tags, those are used instead.

Scientific role (project plan, section 6):
  Albedo is CONTEXTUAL INFORMATION ONLY.  It does NOT enter the similarity
  score.  Similar albedo does not mean similar composition.  OMEGA NIR
  (I/F / cos(i) at 1.08 um) is not the same spectral quantity as TES
  bolometric albedo or Earth MODIS.

Install: python -m pip install rasterio numpy matplotlib
Examples:
  # single site (unchanged behaviour)
  python prep/albedo_prep.py --id jezero_01 --name "Jezero Crater" \
      --lat 18.4 --lon 77.5 --output data/jezero_albedo.json

  # batch: one JSON per site in the SITES table below
  python prep/albedo_prep.py --batch --output-dir data/albedo

Writes a JSON whose layout matches mars_prep.py (regional / detailed /
context / quality / methods) so downstream tooling reads both files the
same way.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np

# --- OMEGA albedo map constants ---
RES = 40.0                    # pixels per degree (14400 cols / 360 deg)
NROWS, NCOLS = 7200, 14400
NODATA = -32768
RADIUS_KM = 3396.0
KM_PER_DEG = 2 * math.pi * RADIUS_KM / 360.0   # ~59.27 km per degree

# Linear scaling from the PDS label (albedo = raw * SCALING_FACTOR + OFFSET)
SCALING_FACTOR = 1.4522365285e-05
OFFSET = 5.2414565669e-01

# Sanity bounds for decoded albedo (PDS label: min 0.048, max 1.000)
ALBEDO_SANE_MIN = -0.01
ALBEDO_SANE_MAX = 1.05

MIN_VALID_FRACTION = 0.5      # flag below this (matches ti_lookup.py convention)

# Default data path (same convention as albedo_lookup.py)
DEFAULT_TIF = (
    Path(__file__).resolve().parent.parent / "prep" / "rawFiles"
    / "ALBEDO_R1080_EQU_MAP.tiff"
)

FEATURE_KEYS = (
    "median_albedo", "mean_albedo", "p10_albedo", "p90_albedo",
    "min_albedo", "max_albedo",
)

# --- Batch targets -------------------------------------------------------
# Coordinates are planetocentric lat (deg) and east-positive lon (deg).
# NOTE: Gale Crater is in the SOUTHERN hemisphere (lat = -5.4).  Do not
# "correct" this to +5.4: NASA (Curiosity site ~4.5S), ESA (5.4S / 137.9E),
# and HiRISE (~-4.72) all agree on a southern-hemisphere location.
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


def load_albedo(tif_path=DEFAULT_TIF):
    """Return physical albedo (float32) with NoData set to NaN.

    Applies the PDS scaling (raw * 1.4522e-05 + 0.52415) to int16 data.
    Fails loudly if decoded values are outside a plausible albedo range.
    """
    import rasterio
    with rasterio.open(tif_path) as src:
        if (src.height, src.width) != (NROWS, NCOLS):
            raise ValueError(
                f"Unexpected shape {(src.height, src.width)}, expected "
                f"{(NROWS, NCOLS)}. Check that this is the 40 ppd OMEGA "
                "global albedo map."
            )
        raw = src.read(1)
        nodata = src.nodata if src.nodata is not None else NODATA
        tag_scale = src.scales[0] if src.scales else 1.0
        tag_offset = src.offsets[0] if src.offsets else 0.0

    if np.issubdtype(raw.dtype, np.floating):
        # Already float: assume physical albedo unless tags say otherwise.
        valid = np.isfinite(raw) & (raw != nodata)
        scale, offset = tag_scale, tag_offset
    else:
        valid = raw != nodata
        if (tag_scale, tag_offset) != (1.0, 0.0):
            scale, offset = tag_scale, tag_offset      # GeoTIFF's own tags
        else:
            scale, offset = SCALING_FACTOR, OFFSET     # PDS label values

    albedo = raw.astype(np.float32)
    del raw
    albedo *= np.float32(scale)
    albedo += np.float32(offset)
    albedo[~valid] = np.nan

    finite = albedo[np.isfinite(albedo)]
    if finite.size == 0:
        raise ValueError("No valid pixels found in the albedo map.")
    lo, hi = float(finite.min()), float(finite.max())
    if lo < ALBEDO_SANE_MIN or hi > ALBEDO_SANE_MAX:
        raise ValueError(
            f"Decoded albedo range {lo:.3f}..{hi:.3f} is outside the "
            f"plausible {ALBEDO_SANE_MIN}..{ALBEDO_SANE_MAX} (PDS label says "
            "~0.048..1.000). The file's scaling is probably different from "
            "the PDS one; check the GeoTIFF with `rio info` / gdalinfo."
        )
    return albedo


def lat_to_row(lat):
    return int(np.clip(math.floor((90.0 - lat) * RES), 0, NROWS - 1))


def lon_to_col(lon_east):
    lon = ((lon_east + 180.0) % 360.0) - 180.0
    return int(math.floor((lon + 180.0) * RES)) % NCOLS


def _half_widths(lat, size_km):
    """Latitude and longitude half-widths (deg) of a square window."""
    lat_half = (size_km / 2.0) / KM_PER_DEG
    coslat = max(math.cos(math.radians(lat)), 1e-3)
    return lat_half, lat_half / coslat


def _window(albedo, lat, lon_east, size_km):
    """Slice a square window centred on the point. Returns the 2-D block."""
    lat_half, lon_half = _half_widths(lat, size_km)

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
        # None -> JSON null (json.dumps(allow_nan=False) rejects NaN)
        features = {k: None for k in FEATURE_KEYS}

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

    _, lon_half = _half_widths(lat, size_km)
    lat_half, _ = _half_widths(lat, size_km)
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


def build_result(albedo, site_id, site_name, lat, lon,
                 detail_km, regional_km, context_km, tif_path):
    """Build the per-site result dict (shared by single and batch modes)."""
    regional = window_context(albedo, lat, lon, regional_km)
    detailed = window_context(albedo, lat, lon, detail_km)

    px_m = 2 * math.pi * RADIUS_KM * 1000.0 / (360.0 * RES)
    result = {
        "id": site_id,
        "name": site_name,
        "source": "OMEGA/MEx NIR albedo (Ody et al. 2012), 1.08 um",
        "source_file": Path(tif_path).name,
        "source_resolution_m": round(px_m, 1),
        "source_grid": {"rows": NROWS, "cols": NCOLS, "ppd": RES},
        "center_geographic": {"lat": lat, "lon_east": lon},
        "regional": regional,
        "detailed": detailed,
        "methods": {
            "unit": ("albedo (dimensionless, I/F / cos(i) at 1.08 um, "
                     "Lambertian); decoded as raw * 1.4522365285e-05 + "
                     "0.52414565669 per the PDS label"),
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

    if context_km > 0:
        result["context"] = window_context(albedo, lat, lon, context_km)

    return result


def write_json(result, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return output


def run_single(args, albedo):
    result = build_result(
        albedo, args.id, args.name, args.lat, args.lon,
        args.detail_km, args.regional_km, args.context_km, args.tif,
    )
    output = write_json(result, args.output)

    print(f"Regional ({args.regional_km:g} km) albedo features:",
          json.dumps(result["regional"]["features"], indent=2))
    print(f"Detailed ({args.detail_km:g} km) albedo features:",
          json.dumps(result["detailed"]["features"], indent=2))
    print(f"Regional valid fraction: {result['regional']['quality']['valid_fraction']} "
          f"({result['regional']['quality']['status']})")
    print(f"Saved: {output}")


def run_batch(args, albedo):
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for i, site in enumerate(SITES, start=1):
        result = build_result(
            albedo, site["id"], site["name"], site["lat"], site["lon"],
            args.detail_km, args.regional_km, args.context_km, args.tif,
        )
        # Self-describing batch metadata.
        result["terrain"] = site["terrain"]
        result["site_index"] = i

        output = out_dir / f"{site['id']}_albedo.json"
        write_json(result, output)
        q = result["regional"]["quality"]
        written.append((site["id"], output, q))
        print(f"[{site['id']}] saved {output} "
              f"(status={q['status']}, valid_fraction={q['valid_fraction']}, "
              f"median_albedo={result['regional']['features']['median_albedo']})")

    print(f"\nWrote {len(written)} JSON files to {out_dir}")
    return written


def main():
    p = argparse.ArgumentParser(
        description="Extract OMEGA NIR albedo context for Mars sites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("tif", nargs="?", default=DEFAULT_TIF,
                   help="OMEGA albedo GeoTIFF (default: prep/rawFiles/ALBEDO_R1080_EQU_MAP.tiff)")

    # Batch mode
    p.add_argument("--batch", action="store_true",
                   help="process the built-in SITES list and write one JSON per site")
    p.add_argument("--output-dir", default="data/albedo",
                   help="directory for batch JSON outputs (default: data/albedo)")

    # Single-site mode
    p.add_argument("--id", help="Site identifier, e.g. jezero_01")
    p.add_argument("--name", help="Site name")
    p.add_argument("--lat", type=float, help="Planetocentric latitude (deg)")
    p.add_argument("--lon", type=float, help="East-positive longitude (deg)")
    p.add_argument("--output", help="JSON output path (single-site mode)")

    p.add_argument("--detail-km", type=float, default=5.0,
                   help="Detailed window size in km (default 5, matches mars_prep)")
    p.add_argument("--regional-km", type=float, default=10.0,
                   help="Regional window size in km (default 10, matches mars_prep)")
    p.add_argument("--context-km", type=float, default=50.0,
                   help="Extra-wide context window in km (default 50; -1 to skip)")
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

    albedo = load_albedo(args.tif)
    print(f"Global albedo: min={np.nanmin(albedo):.3f} "
          f"max={np.nanmax(albedo):.3f} mean={np.nanmean(albedo):.3f} "
          "(PDS label: 0.048 / 1.000 / 0.294)")

    if args.plot:
        save_check_plot(albedo, args.plot)
        print("saved", args.plot)

    if args.batch:
        run_batch(args, albedo)
    else:
        run_single(args, albedo)


if __name__ == "__main__":
    main()