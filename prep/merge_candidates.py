"""Merge the batch exports of step 1 into data/earth_candidates.csv.

Reads data/earth_candidates.csv (existing cells, e.g. the v1 regions) plus every
data/earth_candidates_b*.csv, keeps one row per cell id (a batch file wins over the existing
row), checks the columns, and writes data/earth_candidates.csv again. Safe to run repeatedly.

Usage: python prep/merge_candidates.py
"""

import csv
from collections import Counter
from pathlib import Path

DATA = Path("data")
MAIN = DATA / "earth_candidates.csv"
COLUMNS = ["id", "region", "lat", "lon", "half_height_deg", "half_width_deg",
           "nonvegetated_fraction", "barren_fraction", "excluded_landcover_fraction",
           "dem_coverage_fraction", "missing_data", "eligible"]


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"{path}: missing columns {missing}")
        return [{c: r[c] for c in COLUMNS} for r in reader]


def main():
    batches = sorted(DATA.glob("earth_candidates_b*.csv"))
    if not batches:
        raise SystemExit("No data/earth_candidates_b*.csv files found.")

    merged = {}
    if MAIN.exists():
        for r in read(MAIN):
            merged[r["id"]] = r
        print(f"{MAIN}: {len(merged)} existing cells")
    for path in batches:
        rows = read(path)
        merged.update({r["id"]: r for r in rows})
        print(f"{path}: {len(rows)} cells, regions {sorted({r['region'] for r in rows})}")

    rows = sorted(merged.values(), key=lambda r: r["id"])
    with open(MAIN, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    eligible = Counter(r["region"] for r in rows if r["eligible"].strip() in ("1", "true", "True"))
    total = Counter(r["region"] for r in rows)
    print(f"\nWrote {len(rows)} cells -> {MAIN}")
    for region in sorted(total):
        print(f"  {region:14} {eligible[region]:5} / {total[region]:5} eligible")
    print(f"  {'TOTAL':14} {sum(eligible.values()):5} / {len(rows):5} eligible")


if __name__ == "__main__":
    main()
