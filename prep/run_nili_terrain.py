r"""Generate Nili Patera 5 km and 10 km terrain profiles from genuine MOLA data.

The script reads the official NASA PDS MOLA 128-pixels-per-degree topography
raster (big-endian int16) and uses the SAME terrain_features() calculations as
prep/mars_prep.py. Unlike the Gale DEM, MOLA is ~460 m, so both footprints are
measured at ~460 m; the detailed 5-km footprint is NOT 30-m terrain.

From the project root (Windows PowerShell):
  .\.venv\Scripts\python.exe prep/run_nili_terrain.py --download

The PDS tile covers 44N-0N, 0E-90E. This script uses the selected Nili Patera
centre 8.9N, 67.2E. Coordinate is taken from shared team's TI/albedo reference,
not chosen by taking the geographical midpoint of the MOLA raster.
"""

import argparse
import json
import math
import os
from pathlib import Path
import urllib.request

import numpy as np
from pyproj import CRS, Transformer
from mars_prep import terrain_features

SITE_ID = "nili_patera_01"
SITE_NAME = "Nili Patera"
SITE_LAT = 8.9
SITE_LON_E = 67.2
MARS_RADIUS_M = 3396190.0  # Same project Mars sphere convention as Jezero/Gale
PIXELS_PER_DEGREE = 128
SOURCE_TOP_LAT = 44.0
SOURCE_LEFT_LON_E = 0.0
SOURCE_ROWS = 5632
SOURCE_COLS = 11520
SOURCE_SIZE_BYTES = SOURCE_ROWS * SOURCE_COLS * 2
SOURCE_FILENAME = "megt44n000hb.img"
LABEL_FILENAME = "megt44n000hb.lbl"
SOURCE_ROOT = (
    "https://pds-geosciences.wustl.edu/mgs/"
    "urn-nasa-pds-mgs_mola_topography_derived/meg128/"
)


