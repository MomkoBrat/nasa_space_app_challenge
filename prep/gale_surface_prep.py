#!/usr/bin/env python3
"""Prepare Gale Bradbury Landing geology and (optionally) mineral polygon data.

Run from repository root:
    .\\.venv\\Scripts\\python.exe prep/gale_surface_prep.py

Optional true polygon mineral classification source:
    .\\.venv\\Scripts\\python.exe prep/gale_surface_prep.py --mineral-vector raw_data/gale/mineral_classes.shp --mineral-field INTERP

The global geology layer is coarse (USGS SIM 3292, 1:20M), not equivalent to
Jezero's local USGS 1:75k map. No mineral class is invented without a source.
"""
import argparse
import json
import math
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from pyproj import CRS, Transformer
from shapely.geometry import box, shape
from shapely.ops import transform as transform_geom, unary_union

from geology_prep import arcgis_polygon

ROOT = Path(__file__).resolve().parent.parent
SITE_JSON = ROOT / 'data/gale_features.json'
OUT_DIR = ROOT / 'data/parts/gale_01'
SERVICE = ('https://services.arcgis.com/nzS0F0zdNLvs7nc8/ArcGIS/rest/'
           'services/Mars_Geology_feature_layer/FeatureServer/0')
MARS_RADIUS_M = 3396190.0
MARS_GEO = CRS.from_proj4('+proj=longlat +R=3396190 +no_defs +type=crs')


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Saved: {path.relative_to(ROOT)}')


def mars_crs(crs):
    """Check the planetary radius, not CRS display name ('unnamed' on Gale)."""
    if crs is None or not (crs.is_projected or crs.is_geographic):
        return False
    ell = crs.ellipsoid
    return (abs(ell.semi_major_metre - MARS_RADIUS_M) < 2 and
            abs(ell.semi_minor_metre - MARS_RADIUS_M) < 2)


def site_area():
    site = json.loads(SITE_JSON.read_text(encoding='utf-8'))
    if site.get('id') != 'gale_01':
        raise ValueError('Expected gale_01 terrain JSON')
    crs = CRS.from_wkt(site['source_crs_wkt'])
    if not crs.is_projected or not mars_crs(crs):
        raise ValueError('Terrain CRS is not a projected spherical Mars CRS (R=3396190 m)')
    center = site['center_projected_m']
    x, y = float(center['x']), float(center['y'])
    geo = site.get('center_geographic') or {}
    if 'lat' in geo and 'lon_east' in geo:
        tfm = Transformer.from_crs(MARS_GEO, crs, always_xy=True)
        xp, yp = tfm.transform(geo['lon_east'], geo['lat'])
        if math.hypot(x - xp, y - yp) > 100:
            raise ValueError('Geographic and projected centers disagree by over 100 metres')
    size = float(site['detailed']['region_km']) * 1000
    if not math.isclose(size, 5000.0):
        raise ValueError('Expected a 5 x 5 km Gale detailed footprint')
    roi = box(x-size/2, y-size/2, x+size/2, y+size/2)
    tfm = Transformer.from_crs(crs, MARS_GEO, always_xy=True)
    roi_geo = transform_geom(tfm.transform, roi)
    analysis = {'scale':'detailed', 'width_m':size, 'height_m':size,
                'center_projected_m': {'x':x,'y':y}}
    return crs, roi, roi_geo, analysis


def fetch_arcgis(geo_roi):
    """Retrieve only polygons intersecting the Gale footprint, in Mars lon/lat."""
    xmin, ymin, xmax, ymax = geo_roi.bounds
    features, offset = [], 0
    while True:
        params = {
            'f':'json', 'where':'1=1', 'outFields':'OBJECTID,Unit,UnitDesc',
            'geometry': json.dumps({'xmin':xmin,'ymin':ymin,'xmax':xmax,'ymax':ymax,
                                    'spatialReference':{'wkid':104971}}),
            'geometryType':'esriGeometryEnvelope', 'inSR':104971, 'outSR':104971,
            'spatialRel':'esriSpatialRelIntersects', 'returnGeometry':'true',
            'geometryPrecision':7, 'maxAllowableOffset':0.0003,
            'resultOffset':offset, 'resultRecordCount':1000,
            'orderByFields':'OBJECTID ASC',
        }
        url = SERVICE + '/query?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={'User-Agent':'Mars-Earth-Analog-Research/1.0'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.load(resp)
        if 'error' in payload:
            raise RuntimeError(f'ArcGIS query failed: {payload["error"]}')
        batch = payload.get('features', [])
        features.extend(batch)
        if not payload.get('exceededTransferLimit') and len(batch) < 1000:
            break
        if not batch:
            raise RuntimeError('ArcGIS returned no features but signaled more results')
        offset += len(batch)
        if offset > 5000:
            raise RuntimeError('Unexpectedly large map query; stopped')
    return features


