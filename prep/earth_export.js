/**
 * STEP 1 — Earth candidate cells + bare-land filter (Google Earth Engine Code Editor).
 *
 * How to run: open https://code.earthengine.google.com (project nasa-514808), paste this
 * whole file, click Run, then Tasks tab → RUN the "earth_candidates" export.
 * Output: Google Drive folder "nasa_space_apps" → earth_candidates.csv
 * Save it as data/earth_candidates.csv; step 2 (terrain, Python) reads it.
 *
 * Cells: 10 × 10 km on the ground (same window as Mars regional features). Each cell is a
 * lat/lon rectangle whose width in degrees is widened by 1/cos(lat) so it stays ~10 km.
 *
 * Eligibility (features.json earth_filters; land-cover threshold is PROVISIONAL):
 *   nonvegetated_fraction       >= 0.70   MOD44B Percent_NonVegetated (mean of 2022–2024)
 *   dem_coverage_fraction       >= 0.90   Copernicus GLO-30 valid pixels
 *   excluded_landcover_fraction <= 0.10   MCD12Q1 IGBP croplands, urban, crop mosaic,
 *                                         snow/ice, water (+ no-data counted as excluded)
 */

// ---------------------------------------------------------------- settings
var CELL_KM = 10;
var MIN_NONVEG = 0.70;
var MIN_DEM_COVERAGE = 0.90;
var MAX_EXCLUDED_LANDCOVER = 0.10;
var REDUCE_SCALE_M = 250; // MOD44B native resolution; MCD12Q1 (500 m) and DEM are sampled at it

// Arid Mars-analog regions: [west, south, east, north] in degrees, lon east-positive.
var REGIONS = {
  atacama:   [-70.5, -26.0, -68.5, -20.0],
  utah:      [-112.0, 37.0, -109.0, 39.5],
  mojave:    [-117.5, 34.5, -115.5, 37.0],
  iceland:   [-19.5, 64.2, -15.5, 65.3],
  ladakh:    [77.0, 32.5, 79.5, 35.0],
  namib:     [14.0, -25.0, 15.5, -20.0],
  sahara:    [21.0, 23.0, 24.0, 26.0],
  gobi:      [102.0, 42.0, 105.0, 44.0],
  arabia:    [51.0, 20.0, 53.0, 22.0],
  australia: [136.0, -27.0, 138.5, -24.5],
};

// ---------------------------------------------------------------- cell grid (client-side)
var KM_PER_DEG_LAT = 110.574;
var KM_PER_DEG_LON_EQ = 111.320;
var halfLat = CELL_KM / 2 / KM_PER_DEG_LAT;

function pad(n) { return ('0000' + n).slice(-4); }

var features = [];
var counts = {};
Object.keys(REGIONS).forEach(function (name) {
  var b = REGIONS[name];
  var n = 0;
  for (var lat = b[1] + halfLat; lat + halfLat <= b[3]; lat += 2 * halfLat) {
    var halfLon = CELL_KM / 2 / (KM_PER_DEG_LON_EQ * Math.cos(lat * Math.PI / 180));
    for (var lon = b[0] + halfLon; lon + halfLon <= b[2]; lon += 2 * halfLon) {
      n += 1;
      features.push(ee.Feature(
        ee.Geometry.Rectangle([lon - halfLon, lat - halfLat, lon + halfLon, lat + halfLat], null, false),
        {
          id: name + '_' + pad(n),
          region: name,
          lat: Math.round(lat * 1e5) / 1e5,
          lon: Math.round(lon * 1e5) / 1e5,
          half_height_deg: Math.round(halfLat * 1e7) / 1e7,
          half_width_deg: Math.round(halfLon * 1e7) / 1e7,
        }
      ));
    }
  }
  counts[name] = n;
});
var cells = ee.FeatureCollection(features);
print('Cells per region (before filtering):', counts, 'total', features.length);

// ---------------------------------------------------------------- input layers
// MOD44B: 0–100 %, values > 100 are fill (e.g. water) → masked, then counted as vegetated (0).
var nonveg = ee.ImageCollection('MODIS/061/MOD44B')
  .filterDate('2022-01-01', '2025-01-01')
  .select('Percent_NonVegetated')
  .map(function (img) { return img.updateMask(img.lte(100)); })
  .mean()
  .divide(100)
  .unmask(0, false) // false = also fill outside the source footprint (open ocean has no MODIS tiles)
  .rename('nonvegetated_fraction');

// The newest MCD12Q1 year can be incomplete (the first export had no land cover west of 0°),
// so mosaic several years with the newest on top: gaps are filled from the previous year.
var lcCollection = ee.ImageCollection('MODIS/061/MCD12Q1')
  .filterDate('2020-01-01', '2026-01-01')
  .sort('system:time_start'); // ascending → mosaic() puts the newest year on top
