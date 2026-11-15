#!/usr/bin/env python3
r"""Victoria Crater terrain: 10 km NASA MOLA + 5 km NASA HiRISE DTM.

From project root (Windows PowerShell):
  .\.venv\Scripts\python.exe prep/run_victoria_terrain.py --download

This downloads a ~130 MB MOLA tile and ~360 MB official HiRISE stereo DTM.
For a quicker coarse-only baseline (NOT adequate to resolve crater walls):
  .\.venv\Scripts\python.exe prep/run_victoria_terrain.py --download --mola-only

The 5-km HiRISE crop must have >=95% valid coverage and is downsampled to 30 m.
No 30-m precision is claimed when --mola-only is used.
"""

import argparse
import json
import math
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.windows import Window
from mars_prep import terrain_features

ROOT = Path(__file__).resolve().parent.parent
SITE_ID, SITE_NAME = 'victoria_crater_01', 'Victoria Crater'
SITE_LAT, SITE_LON_E = -2.05, 354.5  # -5.5 degrees = 354.5 degrees east
MARS_RADIUS_M = 3396190.0

MOLA_FILE = 'megt00n270hb.img'
MOLA_URL = ('https://pds-geosciences.wustl.edu/mgs/'
            'urn-nasa-pds-mgs_mola_topography_derived/meg128/' + MOLA_FILE)
MOLA_PATH = ROOT / 'raw_data' / 'victoria_crater' / MOLA_FILE
MOLA_ROWS, MOLA_COLS = 5632, 11520  # 0N to 44S; 270E to 360E, 128 px/deg
MOLA_BYTES = MOLA_ROWS * MOLA_COLS * 2

HIRISE_FILE = 'DTEEC_021747_1780_022380_1780_U01.IMG'
HIRISE_URL = ('https://hirise.lpl.arizona.edu/PDS/DTM/ESP/'
              'ORB_021700_021799/ESP_021747_1780_ESP_022380_1780/' + HIRISE_FILE)
HIRISE_PATH = ROOT / 'raw_data' / 'victoria_crater' / HIRISE_FILE
HIRISE_BYTES = 360364324  # Official HiRISE archive listing; PDS3 attached-label IMG

GEO_CRS = CRS.from_proj4(f'+proj=longlat +R={MARS_RADIUS_M} +type=crs')


def analysis_crs():
    """A unified, local, Mars-metric CRS for all geology/mineral footprints."""
    c = CRS.from_proj4(
        f'+proj=eqc +lat_ts={SITE_LAT} +lon_0=0 +R={MARS_RADIUS_M} '
        '+units=m +no_defs +type=crs')
    wkt = c.to_wkt(version='WKT1_GDAL').replace(
        'PROJCS["unknown"', 'PROJCS["Mars_Victoria_Crater_local_EQC"', 1)
    return CRS.from_wkt(wkt)


def download(url, path, expected_size):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size == expected_size:
        print(f'Already downloaded: {path.name} ({expected_size / 1e6:.1f} MB)')
        return
    tmp = path.with_suffix(path.suffix + '.partial')
    start = tmp.stat().st_size if tmp.exists() else 0
    request = urllib.request.Request(url, headers={
        'User-Agent': 'NASA-Space-Apps-Analog/1.0',
        **({'Range': f'bytes={start}-'} if start else {}),
    })
    print(f'Downloading {path.name} ({expected_size / 1e6:.1f} MB)...', flush=True)
    with urllib.request.urlopen(request, timeout=120) as response:
        resume = start > 0 and response.status == 206
        offset = start if resume else 0
        with tmp.open('ab' if resume else 'wb') as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                offset += len(chunk)
                if offset // (32 * 1024 * 1024) != (offset - len(chunk)) // (32 * 1024 * 1024):
                    print(f'  {offset / 1e6:.1f} MB downloaded', flush=True)
    if tmp.stat().st_size != expected_size:
        raise RuntimeError(f'Incomplete {path.name}: received {tmp.stat().st_size:,} '
                           f'bytes; expected {expected_size:,}. Rerun --download to resume.')
    tmp.replace(path)
    print('Saved:', path)


