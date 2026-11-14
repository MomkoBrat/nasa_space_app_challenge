"""Query official USGS Jezero geologic-unit polygons; calculate actual areal coverage.

Install: python -m pip install shapely pyproj
Example:
  python prep/geology_prep.py --site-json data/jezero_features.json --output data/parts/jezero_01/geology.json

Requires internet unless --response-json points to a previously saved ArcGIS response.
"""
import argparse
import json
import urllib.parse
import urllib.request
from collections import defaultdict

from shapely.geometry import Polygon
from shapely.ops import unary_union
from site_geometry import JZ_GEOLOGY_CRS, read_site, transform_shape, save_json

SERVICE = ('https://services.arcgis.com/v01gqwM5QqNysAAi/ArcGIS/rest/services/'
           'Jezero_FeatureServiceFromPro/FeatureServer/8')
SOURCE = 'Sun and Stack (2020), USGS SIM 3464 geologic units'


def signed_area(ring):
    return 0.5 * sum(x1*y2 - x2*y1 for (x1,y1),(x2,y2) in
                     zip(ring, ring[1:] + ring[:1]))


def arcgis_polygon(rings):
    # ArcGIS rings convention: clockwise outer boundaries, counterclockwise holes.
    shells, holes = [], []
    for r in rings:
        if len(r) < 4:
            continue
        poly = Polygon(r)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            continue
        (shells if signed_area(r) < 0 else holes).append(poly)
    if not shells:
        raise ValueError('Unrecognized ArcGIS ring orientation; cannot safely calculate areas.')
    result = unary_union(shells)
    if holes:
        result = result.difference(unary_union(holes))
    return result


def fetch_features(window):
    all_features = []
    offset = 0
    while True:
        params = {
            'f':'json', 'where':'1=1', 'outFields':'unit,name,Unit_Description,Unit_Interpretation',
            'geometry': json.dumps({'xmin':window.bounds[0], 'ymin':window.bounds[1],
                                    'xmax':window.bounds[2], 'ymax':window.bounds[3]}),
            'geometryType':'esriGeometryEnvelope', 'spatialRel':'esriSpatialRelIntersects',
            'returnGeometry':'true', 'resultOffset':offset, 'resultRecordCount':1000,
            'orderByFields':'OBJECTID ASC',
        }
        url = SERVICE + '/query?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={'User-Agent':'NASA-Space-Apps-Scientific-Project/1.0'})
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.load(resp)
        if 'error' in payload:
            raise RuntimeError(f'USGS ArcGIS service error: {payload["error"]}')
        batch = payload.get('features', [])
        all_features.extend(batch)
        if not payload.get('exceededTransferLimit') and len(batch) < 1000:
            break
        if not batch:
            raise RuntimeError('Service claims more results but returned no features.')
        offset += len(batch)
        if offset > 30000:
            raise RuntimeError('Query unexpectedly large; aborting to avoid incomplete result.')
    return all_features


def analyze(features, roi):
    clipped_by_code = defaultdict(list)
    labels, descriptions, interpretations = {}, {}, {}
    for feature in features:
        a = feature.get('attributes', {})
        code = str(a.get('unit') or '').strip()
        rings = (feature.get('geometry') or {}).get('rings')
        if not code or not rings:
            continue
        poly = arcgis_polygon(rings)
        intersected = poly.intersection(roi)
        if not intersected.is_empty and intersected.area > 0:
            clipped_by_code[code].append(intersected)
            labels[code] = a.get('name') or code
            descriptions[code] = a.get('Unit_Description')
            interpretations[code] = a.get('Unit_Interpretation')
    groups = []
    for code, polys in clipped_by_code.items():
        area = unary_union(polys).area
        groups.append({'unit_code': code, 'name': labels[code],
                       'fraction_of_region': round(min(1.0, area / roi.area), 6),
                       'description': descriptions.get(code),
                       'interpretation': interpretations.get(code)})
    groups.sort(key=lambda x: -x['fraction_of_region'])
    union = unary_union([p for arr in clipped_by_code.values() for p in arr]) if clipped_by_code else None
    coverage = min(1.0, union.area / roi.area) if union else 0.0
    return groups, coverage


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--site-json', required=True, help='Existing Jezero terrain JSON')
    p.add_argument('--scale', choices=['detailed','regional'], default='detailed')
    p.add_argument('--output', required=True)
    p.add_argument('--response-json', help='Previously saved ArcGIS JSON response (offline)')
    p.add_argument('--save-response', help='Optional raw GIS response cache path')
    args = p.parse_args()
    site_id, site_crs, site_roi, analysis = read_site(args.site_json, args.scale)
    geo_roi = transform_shape(site_roi, site_crs, JZ_GEOLOGY_CRS)
    if args.response_json:
        with open(args.response_json, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        features = raw.get('features', raw) if isinstance(raw, dict) else raw
    else:
        features = fetch_features(geo_roi)
    if args.save_response:
        save_json(args.save_response, {'features':features})
    units, cov = analyze(features, geo_roi)
    flags = []
    if cov < 0.90:
        flags.append('incomplete_geologic_map_coverage')
    result = {
        'location_id': site_id, 'category':'geology', 'analysis':analysis,
        'data_status': 'processed' if cov > 0 else 'no_coverage',
        'features':{'dominant_unit':units[0]['name'] if units else None,
                    'mapped_units':units, 'mapped_fraction':round(cov, 6)},
        'quality':{'coverage_fraction':round(cov, 6),'flags':flags},
        'source':{'dataset':SOURCE,'url':'https://doi.org/10.3133/sim3464',
                  'feature_service':SERVICE, 'type':'mapped_geologic_interpretation'},
        'methods':{'area': 'Projected polygons clipped to site footprint; intersection areas divided by site area',
                   'caveat':'Geologic unit is mapped interpretation, not measured mineral composition.'},
    }
    save_json(args.output, result)
    print(f'Mapped fraction: {cov:.1%}, dominant: {result["features"]["dominant_unit"]}')

if __name__ == '__main__':
    main()