var lcImage = lcCollection.sort('system:time_start', false).first(); // only for printing metadata
var lc = lcCollection.select('LC_Type1').mosaic();
print('MCD12Q1 years used:', lcCollection.aggregate_array('system:time_start')
  .map(function (t) { return ee.Date(t).format('YYYY'); }));
// Coverage check: share of valid land-cover pixels at a few test points (should all be 1).
print('LC valid at Atacama / Utah / Iceland / Sahara:', ee.List([
  [-69.5, -23.5], [-110.7, 38.5], [-17.5, 64.7], [22.5, 24.5],
].map(function (p) {
  return lc.mask().reduceRegion(ee.Reducer.first(), ee.Geometry.Point(p), 500).get('LC_Type1');
})));
// Verify the IGBP codes used below (12 crop, 13 urban, 14 crop mosaic, 15 snow/ice, 16 barren, 17 water):
print('MCD12Q1 year:', ee.Date(lcImage.get('system:time_start')).format('YYYY'));
print('LC_Type1 class values:', lcImage.get('LC_Type1_class_values'));
print('LC_Type1 class names:', lcImage.get('LC_Type1_class_names'));

var excluded = lc.remap([12, 13, 14, 15, 17], [1, 1, 1, 1, 1], 0).unmask(1, false)
  .rename('excluded_landcover_fraction');
var barren = lc.eq(16).unmask(0, false).rename('barren_fraction');

var dem = ee.ImageCollection('COPERNICUS/DEM/GLO30').select('DEM').mosaic();
var demValid = dem.mask().unmask(0, false).rename('dem_coverage_fraction');

var stack = nonveg.addBands(excluded).addBands(barren).addBands(demValid);

// ---------------------------------------------------------------- per-cell fractions + eligibility
var reduced = stack.reduceRegions({
  collection: cells,
  reducer: ee.Reducer.mean(),
  scale: REDUCE_SCALE_M,
  tileScale: 4,
});

// A missing value (no data at all in the cell) falls back to the value that makes the cell
// INELIGIBLE, so gaps can never let a cell through. `missing_data` records that it happened.
function valueOr(f, key, fallback) {
  var v = f.get(key);
  return ee.Number(ee.Algorithms.If(ee.Algorithms.IsEqual(v, null), fallback, v));
}
function hasNull(f, keys) {
  return ee.List(keys).map(function (k) {
    return ee.Algorithms.IsEqual(f.get(k), null);
  }).contains(true);
}
function round3(n) { return n.multiply(1000).round().divide(1000); }

var result = reduced.map(function (f) {
  var nv = valueOr(f, 'nonvegetated_fraction', 0);
  var cov = valueOr(f, 'dem_coverage_fraction', 0);
  var ex = valueOr(f, 'excluded_landcover_fraction', 1);
  var bar = valueOr(f, 'barren_fraction', 0);
  var missing = hasNull(f, ['nonvegetated_fraction', 'dem_coverage_fraction',
                            'excluded_landcover_fraction', 'barren_fraction']);
  var eligible = nv.gte(MIN_NONVEG).and(cov.gte(MIN_DEM_COVERAGE)).and(ex.lte(MAX_EXCLUDED_LANDCOVER))
    .and(ee.Number(ee.Algorithms.If(missing, 0, 1)));
  return f.set({
    nonvegetated_fraction: round3(nv),
    dem_coverage_fraction: round3(cov),
    excluded_landcover_fraction: round3(ex),
    barren_fraction: round3(bar),
    missing_data: missing,
    eligible: eligible,
  });
});

Export.table.toDrive({
  collection: result,
  description: 'earth_candidates',
  folder: 'nasa_space_apps',
  fileFormat: 'CSV',
  selectors: [
    'id', 'region', 'lat', 'lon', 'half_height_deg', 'half_width_deg',
    'nonvegetated_fraction', 'barren_fraction', 'excluded_landcover_fraction',
    'dem_coverage_fraction', 'missing_data', 'eligible',
  ],
});

// ---------------------------------------------------------------- visual check (pixel level, fast)
var bareLand = nonveg.gte(MIN_NONVEG).and(excluded.eq(0)).selfMask();
Map.setCenter(-110.5, 38.3, 7);
Map.addLayer(nonveg, { min: 0, max: 1, palette: ['006400', 'ffffbf', 'd7191c'] }, 'Non-vegetated fraction', false);
Map.addLayer(excluded.selfMask(), { palette: ['0000ff'] }, 'Excluded land cover (blue)', false);
Map.addLayer(bareLand, { palette: ['ff8c00'] }, 'Bare land passing filter (orange)', true, 0.6);
Map.addLayer(cells.style({ color: '000000', fillColor: '00000000', width: 1 }), {}, 'Cell outlines');