def fetch(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    print(f"Downloading {destination.name} from NASA PDS...", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NASA-Space-Apps-Mars-Analog/1.0"})
        with urllib.request.urlopen(req, timeout=90) as src, temporary.open("wb") as out:
            total = 0
            last_report = 0
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                total += len(chunk)
                if total - last_report >= 16 * 1024 * 1024:
                    print(f"  {total / 1e6:.1f} MB downloaded", flush=True)
                    last_report = total
        temporary.replace(destination)
    except Exception:
        print(f"Download interrupted; incomplete file retained at {temporary}", flush=True)
        raise
    print(f"Saved: {destination}")


def projected_crs():
    # Local equidistant cylindrical analysis CRS at the site's latitude.
    # Correct horizontal pixel size for physical longitudinal convergence.
    proj = CRS.from_proj4(
        f"+proj=eqc +lat_ts={SITE_LAT} +lon_0=0 +R={MARS_RADIUS_M} "
        "+units=m +no_defs +type=crs"
    )
    # Name the planetary CRS so shared site_geometry.py recognises it as Mars.
    wkt = proj.to_wkt(version="WKT1_GDAL")
    wkt = wkt.replace('PROJCS["unknown"', 'PROJCS["Mars_Nili_Patera_local_EQC"', 1)
    named = CRS.from_wkt(wkt)
    geographic = CRS.from_proj4(
        f"+proj=longlat +R={MARS_RADIUS_M} +no_defs +type=crs"
    )
    return named, geographic


def subset_at_native_resolution(array, cx, cy, width_km, dx_m, dy_m):
    half = width_km * 1000.0 / 2
    # Source topography is a constant-degree grid: row 0 starts at 44N, col 0 at 0E.
    # Using pixel-centre coordinates rather than inventing finer pixels.
    col_first = max(0, math.ceil((cx - half) / dx_m - 0.5))
    col_last = min(SOURCE_COLS - 1, math.floor((cx + half) / dx_m - 0.5))
    row_first = max(0, math.ceil((SOURCE_TOP_LAT * (math.pi / 180) * MARS_RADIUS_M - cy + -half) / dy_m - 0.5))
    row_last = min(SOURCE_ROWS - 1, math.floor((SOURCE_TOP_LAT * (math.pi / 180) * MARS_RADIUS_M - cy + half) / dy_m - 0.5))
    if row_last - row_first + 1 < 3 or col_last - col_first + 1 < 3:
        raise ValueError("Insufficient MOLA cells: site point or window outside tile.")
    # Read only local region, not entire 130 MB into memory.
    elevation = np.asarray(array[row_first:row_last + 1, col_first:col_last + 1], dtype=np.float64)
    if not np.isfinite(elevation).all() or (elevation <= -32768).any():
        elevation[elevation <= -32768] = np.nan
    print(f"{width_km:g} km: grid {elevation.shape[1]}x{elevation.shape[0]} MOLA native pixels")
    stats = terrain_features(elevation, dx_m, dy_m)
    stats.update({
        "region_km": width_km,
        "grid_width": int(elevation.shape[1]),
        "grid_height": int(elevation.shape[0]),
        "effective_pixel_size_m": [round(dx_m, 3), round(dy_m, 3)],
        "quality_note": "MOLA bins may contain interpolated elevations where no laser shot existed; this is not 30m DEM data.",
    })
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true", help="Download official MOLA tile and label if missing")
    parser.add_argument("--input", default="raw_data/nili_patera/megt44n000hb.img")
    parser.add_argument("--output", default="data/nili_patera_features.json")
    args = parser.parse_args()

    source = Path(args.input)
    label = source.with_suffix(".lbl")
    if args.download:
        if not source.exists():
            fetch(SOURCE_ROOT + SOURCE_FILENAME, source)
        if not label.exists():
            fetch(SOURCE_ROOT + LABEL_FILENAME, label)
    if not source.exists():
        parser.error(f"Missing {source}; run with --download, or download tile manually.")
    actual_size = source.stat().st_size
    if actual_size != SOURCE_SIZE_BYTES:
        raise ValueError(f"Incomplete/wrong MOLA tile: {actual_size:,} bytes; expected {SOURCE_SIZE_BYTES:,}")

    projected, geographic = projected_crs()
    fwd = Transformer.from_crs(geographic, projected, always_xy=True)
    rev = Transformer.from_crs(projected, geographic, always_xy=True)
    center_x, center_y = fwd.transform(SITE_LON_E, SITE_LAT)
    lon_out, lat_out = rev.transform(center_x, center_y)
    print(f"Using unified Nili center: {lat_out:.6f} N, {lon_out:.6f} E")

    earth_equator_cell_m = MARS_RADIUS_M * math.pi / (180 * PIXELS_PER_DEGREE)
    dx = earth_equator_cell_m * math.cos(math.radians(SITE_LAT))
    dy = earth_equator_cell_m
    # MOLA tile first pixel centres: (0+0.5)/128 E, (44-0.5/128) N
    array = np.memmap(source, dtype=">i2", mode="r", shape=(SOURCE_ROWS, SOURCE_COLS))
    regional = subset_at_native_resolution(array, center_x, center_y, 10.0, dx, dy)
    detailed = subset_at_native_resolution(array, center_x, center_y, 5.0, dx, dy)

    result = {
        "id": SITE_ID,
        "name": SITE_NAME,
        "source_dem": SOURCE_FILENAME,
        "source_crs_wkt": projected.to_wkt(version="WKT1_GDAL"),
        "source_pixel_size_m": [round(dx, 3), round(dy, 3)],
        "center_projected_m": {"x": center_x, "y": center_y},
        "center_geographic": {"lat": lat_out, "lon_east": lon_out},
        "coordinate_source": "8.9N, 67.2E project reference from existing TI/albedo sources; transformed using Mars sphere",
        "regional": regional,
        "detailed": detailed,
        "methods": {
            "slope": "degrees(arctan(hypot(gradient_x, gradient_y)))",
            "steep_fraction": "fraction of slope samples greater than 15 degrees",
            "relief": "elevation percentile 95 minus percentile 5, in metres",
            "roughness_m": "SD of elevation minus weighted Gaussian-smoothed elevation; sigma=1000m, matching mars_prep.py",
            "resampling": "NONE: native MOLA 128 pixels/degree, pixel centres inside a projected 10km/5km square",
            "nodata": "NASA PDS MOLA gridded topography; some source bins are interpolated when shot coverage is absent",
            "native_source_grid": "Planetocentric 0E-90E, 44N-0N, 128 pixels/degree, MSB signed int16 topography metres",
            "resolution_limit": "Both regional and detailed computed at native ~460m. NO 30m detail exists in this source.",
        },
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print("Regional terrain:", json.dumps(regional["features"], indent=2))
    print("Detailed terrain (native MOLA):", json.dumps(detailed["features"], indent=2))
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
