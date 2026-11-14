"""Measure coverage of independently published mineral-class polygons inside a Mars site.

Expects a *georeferenced* polygon layer from the 1.3 MB Zenodo Jezero western-rim core ZIP.
It deliberately DOES NOT convert mapped class coverage to mineral concentration.

Install: python -m pip install fiona shapely pyproj
Inspect: python prep/minerals_prep.py --vector raw_data/jezero_minerals/some_file.shp --inspect
Run:     python prep/minerals_prep.py --site-json data/jezero_features.json \\
             --vector raw_data/jezero_minerals/some_file.shp --field INTERP \\
             --output data/parts/jezero_01/minerals.json
"""
import argparse
from collections import defaultdict
from pathlib import Path

import fiona
from pyproj import CRS
from shapely.geometry import shape
from shapely.ops import unary_union
from site_geometry import read_site, transform_shape, save_json

SOURCE_URL = 'https://zenodo.org/records/22257754'


def run():
    p = argparse.ArgumentParser()
    p.add_argument('--site-json', help='Existing Mars terrain JSON; required unless --inspect')
    p.add_argument('--scale', choices=['detailed','regional'], default='detailed')
    p.add_argument('--vector', required=True, help='Actual vector polygon file, such as .shp/.gpkg')
    p.add_argument('--layer', help='Optional layer name for multilayer formats')
    p.add_argument('--field', default='INTERP', help='Real mineral class attribute in source file')
    p.add_argument('--output', help='Output JSON; required unless --inspect')
    p.add_argument('--inspect', action='store_true', help='Print source columns/CRS and exit')
    p.add_argument('--source-url', default=SOURCE_URL)
    args = p.parse_args()
    if not args.inspect and (not args.site_json or not args.output):
        p.error('--site-json and --output required unless --inspect')
    kwargs = {'layer': args.layer} if args.layer else {}
    with fiona.open(args.vector, **kwargs) as src:
        print('Source geometry:', src.schema.get('geometry'))
        print('Source fields:', list(src.schema.get('properties', {})))
        print('Source CRS:', src.crs_wkt or src.crs)
        print('Features:', len(src))
        if args.inspect:
            for idx, feat in enumerate(src):
                print('Sample properties:', dict(feat['properties']))
                if idx == 1:
                    break
            return
        src_crs = CRS.from_user_input(src.crs_wkt or src.crs)
        # Published CRISM polygons use geographic Mars lon/lat; the terrain DEM
        # uses projected Mars metres. Both are valid and handled by transform_shape.
        if not (src_crs.is_geographic or src_crs.is_projected) or 'mars' not in src_crs.to_wkt().lower():
            raise ValueError('Mineral layer must have a documented geographic or projected Mars CRS (not Earth WGS84).')
        if src.schema['geometry'] not in ('Polygon', 'MultiPolygon', '3D Polygon', '3D MultiPolygon', 'Unknown'):
            raise ValueError('Mineral class layer must contain polygons.')
        if args.field not in src.schema['properties']:
            raise KeyError(f'Field {args.field!r} is absent. Run --inspect to see real column names.')
        site_id, site_crs, roi, analysis = read_site(args.site_json, args.scale)
        categories = defaultdict(list)
        included = 0
        for feature in src:
            if not feature['geometry']:
                continue
            label = feature['properties'].get(args.field)
            if label is None or str(label).strip() == '':
                continue
            geom = shape(feature['geometry'])
            if geom.is_empty:
                continue
            if not geom.is_valid:
                geom = geom.buffer(0)
            if geom.is_empty:
                continue
            projected = transform_shape(geom, src_crs, site_crs)
            overlap = projected.intersection(roi)
            if overlap.is_empty or overlap.area == 0:
                continue
            categories[str(label).strip()].append(overlap)
            included += 1
    rows = []
    for label, geometries in categories.items():
        rows.append({'mapped_class':label,
                     'fraction_of_region':round(min(1.0, unary_union(geometries).area / roi.area),6)})
    rows.sort(key=lambda r:-r['fraction_of_region'])
    union = unary_union([g for group in categories.values() for g in group]) if categories else None
    mapped_fraction = min(1.0, union.area / roi.area) if union else 0.0
    flags = ['mineral_class_area_is_not_mineral_abundance']
    if not rows:
        flags.append('no_intersection_with_mineral_polygons')
    if mapped_fraction < 0.9:
        flags.append('incomplete_mineral_map_coverage')
    result = {
        'location_id':site_id, 'category':'minerals', 'analysis':analysis,
        'data_status':'processed' if rows else 'no_coverage',
        'features':{'dominant_mapped_class':rows[0]['mapped_class'] if rows else None,
                    'mapped_classes':rows, 'mapped_fraction':round(mapped_fraction,6)},
        'quality':{'coverage_fraction':round(mapped_fraction,6), 'flags':flags,
                   'intersecting_source_polygons':included},
        'source':{'dataset':'Jezero Western Rim Mineral Maps (CRISM; Valantinas et al.)',
                  'url':args.source_url,'local_file':Path(args.vector).name,
                  'class_field':args.field, 'type':'mapped_spectral_mineral_class'},
        'methods':{'area':'Mapped class polygon area intersecting the actual site footprint',
                   'caveat': 'Mineral class coverage is not abundance or percentage by weight. '
                             'Zero overlap is unknown/not covered, NOT proof mineral is absent.'},
    }
    save_json(args.output, result)
    print(f'Mineral-class map coverage: {mapped_fraction:.1%}. Classes: {len(rows)}')
    if not rows:
        print('WARNING: no overlapping mapped mineral polygons; check this window against the western-rim footprint.')

if __name__ == '__main__':
    run()
