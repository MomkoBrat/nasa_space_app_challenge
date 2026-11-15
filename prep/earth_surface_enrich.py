#!/usr/bin/env python3
"""Add scientific Earth geology and mineral columns to an Earth candidate CSV.

Geology: Hartmann & Moosdorf GLiM v1.1, queried as actual point-in-polygon
         lookups from a public ArcGIS FeatureServer. The geology query needs
         network access; successful lookups are cached in JSONL.
Minerals: NASA EMIT L3 Aggregated Spectral Abundance V002, read from an
         official NetCDF downloaded by the user (Earthdata Login may be needed).
         Values are aggregate spectral estimates over 0.5-degree cells, NOT
         local point measurements or mineral mass percentages. Missing is blank.

Examples, run from project root:
  python prep/earth_surface_enrich.py --input data/earth_eligible_locations.csv \
      --output data/earth_eligible_locations_surface.csv
  python prep/earth_surface_enrich.py --input data/earth_eligible_locations_surface.csv \
      --output data/earth_eligible_locations_surface.csv --geology
  python prep/earth_surface_enrich.py --input data/earth_eligible_locations_surface.csv \
      --output data/earth_eligible_locations_surface.csv \
      --emit raw_data/earth/EMIT_L3_ASA_002.nc

Only columns owned by this script are modified. Existing IDs, coordinates,
other teammates' columns and row order are preserved. Rewriting same path is
atomic. Do not use this data for direct Mars-Earth mineral scoring because the
Mars profiles do not contain comparable mapped mineral abundance products.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import csv
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

GLIM_URL = ('https://services8.arcgis.com/4KhTMTZ1x0f76DSg/'
            'arcgis/rest/services/GLiM_Niveau_I/FeatureServer/1/query')
GLIM_SOURCE = 'Hartmann & Moosdorf 2012; https://doi.org/10.1029/2012GC004370'
EMIT_SOURCE = 'NASA EMITL3ASA V002; https://doi.org/10.5067/EMIT/EMITL3ASA.002'

# Exact names of EMIT's published ten mineral estimate layers.
EMIT_MINERALS = {
    'calcite': 'Calcite',
    'chlorite': 'Chlorite',
    'dolomite': 'Dolomite',
    'goethite': 'Goethite',
    'gypsum': 'Gypsum',
    'hematite': 'Hematite',
    'illite_muscovite': 'Illite+Muscovite',
    'kaolinite': 'Kaolinite',
    'montmorillonite': 'Montmorillonite',
    'vermiculite': 'Vermiculite',
}

GEO_COLUMNS = ['geo_lithology', 'geo_group', 'geo_status']
MINERAL_COLUMNS = [f'mineral_{m}_asa_pct' for m in EMIT_MINERALS]
NEW_COLUMNS = GEO_COLUMNS + MINERAL_COLUMNS + ['mineral_status']
assert len(NEW_COLUMNS) == 14

LITHO_GROUPS = {
    'Acid plutonic rocks': 'plutonic',
    'Intermediate plutonic rocks': 'plutonic',
    'Basic plutonic rocks': 'plutonic',
    'Acid volcanic rocks': 'volcanic',
    'Intermediate volcanic rocks': 'volcanic',
    'Basic volcanic rocks': 'volcanic',
    'Pyroclastics': 'volcanic',
    'Carbonate sedimentary rocks': 'sedimentary',
    'Mixed sedimentary rocks': 'sedimentary',
    'Siliciclastic sedimentary rocks': 'sedimentary',
    'Evaporites': 'sedimentary',
    'Metamorphics': 'metamorphic',
    'Unconsolidated sediments': 'unconsolidated',
    'Ice and Glaciers': 'ice',
    'Water Bodies': 'water',
    'No Data': 'no_data',
}


def read_table(path: Path):
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        rd = csv.DictReader(handle)
        if not rd.fieldnames:
            raise ValueError(f'{path} has no headers')
        needed = {'id', 'lat', 'lon'}
        if not needed.issubset(rd.fieldnames):
            raise ValueError(f'Missing required columns: {sorted(needed-set(rd.fieldnames))}')
        rows = list(rd)
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate IDs in input; refusing to enrich ambiguously')
        return list(rd.fieldnames), rows


def write_table_atomic(path: Path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmpname = tempfile.mkstemp(prefix='earth_surface_', suffix='.csv', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction='ignore',
                                    lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmpname, path)
    finally:
        if os.path.exists(tmpname):
            os.unlink(tmpname)


def lat_lon(row):
    try:
        lat, lon = float(row['lat']), float(row['lon'])
    except (ValueError, TypeError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 360):
        return None
    return lat, ((lon + 180) % 360) - 180


def cache_key(row):
    return f"{row['id']}|{row['lat']}|{row['lon']}"


def load_cache(path):
    cache = {}
    if path.is_file():
        with path.open('r', encoding='utf-8') as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                    if isinstance(record.get('value'), dict):
                        cache[record['key']] = record['value']
                except (ValueError, KeyError):
                    continue
    return cache


def query_glim(row, retries=3):
    coord = lat_lon(row)
    if coord is None:
        return {'geo_lithology': '', 'geo_group': '', 'geo_status': 'invalid_coordinates'}
    lat, lon = coord
    params = {
        'f': 'json', 'where': '1=1',
        'geometry': json.dumps({'x': lon, 'y': lat,
                                'spatialReference': {'wkid': 4326}}, separators=(',', ':')),
        'geometryType': 'esriGeometryPoint', 'inSR': '4326',
        'spatialRel': 'esriSpatialRelIntersects',
        'outFields': 'xx_Description', 'returnGeometry': 'false',
    }
    data = urllib.parse.urlencode(params).encode('utf-8')
    error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                GLIM_URL, data=data, headers={
                    'User-Agent': 'NASA-Space-Apps-Earth-Analog/1.0',
                    'Content-Type': 'application/x-www-form-urlencoded',
                }, method='POST')
            with urllib.request.urlopen(req, timeout=25) as response:
                response_json = json.load(response)
            if 'error' in response_json:
                raise RuntimeError(str(response_json['error'])[:200])
            descriptions = sorted({
                x.get('attributes', {}).get('xx_Description', '').strip()
                for x in response_json.get('features', [])
                if x.get('attributes', {}).get('xx_Description')
            })
            if not descriptions or descriptions == ['No Data']:
                return {'geo_lithology': '', 'geo_group': '', 'geo_status': 'no_map_data'}
            valid = [x for x in descriptions if x != 'No Data']
            if len(valid) != 1:
                # Do not arbitrarily select one of several different overlapping classes.
                return {'geo_lithology': '; '.join(valid), 'geo_group': '',
                        'geo_status': 'ambiguous_boundary'}
            litho = valid[0]
            return {'geo_lithology': litho,
                    'geo_group': LITHO_GROUPS.get(litho, 'other'),
                    'geo_status': 'mapped'}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
            error = str(exc)
            if attempt + 1 < retries:
                time.sleep((2 ** attempt) * 0.5)
    return {'geo_lithology': '', 'geo_group': '', 'geo_status': 'query_error'}


def process_geology(rows, cache_path: Path, workers=4, limit=None):
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = load_cache(cache_path)
    todo = []
    for row in rows:
        key = cache_key(row)
        if key in cache and cache[key].get('geo_status') != 'query_error':
            row.update(cache[key])
        elif row.get('geo_status') in {'mapped', 'ambiguous_boundary', 'no_map_data'}:
            # Preserve already-enriched rows and avoid unnecessary network requests.
            continue
        else:
            todo.append(row)
    print(f'GLiM: {len(rows)} rows, {len(cache)} cached, {len(todo)} need lookup', flush=True)
    if limit is not None:
        todo = todo[:limit]
        print(f'GLiM TEST MODE: querying at most {limit} locations; other rows stay unqueried', flush=True)
    if not todo:
        return
    counts = collections.Counter()
    # Cache is flushed as each task finishes. Re-run after interruptions to resume.
    with cache_path.open('a', encoding='utf-8') as checkpoint:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(query_glim, r): r for r in todo}
            for i, future in enumerate(concurrent.futures.as_completed(futures), start=1):
                row = futures[future]
                value = future.result()
                row.update(value)
                counts[value['geo_status']] += 1
                if value['geo_status'] != 'query_error':
                    checkpoint.write(json.dumps({'key': cache_key(row), 'value': value})+'\n')
                    checkpoint.flush()
                if i % 250 == 0 or i == len(todo):
                    print(f'GLiM progress {i:,}/{len(todo):,}: {dict(counts)}', flush=True)


def nkey(s):
    return re.sub('[^a-z0-9]', '', str(s).casefold())


def get_nc_var(nc, requested):
    found = []
    def walk(group):
        for name, var in group.variables.items():
            if nkey(name) == nkey(requested):
                found.append(var)
        for child in group.groups.values():
            walk(child)
    walk(nc)
    if len(found) != 1:
        raise ValueError(f'Expected exactly one NetCDF variable {requested!r}; found {len(found)}')
    return found[0]


def read_emit(nc_path, rows):
    try:
        import netCDF4
        import numpy as np
    except ImportError as exc:
        raise RuntimeError('Install NetCDF support: python -m pip install netCDF4 numpy') from exc
    if not nc_path.is_file():
        raise FileNotFoundError(f'NASA EMIT L3 file missing: {nc_path}')
    with netCDF4.Dataset(nc_path, mode='r') as nc:
        layers = {slug: get_nc_var(nc, var) for slug, var in EMIT_MINERALS.items()}
        shape = next(iter(layers.values())).shape
        if len(shape) != 2:
            raise ValueError(f'Expected 2-D EMIT mineral layers; found {shape}')
        for slug, var in layers.items():
            if var.shape != shape:
                raise ValueError(f'Inconsistent mineral layer shape: {slug} {var.shape}')
        lat_v = get_nc_var(nc, 'latitude')
        lon_v = get_nc_var(nc, 'longitude')
        lat_arr = np.asarray(lat_v[:], dtype='float64')
        lon_arr = np.asarray(lon_v[:], dtype='float64')
        # NASA's L3 user guide: latitude/longitude refer to the UPPER LEFT
        # corner of each 0.5-degree cell; data arrays are (lat, lon).
        if lat_arr.ndim == 2:
            if lat_arr.shape != shape:
                raise ValueError(f'Unexpected latitude array shape {lat_arr.shape}')
            lat_arr = lat_arr[:, 0]
        if lon_arr.ndim == 2:
            if lon_arr.shape != shape:
                raise ValueError(f'Unexpected longitude array shape {lon_arr.shape}')
            lon_arr = lon_arr[0, :]
        if lat_arr.ndim != 1 or lat_arr.size != shape[0]:
            raise ValueError(f'Unexpected latitude grid shape {lat_arr.shape} vs {shape}')
        if lon_arr.ndim != 1 or lon_arr.size != shape[1]:
            raise ValueError(f'Unexpected longitude grid shape {lon_arr.shape} vs {shape}')
        if np.any(~np.isfinite(lat_arr)) or np.any(~np.isfinite(lon_arr)):
            raise ValueError('Non-finite geolocation coordinates in NASA EMIT file')
        print('EMIT mineral grid:', shape, 'lat upper-left:',
              (float(lat_arr.min()), float(lat_arr.max())),
              'lon left:', (float(lon_arr.min()), float(lon_arr.max())), flush=True)
        # Resolve coordinate convention for the NetCDF (some use 0..360 E).
        use_360 = lon_arr.min() >= 0 and lon_arr.max() > 180
        # Read all layers once; they share a small global grid (~220 x 690).
        matrices = {slug: np.ma.masked_invalid(var[:])
                    for slug, var in layers.items()}
        counts = collections.Counter()
        for row in rows:
            coord = lat_lon(row)
            if coord is None:
                row['mineral_status'] = 'invalid_coordinates'
                continue
            lat, lon = coord
            if use_360:
                lon = lon % 360
            # First locate nearest cell center; then verify the point lies in
            # the cell identified by NASA's upper-left-corner geolocation.
            ri = int(np.argmin(np.abs(lat_arr - 0.25 - lat)))
            ci = int(np.argmin(np.abs(lon_arr + 0.25 - lon)))
            in_cell = (lat_arr[ri] - 0.5 - 1e-7 <= lat <= lat_arr[ri] + 1e-7
                       and lon_arr[ci] - 1e-7 <= lon < lon_arr[ci] + 0.5 + 1e-7)
            if not in_cell:
                row['mineral_status'] = 'outside_emit_grid'
                counts['outside_emit_grid'] += 1
                continue
            available = 0
            for slug, arr in matrices.items():
                value = arr[ri, ci]
                if np.ma.is_masked(value):
                    continue
                val = float(value)
                # EMIT fill = -9999 and values are percent-scale estimates.
                if not math.isfinite(val) or val <= -999 or val < 0 or val > 100:
                    continue
                row[f'mineral_{slug}_asa_pct'] = f'{val:.4f}'
                available += 1
            if available == len(layers):
                status = 'observed_coarse_0p5deg'
            elif available:
                status = 'partial_coarse_0p5deg'
            else:
                status = 'no_emit_observation'
            row['mineral_status'] = status
            counts[status] += 1
        print('EMIT status counts:', dict(counts), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--geology', action='store_true', help='Query GLiM API for mapped geology')
    ap.add_argument('--emit', type=Path, help='Path to official NASA EMITL3ASA V002 .nc file')
    ap.add_argument('--cache', type=Path,
                    default=Path('raw_data/earth/glim_point_cache.jsonl'))
    ap.add_argument('--geology-limit', type=int, default=None,
                    help='Test first N GLiM lookups, then rerun without this option')
    ap.add_argument('--workers', type=int, default=4,
                    help='Concurrent GLiM requests; use a small value to respect server limits')
    args = ap.parse_args()
    if args.geology_limit is not None and args.geology_limit < 1:
        ap.error('--geology-limit must be >=1')
    if not 1 <= args.workers <= 8:
        ap.error('--workers must be between 1 and 8')
    columns, rows = read_table(args.input)
    new_cols = [x for x in NEW_COLUMNS if x not in columns]
    cols_out = columns + new_cols
    # Always write original columns intact, append only script-owned new columns.
    for row in rows:
        for name in NEW_COLUMNS:
            row.setdefault(name, '')
        if not row['geo_status']:
            row['geo_status'] = 'not_queried'
        if not row['mineral_status']:
            row['mineral_status'] = 'not_loaded'
    if args.geology:
        process_geology(rows, args.cache, workers=args.workers, limit=args.geology_limit)
    if args.emit:
        read_emit(args.emit, rows)
    write_table_atomic(args.output, cols_out, rows)
    with args.output.open('r', encoding='utf-8', newline='') as handle:
        out_reader = csv.DictReader(handle)
        out_count = sum(1 for _ in out_reader)
    assert out_count == len(rows)
    print(f'Saved: {args.output}, {len(rows):,} locations, {len(cols_out)} columns', flush=True)
    print('Geology:', dict(collections.Counter(x['geo_status'] for x in rows)), flush=True)
    print('Minerals:', dict(collections.Counter(x['mineral_status'] for x in rows)), flush=True)
    print('Sources:', GLIM_SOURCE, ';', EMIT_SOURCE, flush=True)


if __name__ == '__main__':
    main()
