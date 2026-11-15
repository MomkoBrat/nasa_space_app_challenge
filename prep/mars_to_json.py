"""Build frontend/public/data/mars_cells.json (DATA_CONTRACT §3 shape) from data/combined/*.json.

Scored features: the 4 regional terrain features (10 x 10 km, 22 x 22 grid, same method as Earth)
plus mean wind speed (MACDA; optional slider, default weight 0).
Everything else (thermal inertia, albedo, wind extras, pressure, geology, minerals) is copied into
`context` for display only — it is NOT used in the similarity score until Earth has matching data.

Usage: python prep/mars_to_json.py
"""

import glob
import json
import math
from pathlib import Path

COMBINED = sorted(glob.glob("data/combined/*.json"))
OUTPUT = Path("frontend/public/data/mars_cells.json")
FEATURES = ["median_slope_deg", "steep_fraction", "relief_m", "roughness_m"]
WIND = "mean_wind_speed_ms"  # 5th scored feature (optional slider, default weight 0)

# Descriptive filter categories (contract §3) — not a statement of geological certainty.
SITE_INFO = {
    "jezero_rim_01": ("crater", "Western rim of Jezero crater, explored by the Perseverance rover."),
    "gale_01": ("landing_site", "Bradbury Landing, where the Curiosity rover landed in Gale crater."),
    "victoria_crater_01": ("crater", "Victoria crater in Meridiani Planum, explored by the Opportunity rover."),
    "nili_patera_01": ("volcanic", "Nili Patera caldera in Syrtis Major, known for active dune fields."),
    "athabasca_valles_01": ("other", "Athabasca Valles, young flood channels with lava-covered plains."),
}


def lon180(lon):
    return ((lon + 180.0) % 360.0) - 180.0


def finite(v):
    return isinstance(v, (int, float)) and math.isfinite(v)


def rounded(v, nd=3):
    return round(v, nd) if finite(v) else None


def centre(d):
    """Site centre: top-level center_geographic, else the module centres (Jezero Rim has none)."""
    if "center_geographic" in d:
        return d["center_geographic"]
    m = d["modules"]
    for path in (("thermal", "analysis", "center_geographic"), ("albedo", "analysis", "center_geographic"),
                 ("wind", "analysis", "requested_center")):
        node = m
        for key in path:
            node = node.get(key, {}) if isinstance(node, dict) else {}
        if node:
            return node
    raise ValueError(f"{d['location_id']}: no centre coordinates")


def module_context(m):
    th, al, wi = m.get("thermal", {}), m.get("albedo", {}), m.get("wind", {})
    geo, mins = m.get("geology", {}), m.get("minerals", {})
    th_reg = th.get("regional", {}).get("features", th.get("features", {}))
    al_reg = al.get("regional", {}).get("features", al.get("features", {}))
    wf = wi.get("features", {})
    mf = mins.get("features", {})
    minerals = [c["mapped_class"] for c in mf.get("mapped_classes", [])] or \
               [c["mineral_class"] for c in mf.get("reported_mineral_classes", [])]
    return {
        "thermal_inertia_tiu": rounded(th_reg.get("median_ti"), 1),
        "albedo_1080nm": rounded(al_reg.get("median_albedo"), 4),
        "wind_speed_ms": rounded(wf.get("mean_wind_speed_ms"), 2),
        "wind_speed_p95_ms": rounded(wf.get("p95_wind_speed_ms"), 2),
        "wind_speed_std_ms": rounded(wf.get("wind_speed_std_ms"), 2),
        "prevailing_wind_direction_deg": rounded(wf.get("prevailing_wind_direction_deg"), 1),
        "surface_pressure_pa": rounded(wf.get("mean_surface_pressure_pa"), 1),
        "wind_source_distance_km": rounded(wi.get("analysis", {}).get("distance_from_site_km"), 1),
        "geology_dominant_unit": geo.get("features", {}).get("dominant_unit"),
        "minerals": sorted(set(minerals)),
        "module_status": {k: v.get("data_status") for k, v in m.items()},
        "scored": False,
        "note": "Context only, not scored. Exception: mean wind speed is also in `features` "
                "(scored only when its slider is above 0).",
    }


def build_site(path):
    d = json.load(open(path, encoding="utf-8"))
    sid = d["location_id"]
    reg = d["terrain"]["regional"]
    feats = {k: reg["features"][k] for k in FEATURES}
    feats[WIND] = d["modules"]["wind"]["features"]["mean_wind_speed_ms"]
    if not all(finite(v) for v in feats.values()):
        raise ValueError(f"{sid}: non-finite terrain feature {feats}")
    c = centre(d)
    lat, lon = float(c["lat"]), lon180(float(c.get("lon_east", c.get("lon"))))
    group, desc = SITE_INFO.get(sid, ("other", None))
    px = reg.get("effective_pixel_size_m") or [None]
    native = d["terrain"].get("source_pixel_size_m") or [None]

    flags = list(d.get("missing_modules", [])) + list(d.get("invalid_modules", []))
    sources = [{"dataset": d["terrain"].get("source_dem"),
                "native_resolution_m": rounded(abs(native[0]), 1) if finite(native[0]) else None,
                "url": None, "used_for": "terrain features (scored)"}]
    for name, mod in d["modules"].items():
        src = mod.get("source", {})
        sources.append({"dataset": src.get("dataset"), "native_resolution_m":
                        rounded(mod.get("analysis", {}).get("source_resolution_m"), 1),
                        "url": src.get("url"), "used_for": f"{name} (context only)"})

    return {
        "id": sid,
        "name": d["name"],
        "group": group,
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "description": desc,
        "analysis": {"window_size_m": reg.get("region_km", 10) * 1000,
                     "analysis_resolution_m": rounded(px[0], 1)},
        "features": {k: round(v, 4) for k, v in feats.items()},
        "quality": {"coverage_fraction": reg["quality"]["valid_fraction_resampled"],
                    "flags": flags, "data_status": "processed"},
        "sources": sources,
        "context": module_context(d["modules"]),
        "limitations": d.get("scientific_limitations", []),
        "image_url": None,
        "detail_available": False,
    }


def main():
    if not COMBINED:
        raise SystemExit("No data/combined/*.json files found.")
    sites = [build_site(p) for p in COMBINED]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"schema_version": "1.0", "sites": sites}, indent=2,
                                 ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(f"Wrote {len(sites)} Mars sites -> {OUTPUT}")
    for s in sites:
        print(f"  {s['id']:20} {s['group']:12} lat {s['lat']:9.4f} lon {s['lon']:9.4f}  {s['features']}")


if __name__ == "__main__":
    main()
