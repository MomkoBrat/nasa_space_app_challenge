#!/usr/bin/env python3
r"""Generate a geologic-unit JSON for Nili Patera's fixed 5 x 5 km site.

Requires the Nili MOLA terrain JSON (from prep/run_nili_terrain.py),
Shapely and pyproj. Uses the *global* USGS SIM 3292 map, not a Jezero map.

From repository root (Windows PowerShell):
  .\.venv\Scripts\python.exe prep/nili_geology_prep.py

Optionally cache the downloaded ArcGIS features for reproducibility:
  .\.venv\Scripts\python.exe prep/nili_geology_prep.py --save-response data/nili_geology_source_response.json

Offline re-run with a saved cache:
  .\.venv\Scripts\python.exe prep/nili_geology_prep.py --response-json data/nili_geology_source_response.json
"""

import argparse
import json
import math
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from pyproj import CRS, Transformer
from shapely.geometry import box
from shapely.ops import transform as transform_geom, unary_union

from geology_prep import arcgis_polygon  # Existing helper for native ArcGIS polygon rings.

ROOT = Path(__file__).resolve().parent.parent
SITE_ID = 'nili_patera_01'
SITE_LAT = 8.9
SITE_LON = 67.2
MARS_RADIUS_M = 3396190.0
TERRAIN_PATH = ROOT / 'data/nili_patera_features.json'
OUTPUT_PATH = ROOT / 'data/parts/nili_patera_01/geology.json'
SERVICE = ('https://services.arcgis.com/nzS0F0zdNLvs7nc8/ArcGIS/rest/'
           'services/Mars_Geology_feature_layer/FeatureServer/0')
MARS_GEO = CRS.from_proj4('+proj=longlat +R=3396190 +no_defs +type=crs')


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Saved: {path.relative_to(ROOT)}')


def site_footprint(scale):
    if not TERRAIN_PATH.is_file():
        raise FileNotFoundError(f'Missing terrain JSON: {TERRAIN_PATH}')
    terrain = json.loads(TERRAIN_PATH.read_text(encoding='utf-8'))
    if terrain.get('id') != SITE_ID:
        raise ValueError(f'Expected terrain ID {SITE_ID}')
    geo = terrain.get('center_geographic') or {}
    lat, lon = float(geo['lat']), float(geo['lon_east'])
    if abs(lat - SITE_LAT) > 1e-5 or abs(lon - SITE_LON) > 1e-5:
        raise ValueError('Nili terrain JSON is not centered at 8.9N, 67.2E')
    site_crs = CRS.from_wkt(terrain['source_crs_wkt'])
    if not site_crs.is_projected:
        raise ValueError('Nili terrain coordinates are not projected metres')
    ell = site_crs.ellipsoid
    if (abs(ell.semi_major_metre - MARS_RADIUS_M) > 2 or
            abs(ell.semi_minor_metre - MARS_RADIUS_M) > 2):
        raise ValueError('DEM projection is not a spherical Mars CRS with R=3396190m')
    x = float(terrain['center_projected_m']['x'])
    y = float(terrain['center_projected_m']['y'])
    from_geo = Transformer.from_crs(MARS_GEO, site_crs, always_xy=True)
    xp, yp = from_geo.transform(lon, lat)
    if math.hypot(x - xp, y - yp) > 100:
        raise ValueError('Projected and geographic centres disagree (>100m)')
    size = float(terrain[scale]['region_km']) * 1000.0
    if not math.isclose(size, 5000 if scale == 'detailed' else 10000):
        raise ValueError(f'Unexpected {scale} footprint size: {size}m')
    site_roi = box(x - size / 2, y - size / 2, x + size / 2, y + size / 2)
    to_geo = Transformer.from_crs(site_crs, MARS_GEO, always_xy=True)
    geo_roi = transform_geom(to_geo.transform, site_roi)
    analysis = {
        'scale': scale, 'width_m': size, 'height_m': size,
        'center_projected_m': {'x': x, 'y': y},
    }
    return site_crs, site_roi, geo_roi, analysis