def geology(site_crs, roi, roi_geo, analysis, response_json):
    if response_json:
        payload = json.loads(Path(response_json).read_text(encoding='utf-8'))
        features = payload['features'] if isinstance(payload, dict) else payload
    else:
        features = fetch_arcgis(roi_geo)
    if not isinstance(features, list) or not features:
        raise ValueError('No geology polygons returned for Gale; check the map query')
    to_local = Transformer.from_crs(MARS_GEO, site_crs, always_xy=True)
    groups = defaultdict(list)
    names = {}
    for feat in features:
        attr = feat.get('attributes') or {}
        unit = str(attr.get('Unit') or '').strip()
        rings = (feat.get('geometry') or {}).get('rings')
        if not unit or not rings:
            continue
        geom = arcgis_polygon(rings)
        if geom.is_empty:
            continue
        local_geom = transform_geom(to_local.transform, geom)
        clipped = local_geom.intersection(roi)
        if clipped.area > 0:
            groups[unit].append(clipped)
            names[unit] = attr.get('UnitDesc') or unit
    if not groups:
        raise ValueError('No valid geology polygon intersects the Gale footprint')
    entries = [
        {'unit_code':unit, 'name':names[unit],
         'fraction_of_region':round(min(1, unary_union(parts).area/roi.area), 6)}
        for unit,parts in groups.items()
    ]
    entries.sort(key=lambda row: -row['fraction_of_region'])
    covered = unary_union([g for pieces in groups.values() for g in pieces])
    coverage = min(1.0, covered.area / roi.area)
    flags = ['global_geologic_map_coarse_1_to_20_million',
             'not_equivalent_to_local_jezero_geology_map']
    if coverage < 0.90:
        flags.append('incomplete_geologic_map_coverage')
    result = {
        'location_id':'gale_01', 'category':'geology', 'analysis':analysis,
        'data_status':'processed',
        'features':{'dominant_unit':entries[0]['name'],
                    'mapped_units':entries,'mapped_fraction':round(coverage,6)},
        'quality':{'coverage_fraction':round(coverage,6),'flags':flags},
        'source':{'dataset':'USGS SIM 3292 Global Geologic Map of Mars (Tanaka et al., 2014)',
                  'url':'https://doi.org/10.3133/sim3292',
                  'feature_service':SERVICE, 'map_scale':'1:20,000,000',
                  'type':'broad_geologic_unit_interpretation'},
        'methods':{'area':'Mars geological polygons clipped to detailed site footprint in projected metres',
                   'caveat':'Global geology has insufficient resolution to resolve local Bradbury Landing units.'}
    }
    save_json(OUT_DIR/'geology.json', result)
    print('Geology:', result['features']['dominant_unit'], f'({coverage:.1%} coverage)')


def minerals(site_crs, roi, analysis, source, field, layer):
    """Only label mineral classes from true polygon classification, never RGB imagery."""
    groups = defaultdict(list)
    count = 0
    if source:
        import fiona
        kwargs = {'layer':layer} if layer else {}
        with fiona.open(source, **kwargs) as f:
            mineral_crs = CRS.from_user_input(f.crs_wkt or f.crs)
            if not mars_crs(mineral_crs):
                raise ValueError('Mineral polygons require documented Mars CRS, not Earth WGS84')
            if field not in f.schema['properties']:
                raise KeyError(f'Mineral field {field} missing. Available: {list(f.schema["properties"])}')
            tfm = Transformer.from_crs(mineral_crs, site_crs, always_xy=True)
            for feat in f:
                if not feat['geometry']:
                    continue
                label = str(feat['properties'].get(field) or '').strip()
                if not label:
                    continue
                geom = shape(feat['geometry'])
                if not geom.is_valid:
                    geom = geom.buffer(0)
                if geom.is_empty:
                    continue
                clipped = transform_geom(tfm.transform, geom).intersection(roi)
                if clipped.area > 0:
                    groups[label].append(clipped)
                    count += 1
    rows = [{'mapped_class':name,
             'fraction_of_region':round(min(1,unary_union(items).area/roi.area),6)}
            for name,items in groups.items()]
    rows.sort(key=lambda d:-d['fraction_of_region'])
    shapes = [g for parts in groups.values() for g in parts]
    cov = min(1.0, unary_union(shapes).area/roi.area) if shapes else 0.0
    flags=['mineral_class_area_is_not_mineral_abundance']
    if source is None:
        flags.append('classified_mineral_map_not_supplied')
    if cov < 0.90:
        flags.append('incomplete_mineral_map_coverage')
    result = {
        'location_id':'gale_01', 'category':'minerals', 'analysis':analysis,
        'data_status': ('processed' if rows else ('no_coverage' if source else 'not_mapped')),
        'features':{'dominant_mapped_class':rows[0]['mapped_class'] if rows else None,
                    'mapped_classes':rows,'mapped_fraction':round(cov,6)},
        'quality':{'coverage_fraction':round(cov,6),'flags':flags,
                   'intersecting_source_polygons':count},
        'source':{'dataset':'User-supplied georeferenced mineral classification polygons' if source else None,
                  'local_file':str(source) if source else None,
                  'class_field':field if source else None,
                  'type':'mapped_spectral_mineral_class' if source else 'no_source'},
        'methods':{'area':'Mineral-class polygon union clipped to 5 km site, divided by site area',
                   'caveat':'Do not treat absence of coverage as absence of minerals. RGB spectral-index composites are NOT class polygons.'}
    }
    save_json(OUT_DIR/'minerals.json',result)
    print('Minerals:',result['data_status'],f'({cov:.1%} mapped area)')


def main():
    parser = argparse.ArgumentParser(description='Prepare Gale geology and mineral polygon coverage')
    parser.add_argument('--response-json', help='Previously saved ArcGIS geology features JSON for offline testing')
    parser.add_argument('--mineral-vector', help='Optional real, classified Mars mineral polygon layer (.shp/.gpkg)')
    parser.add_argument('--mineral-field', default='INTERP')
    parser.add_argument('--mineral-layer')
    args = parser.parse_args()
    crs, roi, geo_roi, analysis = site_area()
    print('Gale center:', geo_roi.centroid.x, geo_roi.centroid.y)
    geology(crs,roi,geo_roi,analysis,args.response_json)
    minerals(crs,roi,analysis,args.mineral_vector,args.mineral_field,args.mineral_layer)
    print('Gale surface modules complete. Non-mapped minerals must not enter Stage 2 scoring.')

if __name__ == '__main__':
    main()
