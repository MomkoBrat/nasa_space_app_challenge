"""STEP 2 — Earth terrain features for the eligible candidate cells.

Uses the SAME feature code as Mars (terrain_features / local_roughness from prep/mars_prep.py),
so slope, steep fraction, relief and roughness (sigma = 1000 m) are computed identically.

Per cell:
  1. Read the Copernicus GLO-30 DEM (public AWS bucket, no login; only the needed window
     of each 1°x1° tile is downloaded) around the cell centre.
  2. Average-resample it onto a 10 km x 10 km square in a local Transverse Mercator projection
     centred on the cell, 22 x 22 pixels (~454.5 m), like the Mars regional grid.
  3. Run terrain_features() from mars_prep.py.

Usage:
  python prep/earth_terrain.py                       # all eligible cells
  python prep/earth_terrain.py --region utah --limit 20   # quick test
Input:  data/earth_candidates.csv  (step 1 export)
Output: data/earth_terrain.csv     (appended per cell; re-running skips finished ids)
"""

import argparse
import csv
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import from_bounds

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mars_prep import terrain_features  # noqa: E402  (identical method to Mars)

CELL_M = 10_000.0
GRID = 22  # same as Mars regional grid -> ~454.5 m pixels
PIXEL_M = CELL_M / GRID
TILE_URL = ("https://copernicus-dem-30m.s3.amazonaws.com/"
            "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/"
            "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif")
GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "3",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "VSI_CACHE": "TRUE",
}
FEATURES = ["median_slope_deg", "steep_fraction", "relief_m", "roughness_m"]
EXTRA = ["mean_slope_deg", "slope_p90_deg", "flat_fraction", "elevation_std_m",
         "roughness_100m_m", "roughness_500m_m"]
COLUMNS = (["id", "region", "lat", "lon"] + FEATURES + EXTRA
           + ["valid_fraction", "samples", "status", "error"])


def tile_url(lat_floor, lon_floor):
    return TILE_URL.format(ns="N" if lat_floor >= 0 else "S", lat=abs(lat_floor),
                           ew="E" if lon_floor >= 0 else "W", lon=abs(lon_floor))


def cell_elevation(lat, lon):
    """22x22 elevation grid (metres, NaN where no DEM) for a 10 km square centred on lat/lon."""
    dst_crs = CRS.from_proj4(f"+proj=tmerc +lat_0={lat} +lon_0={lon} +k=1 "
                             "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")
    dst_transform = from_origin(-CELL_M / 2, CELL_M / 2, PIXEL_M, PIXEL_M)
    dst = np.full((GRID, GRID), np.nan, dtype=np.float64)

    # Geographic bounds of the square, padded slightly so edge pixels have full support.
    w, s, e, n = transform_bounds(dst_crs, "EPSG:4326",
                                  -CELL_M / 2, -CELL_M / 2, CELL_M / 2, CELL_M / 2)
    pad = 0.01
    w, s, e, n = w - pad, s - pad, e + pad, n + pad

    tiles_read = 0
    for tlat in range(math.floor(s), math.floor(n) + 1):
        for tlon in range(math.floor(w), math.floor(e) + 1):
            try:
                src = rasterio.open(tile_url(tlat, tlon))
            except rasterio.errors.RasterioIOError:
                continue  # no tile = open ocean; those pixels stay NaN
            with src:
                win = from_bounds(max(w, tlon), max(s, tlat),
                                  min(e, tlon + 1), min(n, tlat + 1), src.transform)
                win = win.round_offsets().round_lengths()
                if win.width < 1 or win.height < 1:
                    continue  # cell only grazes this tile's edge (< 1 pixel); nothing to read
                data = src.read(1, window=win, boundless=True, fill_value=np.nan,
                                out_dtype="float64")
                if src.nodata is not None:
                    data[data == src.nodata] = np.nan
                part = np.full_like(dst, np.nan)
                reproject(data, part,
                          src_transform=src.window_transform(win), src_crs=src.crs,
                          src_nodata=np.nan, dst_transform=dst_transform,
                          dst_crs=dst_crs, dst_nodata=np.nan,
                          resampling=Resampling.average)
                fill = np.isnan(dst) & ~np.isnan(part)
                dst[fill] = part[fill]
                tiles_read += 1
    return dst, tiles_read


def process(row):
    lat, lon = float(row["lat"]), float(row["lon"])
    out = {"id": row["id"], "region": row["region"], "lat": lat, "lon": lon}
    try:
        with rasterio.Env(**GDAL_ENV):
            elev, tiles = cell_elevation(lat, lon)
        if tiles == 0:
            raise ValueError("no Copernicus tile covers this cell")
        stats = terrain_features(elev, PIXEL_M, PIXEL_M)  # raises if < 95 % valid pixels
        out.update({k: round(v, 6) for k, v in stats["features"].items()})
        out.update({k: round(v, 6) for k, v in stats["additional_features"].items()})
        out["valid_fraction"] = round(stats["quality"]["valid_fraction_resampled"], 4)
        out["samples"] = stats["quality"]["samples"]
        out["status"] = "ok"
        out["error"] = ""
    except Exception as exc:  # recorded per cell, the run continues
        out["status"] = "failed"
        out["error"] = f"{type(exc).__name__}: {exc}"[:200]
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--input", default="data/earth_candidates.csv")
    p.add_argument("--output", default="data/earth_terrain.csv")
    p.add_argument("--region", help="only this region (e.g. utah)")
    p.add_argument("--limit", type=int, help="only the first N cells (testing)")
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args()

    with open(args.input, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)
                if str(r["eligible"]).strip() in ("1", "true", "True")]
    if args.region:
        rows = [r for r in rows if r["region"] == args.region]

    out_path = Path(args.output)
    done = set()
    if out_path.exists():
        with open(out_path, newline="", encoding="utf-8") as f:
            done = {r["id"] for r in csv.DictReader(f)}
    rows = [r for r in rows if r["id"] not in done]
    if args.limit:
        rows = rows[: args.limit]
    print(f"{len(rows)} eligible cells to process ({len(done)} already in {out_path})")
    if not rows:
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out_path.exists()
    started, ok, failed = time.time(), 0, 0
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if new_file:
            writer.writeheader()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(process, r) for r in rows]
            for i, fut in enumerate(as_completed(futures), 1):
                result = fut.result()
                writer.writerow(result)
                f.flush()
                if result["status"] == "ok":
                    ok += 1
                else:
                    failed += 1
                    print(f"  failed {result['id']}: {result['error']}")
                if i % 25 == 0 or i == len(rows):
                    rate = i / (time.time() - started)
                    print(f"  {i}/{len(rows)} done ({ok} ok, {failed} failed), "
                          f"{rate:.1f} cells/s, ~{(len(rows) - i) / rate / 60:.0f} min left")
    print(f"Finished: {ok} ok, {failed} failed -> {out_path}")


if __name__ == "__main__":
    main()
