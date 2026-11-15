"""STEP 3 — Earth thermal features (MODIS LST + albedo) for the eligible candidate cells.

Same layout as prep/earth_terrain.py: one row per eligible cell, the same 10 km x 10 km footprint,
a resumable CSV and a thread pool. The data come from Google Earth Engine instead of AppEEARS:
no task queue and no bundle download - the cell statistics are computed on Google's side and only
a handful of numbers come back per cell.

Per cell:
  1. Take the 10 km square centred on the cell (lat/lon from earth_candidates.csv).
  2. MOD11A2.061 (8-day LST, 1 km): LST_Day_1km and LST_Night_1km. Only composites where day AND
     night are valid (and good quality) are used -> annual mean day, night and dT = day - night.
  3. MCD43A3.061 (daily albedo, 500 m): Albedo_BSA_shortwave -> annual mean (quality filtered).
  4. Spatial mean / std over the square; apparent thermal inertia ATI = (1 - albedo) / dT.

Setup (once):
  pip install earthengine-api
  earthengine authenticate          # or let the script call ee.Authenticate() on first run
Usage:
  python prep/earth_thermal.py --project YOUR_GEE_PROJECT                   # all eligible cells
  python prep/earth_thermal.py --project YOUR_GEE_PROJECT --region utah --limit 5   # quick test
  (the project can also come from the EE_PROJECT environment variable)
Input:  data/earth_candidates.csv  (step 1 export)
Output: data/earth_thermal.csv     (appended per cell; re-running skips finished ids and retries failed ones)
"""

import argparse
import csv
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import ee

CELL_M = 10_000.0
LST_ID = "MODIS/061/MOD11A2"   # 8-day land surface temperature, 1 km
ALB_ID = "MODIS/061/MCD43A3"   # daily albedo (16-day window), 500 m
HIGH_VOLUME_URL = "https://earthengine-highvolume.googleapis.com"
FEATURES = ["lst_day_k", "lst_night_k", "dT_k", "albedo_bsa_sw"]
EXTRA = ["ati", "lst_day_std_k", "lst_night_std_k", "dT_std_k", "albedo_std"]
COLUMNS = (["id", "region", "lat", "lon"] + FEATURES + EXTRA
           + ["lst_obs_fraction", "albedo_obs_fraction", "status", "error"])
STD_OF = {"lst_day_std_k": "lst_day_k", "lst_night_std_k": "lst_night_k",
          "dT_std_k": "dT_k", "albedo_std": "albedo_bsa_sw"}


# ----------------------------------------------------------------------------- Earth Engine
def init_ee(project):
    """Initialise Earth Engine with the already-authorised account / project."""
    try:
        ee.Initialize(project=project, opt_url=HIGH_VOLUME_URL)
        ee.Number(1).getInfo()          # fails fast if the project / account is not usable
    except Exception:
        ee.Authenticate()               # no-op when valid credentials exist, else opens a browser once
        ee.Initialize(project=project)  # standard endpoint as a fallback
        ee.Number(1).getInfo()


def lst_layer(start, end_excl, qc):
    """Annual-mean day / night LST (K) and dT from MOD11A2, plus the fraction of valid composites."""
    def prep(img):
        d_raw, n_raw = img.select("LST_Day_1km"), img.select("LST_Night_1km")
        ok = d_raw.gt(0).And(n_raw.gt(0))                 # 0 = fill value
        if qc:                                            # QA bits 0-1 == 0 -> "LST produced, good quality"
            ok = ok.And(img.select("QC_Day").bitwiseAnd(3).eq(0))
            ok = ok.And(img.select("QC_Night").bitwiseAnd(3).eq(0))
        day, night = d_raw.multiply(0.02), n_raw.multiply(0.02)   # scale factor 0.02 -> Kelvin
        return (ee.Image.cat([day, night, day.subtract(night)])
                .rename(["lst_day_k", "lst_night_k", "dT_k"]).updateMask(ok))

    col = ee.ImageCollection(LST_ID).filterDate(start, end_excl).map(prep)
    n = col.size()
    obs = col.select("dT_k").count().unmask(0).divide(n).rename("lst_obs_fraction")
    proj = ee.ImageCollection(LST_ID).first().select("LST_Day_1km").projection()
    return (col.mean().addBands(obs), proj), n


def albedo_layer(start, end_excl, qc):
    """Annual-mean black-sky shortwave albedo from MCD43A3, plus the fraction of valid days."""
    def prep(img):
        a = img.select("Albedo_BSA_shortwave").multiply(0.001)     # scale factor 0.001
        ok = a.gte(0).And(a.lte(1))
        if qc:   # 0 = full BRDF inversion, 1 = magnitude inversion (both usable); 255 = fill
            ok = ok.And(img.select("BRDF_Albedo_Band_Mandatory_Quality_shortwave").lte(1))
        return a.rename("albedo_bsa_sw").updateMask(ok)

    col = ee.ImageCollection(ALB_ID).filterDate(start, end_excl).map(prep)
    n = col.size()
    obs = col.count().unmask(0).divide(n).rename("albedo_obs_fraction")
    proj = ee.ImageCollection(ALB_ID).first().select("Albedo_BSA_shortwave").projection()
    return (col.mean().addBands(obs), proj), n