def mola_subset(array, center_x, center_y, km):
    """Crop pixel centres from NASA's original spherical Mars grid; no upsampling."""
    m_per_degree = MARS_RADIUS_M * math.pi / 180
    dx = m_per_degree * math.cos(math.radians(SITE_LAT)) / 128
    dy = m_per_degree / 128
    # CRS normalizes longitude 354.5E to -5.5E. The source tile 270E..360E
    # is equivalent to -90E..0E. Use source left longitude -90E accordingly.
    left_x = -90 * m_per_degree * math.cos(math.radians(SITE_LAT))
    half = km * 500.0
    # Source pixel centres are left+(j+0.5)*dx and top-(i+0.5)*dy.
    c0 = max(0, math.ceil((center_x - half - left_x) / dx - .5))
    c1 = min(MOLA_COLS-1, math.floor((center_x + half - left_x) / dx - .5))
    r0 = max(0, math.ceil((-center_y - half) / dy - .5))
    r1 = min(MOLA_ROWS-1, math.floor((-center_y + half) / dy - .5))
    if (c0 >= c1 or r0 >= r1 or c0 < 0 or r0 < 0
            or c1 >= MOLA_COLS or r1 >= MOLA_ROWS):
        raise ValueError('Victoria crop outside expected MOLA tile')
    elevation = np.array(array[r0:r1+1, c0:c1+1], dtype='float64')
    elevation[elevation <= -32768] = np.nan
    stats = terrain_features(elevation, dx, dy)
    stats.update({
        'region_km': float(km),
        'grid_width': int(elevation.shape[1]),
        'grid_height': int(elevation.shape[0]),
        'effective_pixel_size_m': [round(dx, 3), round(dy, 3)],
        'source_dem': MOLA_FILE,
        'quality_note': 'MOLA ~460 m pixels cannot resolve Victoria Crater walls/rim (~800 m diameter).',
    })
    print(f'MOLA {km:g} km: {elevation.shape[1]}x{elevation.shape[0]} at ~460 m')
    return stats


def hirise_subset(path):
    """Verify an actual 5 km square coverage before claiming 30 m detail."""
    with rasterio.open(path) as ds:
        if ds.count < 1 or not ds.crs or not ds.crs.is_projected:
            raise ValueError('HiRISE IMG lacks a readable projected Mars CRS')
        if any(abs(r) > 100 for r in ds.res) or min(abs(ds.res[0]), abs(ds.res[1])) > 30.3:
            raise ValueError(f'Unexpected HiRISE DTM pixel size: {ds.res}')
        src_crs = CRS.from_wkt(ds.crs.to_wkt())
        if abs(src_crs.ellipsoid.semi_major_metre - MARS_RADIUS_M) > 1000:
            raise ValueError('HiRISE DTM appears not to use Mars coordinates')
        trans = Transformer.from_crs(src_crs.geodetic_crs, src_crs, always_xy=True)
        # Some archives wrap longitudes to [-180,180); check both equivalents.
        candidates = [trans.transform(lon, SITE_LAT) for lon in (SITE_LON_E, SITE_LON_E - 360)]
        matches = [xy for xy in candidates if ds.bounds.left <= xy[0] <= ds.bounds.right
                   and ds.bounds.bottom <= xy[1] <= ds.bounds.top]
        if not matches:
            raise ValueError(f'Victoria center not in HiRISE DTM bounds: {ds.bounds}')
        cx, cy = matches[0]
        dx, dy = abs(ds.transform.a), abs(ds.transform.e)
        if abs(ds.transform.b) > 1e-7 or abs(ds.transform.d) > 1e-7:
            raise ValueError('Rotated DTM grid not supported')
        x0, y0 = (~ds.transform) * (cx, cy)
        # Even if source cover is larger, read precisely a 5 km square.
        width = round(5000 / dx)
        height = round(5000 / dy)
        left, top = round(x0 - width / 2), round(y0 - height / 2)
        if left < 0 or top < 0 or left+width > ds.width or top+height > ds.height:
            raise ValueError('HiRISE DTM does not fully cover the 5 km square. '
                             'Use the larger Victoria DTM, or --mola-only.')
        out_w = max(3, round(width * dx / 30))
        out_h = max(3, round(height * dy / 30))
        elevation = ds.read(1, window=Window(left, top, width, height),
                            out_shape=(out_h, out_w), resampling=Resampling.average,
                            masked=True)
        z = np.asarray(elevation.filled(np.nan), dtype='float64')
        z[(abs(z) > 1e8) | (~np.isfinite(z))] = np.nan
        px, py = width * dx / out_w, height * dy / out_h
        stats = terrain_features(z, px, py)  # Requires >=95% actual valid data.
        stats.update({
            'region_km': 5.0, 'grid_width': out_w, 'grid_height': out_h,
            'effective_pixel_size_m': [round(px, 3), round(py, 3)],
            'source_dem': path.name,
            'quality_note': 'Real HiRISE stereo DTM, averaged to 30 m; not upsampled MOLA.',
        })
        print(f'HiRISE 5 km: {out_w}x{out_h} at {px:.2f}x{py:.2f} m; '
              f'valid={stats["quality"]["valid_fraction_resampled"]:.1%}')
        return stats, list(map(float, ds.res)), ds.crs.to_wkt()