def fetch_features(geo_roi):
    xmin, ymin, xmax, ymax = geo_roi.bounds
    collected = []
    offset = 0
    while True:
        params = {
            'f': 'json', 'where': '1=1', 'outFields': 'OBJECTID,Unit,UnitDesc',
            'geometry': json.dumps({
                'xmin': xmin, 'ymin': ymin, 'xmax': xmax, 'ymax': ymax,
                'spatialReference': {'wkid': 104971},
            }),
            'geometryType': 'esriGeometryEnvelope',
            'inSR': 104971, 'outSR': 104971,
            'spatialRel': 'esriSpatialRelIntersects',
            'returnGeometry': 'true', 'geometryPrecision': 7,
            'resultOffset': offset, 'resultRecordCount': 1000,
            'orderByFields': 'OBJECTID ASC',
        }
        req = urllib.request.Request(
            SERVICE + '/query?' + urllib.parse.urlencode(params),
            headers={'User-Agent': 'NASA-Space-Apps-Mars-Analog/1.0'},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.load(resp)
        if 'error' in payload:
            raise RuntimeError(f'USGS ArcGIS error: {payload["error"]}')
        batch = payload.get('features', [])
        collected.extend(batch)
        if not payload.get('exceededTransferLimit') and len(batch) < 1000:
            return collected
        if not batch:
            raise RuntimeError('ArcGIS pagination ended without delivering advertised features')
        offset += len(batch)
        if offset > 5000:
            raise RuntimeError('Unexpectedly large response; stop to avoid incomplete data')


def process(features, site_crs, site_roi, analysis):
    groups = defaultdict(list)
    names = {}
    to_local = Transformer.from_crs(MARS_GEO, site_crs, always_xy=True)
    for feature in features:
        attrs = feature.get('attributes') or {}
        unit = str(attrs.get('Unit') or '').strip()
        rings = (feature.get('geometry') or {}).get('rings')
        if not unit or not rings:
            continue
        geometry = arcgis_polygon(rings)
        if geometry.is_empty:
            continue
        clipped = transform_geom(to_local.transform, geometry).intersection(site_roi)
        if clipped.is_empty or clipped.area <= 0:
            continue
        groups[unit].append(clipped)
        names[unit] = attrs.get('UnitDesc') or unit
    if not groups:
        raise RuntimeError('No USGS geology units overlap the Nili footprint; refusing to invent geology')
    mapped_units = [{
        'unit_code': code,
        'name': names[code],
        'fraction_of_region': round(min(1.0, unary_union(polys).area / site_roi.area), 6),
    } for code, polys in groups.items()]
    mapped_units.sort(key=lambda item: -item['fraction_of_region'])
    union = unary_union([p for polylist in groups.values() for p in polylist])
    coverage = min(1.0, union.area / site_roi.area)
    flags = ['global_geologic_map_coarse_1_to_20_million',
             'not_equivalent_to_local_geologic_mapping']
    if coverage < .9:
        flags.append('incomplete_geologic_map_coverage')
    return {
        'location_id': SITE_ID,
        'category': 'geology',
        'analysis': analysis,
        'data_status': 'processed',
        'features': {
            'dominant_unit': mapped_units[0]['name'],
            'mapped_units': mapped_units,
            'mapped_fraction': round(coverage, 6),
        },
        'quality': {'coverage_fraction': round(coverage, 6), 'flags': flags},
        'source': {
            'dataset': 'USGS SIM 3292 Global Geologic Map of Mars (Tanaka et al., 2014)',
            'url': 'https://doi.org/10.3133/sim3292',
            'feature_service': SERVICE,
            'map_scale': '1:20,000,000',
            'type': 'broad_geologic_unit_interpretation',
        },
        'methods': {
            'area': 'USGS Mars geological polygons transformed to the site metric CRS; clipped to the footprint; area fraction computed',
            'caveat': 'Global geology cannot resolve local lava/silica exposures at 5km scale. Do not equate global USGS codes with detailed local Nili Patera geological units.',
        },
    }


def main():
    parser = argparse.ArgumentParser(description='Generate mapped USGS geology statistics for Nili Patera')
    parser.add_argument('--scale', choices=('detailed', 'regional'), default='detailed')
    parser.add_argument('--response-json', help='Saved ArcGIS features JSON for offline regeneration')
    parser.add_argument('--save-response', help='Optionally cache downloaded ArcGIS features JSON')
    args = parser.parse_args()
    site_crs, site_roi, geo_roi, analysis = site_footprint(args.scale)
    print(f'Nili center: {SITE_LAT:.4f}N, {SITE_LON:.4f}E; analysis: {args.scale}')
    if args.response_json:
        saved = json.loads(Path(args.response_json).read_text(encoding='utf-8'))
        features = saved['features'] if isinstance(saved, dict) else saved
    else:
        features = fetch_features(geo_roi)
    if args.save_response:
        save_json(Path(args.save_response), {'features': features})
    result = process(features, site_crs, site_roi, analysis)
    save_json(OUTPUT_PATH, result)
    print(f'Dominant geology: {result["features"]["dominant_unit"]}')
    print(f'Mapped coverage: {result["features"]["mapped_fraction"]:.2%}')
    print('Note: USGS global map is coarse; local Nili rock classes are not resolved.')


if __name__ == '__main__':
    main()