def cell_stats(lst, alb, lat, lon):
    """One Earth Engine request: spatial mean / std of the annual-mean images over the 10 km cell."""
    geom = ee.Geometry.Point([lon, lat]).buffer(CELL_M / 2).bounds(1)
    reducer = ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True)
    parts = [img.reduceRegion(reducer=reducer, geometry=geom, crs=proj,
                              scale=proj.nominalScale(), maxPixels=1e8)   # native MODIS grid, no resampling
             for img, proj in (lst, alb)]
    return parts[0].combine(parts[1]).getInfo()


def with_retries(fn, tries=3):
    for attempt in range(tries):
        try:
            return fn()
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** (attempt + 1))  # 2 s, 4 s: covers quota / timeout hiccups


def r6(v):
    return "" if v is None else round(v, 6)


# ----------------------------------------------------------------------------- per cell
def process(row, lst, alb):
    lat, lon = float(row["lat"]), float(row["lon"])
    out = {"id": row["id"], "region": row["region"], "lat": lat, "lon": lon}
    try:
        s = with_retries(lambda: cell_stats(lst, alb, lat, lon))
        if any(s.get(f"{b}_mean") is None for b in FEATURES):
            raise ValueError("no valid MODIS pixels in this cell for the chosen period / QC")
        for b in FEATURES:
            out[b] = r6(s[f"{b}_mean"])
        for col, b in STD_OF.items():
            out[col] = r6(s.get(f"{b}_stdDev"))
        dT, albedo = s["dT_k_mean"], s["albedo_bsa_sw_mean"]
        out["ati"] = r6((1 - albedo) / dT) if dT > 0 else ""
        out["lst_obs_fraction"] = r6(s.get("lst_obs_fraction_mean"))
        out["albedo_obs_fraction"] = r6(s.get("albedo_obs_fraction_mean"))
        out["status"] = "ok"
        out["error"] = ""
    except Exception as exc:  # recorded per cell, the run continues
        out["status"] = "failed"
        out["error"] = f"{type(exc).__name__}: {exc}"[:200]
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--input", default="data/earth_candidates.csv")
    p.add_argument("--output", default="data/earth_thermal.csv")
    p.add_argument("--region", help="only this region (e.g. utah)")
    p.add_argument("--limit", type=int, help="only the first N cells (testing)")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--project", default=os.environ.get("EE_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT"),
                   help="Google Cloud / Earth Engine project id (or set EE_PROJECT)")
    p.add_argument("--start", default="2023-01-01", help="first day, YYYY-MM-DD")
    p.add_argument("--end", default="2023-12-31", help="last day (inclusive), YYYY-MM-DD")
    p.add_argument("--no-qc", action="store_true", help="skip the MODIS quality-flag filtering")
    args = p.parse_args()
    if not args.project:
        p.error("pass --project or set the EE_PROJECT environment variable")

    with open(args.input, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)
                if str(r["eligible"]).strip() in ("1", "true", "True")]
    if args.region:
        rows = [r for r in rows if r["region"] == args.region]

    out_path = Path(args.output)
    kept = []
    if out_path.exists():
        with open(out_path, newline="", encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
        kept = [r for r in existing if r.get("status") == "ok"]
        if len(kept) != len(existing):  # drop failed rows so this run retries them (no duplicates)
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
                w.writeheader()
                w.writerows(kept)
    done = {r["id"] for r in kept}
    rows = [r for r in rows if r["id"] not in done]
    if args.limit:
        rows = rows[: args.limit]
    print(f"{len(rows)} eligible cells to process ({len(done)} already in {out_path})")
    if not rows:
        return

    # ---- Earth Engine: authenticate, build the two annual-mean images once, smoke-test one cell
    init_ee(args.project)
    end_excl = (date.fromisoformat(args.end) + timedelta(days=1)).isoformat()  # GEE end date is exclusive
    qc = not args.no_qc
    lst, n_lst = lst_layer(args.start, end_excl, qc)
    alb, n_alb = albedo_layer(args.start, end_excl, qc)
    n_lst, n_alb = n_lst.getInfo(), n_alb.getInfo()
    print(f"{args.start} .. {args.end}: {n_lst} MOD11A2 composites, {n_alb} MCD43A3 days "
          f"(quality filter {'on' if qc else 'off'})")
    if not n_lst or not n_alb:
        sys.exit("No MODIS images in that date range.")
    try:
        cell_stats(lst, alb, float(rows[0]["lat"]), float(rows[0]["lon"]))
    except Exception as exc:
        sys.exit(f"Earth Engine test request failed: {type(exc).__name__}: {exc}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out_path.exists()
    started, ok, failed = time.time(), 0, 0
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if new_file:
            writer.writeheader()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(process, r, lst, alb) for r in rows]
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
