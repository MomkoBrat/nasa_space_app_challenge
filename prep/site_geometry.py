"""Shared coordinates for scientific modules: never assume Mars coordinates are Earth WGS84."""
import json
from pathlib import Path
from shapely.geometry import box
from shapely.ops import transform as shape_transform
from pyproj import CRS, Transformer

# USGS Sun & Stack Jezero geological units (native Mars sphere, local Transverse Mercator).
JZ_GEOLOGY_CRS = CRS.from_proj4(
    '+proj=tmerc +lat_0=0 +lon_0=77.5 +k=1 +x_0=0 +y_0=0 '
    '+R=3396190 +units=m +no_defs +type=crs'
)


def read_site(site_json, scale='detailed'):
    """Site centre and Mars CRS copied from the already-extracted terrain JSON."""
    d = json.loads(Path(site_json).read_text(encoding='utf-8'))
    if scale not in ('detailed', 'regional'):
        raise ValueError('scale must be detailed or regional')
    center = d['center_projected_m']
    crs = CRS.from_wkt(d['source_crs_wkt'])
    if not crs.is_projected or 'mars' not in crs.to_wkt().lower():
        raise ValueError('Terrain JSON does not contain a projected Mars CRS.')
    size = float(d[scale]['region_km']) * 1000
    x, y = float(center['x']), float(center['y'])
    roi = box(x - size/2, y - size/2, x + size/2, y + size/2)
    return d['id'], crs, roi, {'scale': scale, 'width_m': size, 'height_m': size,
                              'center_projected_m': {'x': x, 'y': y}}


def transform_shape(geometry, src_crs, dst_crs):
    src_crs = CRS.from_user_input(src_crs)
    dst_crs = CRS.from_user_input(dst_crs)
    if 'mars' not in src_crs.to_wkt().lower() and 'mars' not in str(src_crs).lower():
        raise ValueError('Source projection must explicitly identify Mars. Do NOT use Earth EPSG:4326.')
    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    return shape_transform(transformer.transform, geometry)


def save_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(f'Saved: {path}')