def main():
    p = argparse.ArgumentParser(description='Produce Victoria Crater Mars terrain profile')
    p.add_argument('--download', action='store_true', help='Download required official imagery')
    p.add_argument('--mola-only', action='store_true',
                   help='Use native coarse MOLA for both windows; crater relief unresolved')
    p.add_argument('--mola-path', type=Path, default=MOLA_PATH)
    p.add_argument('--hirise-path', type=Path, default=HIRISE_PATH)
    p.add_argument('--output', type=Path, default=ROOT/'data/victoria_crater_features.json')
    args = p.parse_args()
    if args.download:
        download(MOLA_URL, args.mola_path, MOLA_BYTES)
        if not args.mola_only:
            download(HIRISE_URL, args.hirise_path, HIRISE_BYTES)
    if not args.mola_path.exists():
        p.error(f'Missing MOLA file {args.mola_path}. Use --download')
    if args.mola_path.stat().st_size != MOLA_BYTES:
        raise ValueError('MOLA tile has incorrect byte size; redownload it')
    if not args.mola_only and not args.hirise_path.exists():
        p.error(f'Missing HiRISE DTM {args.hirise_path}. Use --download or --mola-only')

    crs = analysis_crs()
    x, y = Transformer.from_crs(GEO_CRS, crs, always_xy=True).transform(SITE_LON_E, SITE_LAT)
    print(f'Using Victoria center: {SITE_LAT:.4f} N, {SITE_LON_E:.4f} E (= -5.5 E)')
    mola = np.memmap(args.mola_path, dtype='>i2', mode='r', shape=(MOLA_ROWS, MOLA_COLS))
    regional = mola_subset(mola, x, y, 10)
    if args.mola_only:
        detailed = mola_subset(mola, x, y, 5)
        source_dem = MOLA_FILE
        resolution = regional['effective_pixel_size_m']
        source_dtm_crs = None
    else:
        detailed, resolution, source_dtm_crs = hirise_subset(args.hirise_path)
        source_dem = HIRISE_FILE

    result = {
        'id': SITE_ID, 'name': SITE_NAME, 'source_dem': source_dem,
        'source_crs_wkt': crs.to_wkt(version='WKT1_GDAL'),
        'source_pixel_size_m': resolution,
        'center_projected_m': {'x': x, 'y': y},
        'center_geographic': {'lat': SITE_LAT, 'lon_east': SITE_LON_E},
        'coordinate_source': 'Shared TI/albedo center -2.05N, -5.5E (354.5E)',
        'regional': regional, 'detailed': detailed,
        'methods': {
            'slope': 'degrees(arctan(hypot(gradient_x, gradient_y)))',
            'steep_fraction': 'fraction of slope samples greater than 15 degrees',
            'relief': 'elevation percentile 95 minus percentile 5, in metres',
            'roughness_m': 'SD of elevation minus valid-weighted Gaussian-smoothed elevation; sigma=1000 m, matching mars_prep.py',
            'resampling': ('10km: native MOLA (~460m); 5km: HiRISE DTM average downsampling to ~30m'
                           if not args.mola_only else '10km and 5km: native MOLA (~460m) only'),
            'nodata': 'HiRISE raster mask plus extreme missing values; MOLA -32768 masked',
            'native_source_grid': 'MOLA 0N-44S, 270E-360E, big-endian signed int16; 128 pixels/degree',
            'resolution_limit': ('10km: MOLA ~460m; 5km: actual HiRISE ~1m source sampled at 30m'
                                 if not args.mola_only else
                                 'Both windows are MOLA ~460m; Victoria crater walls/rim unresolved, NOT 30m terrain'),
            'source_dem_crs_wkt': source_dtm_crs,
            'site_metric_crs_note': 'source_crs_wkt is the shared Mars site-analysis EQC CRS used for geometry, not the HiRISE source projection.',
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print('Regional terrain:', json.dumps(regional['features'], indent=2))
    print('Detailed terrain:', json.dumps(detailed['features'], indent=2))
    print('Saved:', args.output)


if __name__ == '__main__':
    main()
