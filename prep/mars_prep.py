"""Extract reproducible terrain metrics from a *projected, metric* Mars DEM.

Install: python -m pip install rasterio numpy scipy
Example: python prep/mars_prep.py raw_data/M20_JezeroCrater_CTXDEM_20m.tif --id jezero_01 --name "Jezero Crater" --output data/jezero_features.json

IMPORTANT: The roughness smoothing length (Gaussian sigma=1000 metres for
`roughness_m`) is a proposed shared convention. Agree on it with the Earth
processing team before using `roughness_m` in similarity ranking.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window
from scipy.ndimage import gaussian_filter


def local_roughness(elevation, valid, dx, dy, sigma_m):
    """SD of elevation residual against a valid-pixel weighted Gaussian surface."""
    sigma_pixels = (sigma_m / dy, sigma_m / dx)
    weights = valid.astype(np.float64)
    weighted_elevation = np.where(valid, elevation, 0.0)
    smooth_weights = gaussian_filter(weights, sigma_pixels, mode="reflect")
    smooth_sum = gaussian_filter(weighted_elevation, sigma_pixels, mode="reflect")
    smooth_elevation = smooth_sum / np.maximum(smooth_weights, 1e-12)
    return float(np.std((elevation - smooth_elevation)[valid]))


def terrain_features(elevation, dx, dy):
    """All horizontal and elevation distances are in metres."""
    valid = np.isfinite(elevation)
    coverage = float(valid.mean())
    if coverage < 0.95:
        raise ValueError(
            f"Crop has only {coverage:.1%} usable pixels (need >=95%). "
            "Choose another --center-x/--center-y inside the valid DEM area."
        )

    # np.gradient outputs NaN next to NoData, so slopes at those pixels are excluded.
    dz_dy, dz_dx = np.gradient(elevation, dy, dx)
    slope = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))
    slope_values = slope[valid & np.isfinite(slope)]
    if len(slope_values) < 0.9 * len(elevation[valid]):
        raise ValueError("Too few slope samples after excluding NoData edges.")

    z = elevation[valid]
    relief = float(np.percentile(z, 95) - np.percentile(z, 5))

    return {
        "features": {
            "median_slope_deg": float(np.median(slope_values)),
            "steep_fraction": float(np.mean(slope_values > 15.0)),
            "relief_m": relief,
            "roughness_m": local_roughness(elevation, valid, dx, dy, 1000.0),
        },
        "additional_features": {
            "mean_slope_deg": float(np.mean(slope_values)),
            "slope_p90_deg": float(np.percentile(slope_values, 90)),
            "flat_fraction": float(np.mean(slope_values < 5.0)),
            "elevation_std_m": float(np.std(z)),
            "roughness_100m_m": local_roughness(elevation, valid, dx, dy, 100.0),
            "roughness_500m_m": local_roughness(elevation, valid, dx, dy, 500.0),
        },
        "quality": {
            "valid_fraction_resampled": coverage,
            "valid_slope_fraction_resampled": float(len(slope_values) / elevation.size),
            "samples": int(elevation.size),
        },
    }


def extract_region(ds, center_x, center_y, region_km, target_resolution_m):
    """Crop the same projected centre, and average-downsample if needed."""
    size_m = region_km * 1000.0
    px_x, px_y = abs(ds.transform.a), abs(ds.transform.e)
    if abs(ds.transform.b) > 1e-9 or abs(ds.transform.d) > 1e-9:
        raise ValueError("Rotated DEM grids are not supported by this script.")
    if min(px_x, px_y) > target_resolution_m * 1.01:
        raise ValueError(
            f"DEM pixels ({px_x:g}x{px_y:g} m) are coarser than "
            f"requested {target_resolution_m:g} m output. Do not upsample and claim detail."
        )

    center_col, center_row = (~ds.transform) * (center_x, center_y)
    width = int(round(size_m / px_x))
    height = int(round(size_m / px_y))
    left = int(round(center_col - width / 2))
    top = int(round(center_row - height / 2))
    if left < 0 or top < 0 or left + width > ds.width or top + height > ds.height:
        raise ValueError(f"{region_km:g} km crop is outside the raster bounds.")

    output_w = max(3, int(round(size_m / target_resolution_m)))
    output_h = max(3, int(round(size_m / target_resolution_m)))
    window = Window(left, top, width, height)
    data = ds.read(
        1,
        window=window,
        out_shape=(output_h, output_w),
        resampling=Resampling.average,
        masked=True,
    )
    elevation = np.asarray(data.filled(np.nan), dtype=np.float64)
    dx = (width * px_x) / output_w
    dy = (height * px_y) / output_h
    stats = terrain_features(elevation, dx, dy)
    stats.update({
        "region_km": region_km,
        "grid_width": output_w,
        "grid_height": output_h,
        "effective_pixel_size_m": [round(dx, 3), round(dy, 3)],
    })
    return stats


def main():
    p = argparse.ArgumentParser(description="Extract comparable Mars DEM metrics")
    p.add_argument("dem", help="Path to an elevation GeoTIFF or GDAL-readable DEM")
    p.add_argument("--id", required=True, help="Site identifier, e.g. jezero_01")
    p.add_argument("--name", required=True, help="Site name")
    p.add_argument("--output", required=True, help="JSON output path")
    p.add_argument("--center-x", type=float, help="Site centre easting (projected metres)")
    p.add_argument("--center-y", type=float, help="Site centre northing (projected metres)")
    args = p.parse_args()
    if (args.center_x is None) != (args.center_y is None):
        p.error("Provide both --center-x and --center-y, or neither.")

    with rasterio.open(args.dem) as ds:
        if not ds.crs or not ds.crs.is_projected:
            raise ValueError("DEM must have a projected Mars CRS with metre units.")
        if ds.crs.linear_units.lower() not in ("metre", "meter", "metres", "meters", "m"):
            raise ValueError(f"Projected coordinates must be in metres, not {ds.crs.linear_units}.")
        center_x = args.center_x if args.center_x is not None else (ds.bounds.left + ds.bounds.right) / 2
        center_y = args.center_y if args.center_y is not None else (ds.bounds.bottom + ds.bounds.top) / 2
        print(f"Using projected centre: x={center_x:.1f} m, y={center_y:.1f} m")
        print(f"Source DEM pixels: {ds.res}; nodata: {ds.nodata}")
        regional = extract_region(ds, center_x, center_y, 10.0, 460.0)
        detailed = extract_region(ds, center_x, center_y, 5.0, 30.0)
        result = {
            "id": args.id,
            "name": args.name,
            "source_dem": Path(args.dem).name,
            "source_crs_wkt": ds.crs.to_wkt(),
            "source_pixel_size_m": list(map(float, ds.res)),
            "center_projected_m": {"x": center_x, "y": center_y},
            "regional": regional,
            "detailed": detailed,
            "methods": {
                "slope": "degrees(arctan(hypot(gradient_x, gradient_y)))",
                "relief": "elevation percentile 95 minus percentile 5, in metres",
                "roughness_m": "standard deviation of elevation minus valid-pixel-weighted Gaussian-smoothed elevation; sigma=1000 m (PROPOSED; coordinate with Earth team)",
                "resampling": "GDAL average from source DEM to analysis grid",
                "nodata": "masked; slope samples adjoining voids excluded",
            },
        }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print("Regional (about 460 m) core features:", json.dumps(result["regional"]["features"], indent=2))
    print("Detailed (about 30 m) core features:", json.dumps(result["detailed"]["features"], indent=2))
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
