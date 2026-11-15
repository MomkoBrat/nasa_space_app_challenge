#!/usr/bin/env python3
"""Build a Gale Crater terrain profile using the existing mars_prep.py functions.

Place this file at prep/run_gale_terrain.py and run from the repository root:
    .\\.venv\\Scripts\\python.exe prep/run_gale_terrain.py
"""

import json
import math
from pathlib import Path

import rasterio
from pyproj import CRS, Transformer
from mars_prep import extract_region

ROOT = Path(__file__).resolve().parent.parent
DEM = ROOT / "raw_data" / "gale" / "hrsc_km09_h1938_h1927_h1916-dtm-mosaic.tif"
OUTPUT = ROOT / "data" / "gale_features.json"

SITE_ID = "gale_01"
SITE_NAME = "Gale Crater - Bradbury Landing"
LAT = -4.5895
LON_EAST = 137.4417


def main():
    if not DEM.is_file():
        raise FileNotFoundError(f"Gale elevation model not found: {DEM}")

    with rasterio.open(DEM) as ds:
        if not ds.crs or not ds.crs.is_projected:
            raise ValueError("The DEM needs a projected Mars CRS")
        if ds.crs.linear_units.lower() not in {"metre", "meter", "metres", "meters", "m"}:
            raise ValueError(f"DEM CRS must use metres, not {ds.crs.linear_units}")

        projected_crs = CRS.from_wkt(ds.crs.to_wkt())
        geographic_crs = projected_crs.geodetic_crs
        if geographic_crs is None:
            raise ValueError("Could not derive the DEM's Mars geographic coordinate system")

        # Compute x/y in the DEM's own coordinate system, not Earth's EPSG:4326.
        to_dem = Transformer.from_crs(geographic_crs, projected_crs, always_xy=True)
        to_lonlat = Transformer.from_crs(projected_crs, geographic_crs, always_xy=True)
        x, y = to_dem.transform(LON_EAST, LAT)
        derived_lon, derived_lat = to_lonlat.transform(x, y)

        if not all(math.isfinite(v) for v in (x, y, derived_lon, derived_lat)):
            raise ValueError("Projection returned non-finite coordinates")

        print(f"Site: {SITE_NAME} ({SITE_ID})")
        print(f"Reference: lat={LAT:.6f}, east lon={LON_EAST:.6f}")
        print(f"Projected DEM centre: x={x:.2f} m, y={y:.2f} m")
        print(f"Inverse-projected: lat={derived_lat:.6f}, east lon={derived_lon:.6f}")
        print(f"DEM resolution: {ds.res}, NoData: {ds.nodata}")

        if not (ds.bounds.left <= x <= ds.bounds.right and ds.bounds.bottom <= y <= ds.bounds.top):
            raise ValueError("Bradbury Landing is outside this DEM's bounds")

        # These functions check actual valid pixel coverage (>=95%) and refuse
        # to upsample a coarse DEM while claiming higher resolution.
        regional = extract_region(ds, x, y, 10.0, 460.0)
        detailed = extract_region(ds, x, y, 5.0, 30.0)

        result = {
            "id": SITE_ID,
            "name": SITE_NAME,
            "source_dem": DEM.name,
            "source_crs_wkt": ds.crs.to_wkt(),
            "source_pixel_size_m": list(map(float, ds.res)),
            "center_projected_m": {"x": x, "y": y},
            "center_geographic": {"lat": derived_lat, "lon_east": derived_lon},
            "coordinate_source": "Bradbury Landing reference; projected through source DEM CRS",
            "regional": regional,
            "detailed": detailed,
            "methods": {
                "slope": "degrees(arctan(hypot(gradient_x, gradient_y)))",
                "steep_fraction": "fraction of slope samples greater than 15 degrees",
                "relief": "elevation percentile 95 minus percentile 5, in metres",
                "roughness_m": (
                    "standard deviation of elevation minus valid-pixel-weighted "
                    "Gaussian-smoothed elevation; sigma=1000 m (verify with Earth team)"
                ),
                "resampling": "GDAL average from source DEM to analysis grid",
                "nodata": "masked; slope samples adjoining voids excluded",
            },
        }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("\nRegional terrain features:", json.dumps(regional["features"], indent=2))
    print("Detailed terrain features:", json.dumps(detailed["features"], indent=2))
    print(f"\nSaved: {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
