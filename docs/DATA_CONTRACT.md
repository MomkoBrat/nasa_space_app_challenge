# Mars-to-Earth Analog Finder — Data Contract v1.0

**Freeze this format before parallel development.** Project uses **JavaScript/JSX** (not TypeScript), with Python preprocessing. All data examples in `examples/` are **MOCK values, not NASA measurements**. Never submit mock values as scientific results.

## 1. Files and owners

| Path in current repository | Owner | Contract |
|---|---|---|
| `data/mars_cells.csv` | Person 1 | Generated regional Mars features; CSV header specified below |
| `data/earth_cells.csv` | Person 2 | Generated Earth terrain features; same feature columns |
| `frontend/public/data/mars_cells.json` | Person 1 | Website Mars catalog, JSON wrapper `{ schema_version, sites }` |
| `frontend/public/data/earth_cells.json` | Person 2 | Small/test Earth dataset, `{ schema_version, cells }` |
| `frontend/public/data/features.json` | Person 3 (owner) | **Single source of truth** for units, normalization, weights, and region size |
| `frontend/src/lib/similarity.js` | Person 3 | Pure function described in section 5 |
| `frontend/src/App.jsx`, `frontend/src/components/` | Person 4 | Fetches JSON and calls ranking function |
| `docs/methodology.md` + comparison UI | Person 5 | Explains sources, methods, limitations, and verification |
| `prep/earth_export.js`, `prep/mars_prep.py` | Persons 2 and 1 | Produces source CSV/JSON according to this contract |

**Production optimization (later):** Replace large `earth_cells.json` with `earth_cells.bin` and `earth_cells.meta.json`. Keep JSON as a small working fallback. No frontend rewrite: parsing layer returns the *same normalized Earth objects* to the ranker. Do not spend the first hours building the binary format before matching works.

## 2. Global conventions

- Coordinates: `{ "lat": number, "lon": number }` in decimal degrees; longitude **east-positive from -180 through 180**. Mars coordinates are planetocentric; Earth coordinates are standard geographic/WGS84. **Never use Mars coordinates as Earth coordinates.**
- Regional comparison: `window_size_m = 10000` (10 × 10 km), `analysis_resolution_m = 460` (common analysis scale on both planets). Compute features using a consistent local projection, physical units and method. Save the actual pixel size/resolution used.
- Detailed showcase (separate record): ~5 × 5 km, common finer comparison scale *documented per pair*. **Do not mix 60 m and 460 m feature vectors in the same ranking.**
- Feature values **must be finite numeric values** when the region is eligible for ranking. If a measurement is missing use `null`, flag it, and exclude or explicitly omit that feature from scoring with disclosed rules; never substitute 0.
- Four scored regional features (exact spellings, case-sensitive):
  1. `median_slope_deg` — median of slope in **degrees**.
  2. `steep_fraction` — fraction of analyzed pixels whose slope is **strictly greater than 15 degrees**; range [0,1], not percent.
  3. `relief_m` — P95 minus P5 elevation in **metres**.
  4. `roughness_m` — standard deviation of residual elevation vs approximately 3 km smoothed terrain, in **metres** (same algorithm both planets).
- `albedo` and geology are **context only** in v1, not part of the scoring algorithm. TES and MODIS albedos are not a validated identical-material measurement.
- Earth preliminary eligibility: area is sufficiently barren/sparsely vegetated, with **>=70% non-vegetated fraction** and **>=90% valid DEM coverage**. Thresholds are provisional and must be documented/tested. Don't claim rover access or soil strength from eligibility.
- Include original data source(s), quality/coverage information, and `data_status: "mock" | "processed"`. UI **must flag mock data clearly**; final submission must contain processed scientific values.

## 3. Mars JSON shape — `frontend/public/data/mars_cells.json`

```json
{
  "schema_version": "1.0",
  "sites": [
    {
      "id": "mars_site_001",
      "name": "Mars example site (MOCK)",
      "group": "crater",
      "lat": 18.44,
      "lon": 77.45,
      "description": "Example only; values are invented.",
      "analysis": { "window_size_m": 10000, "analysis_resolution_m": 460 },
      "features": {
        "median_slope_deg": 4.5,
        "steep_fraction": 0.08,
        "relief_m": 170,
        "roughness_m": 22
      },
      "quality": { "coverage_fraction": 0.98, "flags": [], "data_status": "mock" },
      "sources": [{ "dataset": "MOCK", "native_resolution_m": null, "url": null }],
      "image_url": null,
      "detail_available": false
    }
  ]
}
```

`group` is a descriptive filter category (e.g. `crater`, `landing_site`, `volcanic`, `dune`, `canyon`, `polar`, `other`). Do not encode geological certainty into the group.

## 4. Earth JSON shape — `frontend/public/data/earth_cells.json`

```json
{
  "schema_version": "1.0",
  "analysis": { "window_size_m": 10000, "analysis_resolution_m": 460 },
  "cells": [
    {
      "id": "earth_site_001",
      "lat": 38.5,
      "lon": -110.7,
      "features": {
        "median_slope_deg": 4.0,
        "steep_fraction": 0.06,
        "relief_m": 150,
        "roughness_m": 20
      },
      "surface": { "nonvegetated_fraction": 0.91, "landcover": "barren" },
      "quality": { "coverage_fraction": 0.97, "flags": [], "data_status": "mock" },
      "sources": [{ "dataset": "MOCK", "native_resolution_m": null, "url": null }]
    }
  ]
}
```

Earth candidates are **region centres**, not verified access points. Names/countries are optional and should be displayed only when sourced. Earth production rows may omit verbose `sources` when dataset-level provenance is stored in accompanying metadata.

## 5. Matching interface — Person 3 delivers

```js
// frontend/src/lib/similarity.js
export function rankEarthCells({
  marsSite,       // one object from mars_cells.json.sites
  earthCells,     // array from earth_cells.json.cells or decoded binary
  weights,        // object with same 4 feature keys, nonnegative, normalized to sum to 1
  limit = 10,
  minSeparationKm = 50
}) {
  // Returns array sorted ascending by distance:
  // [{ id, lat, lon, distance, score, contributions, features }]
}
```

**Math (v1):** `distance = sqrt(sum(weight_i * ((mars_i-earth_i)/scale_i)^2))`. Read `scale_i` from `features.json` (not arbitrary changes in different modules). Optional display-only score `100/(1+distance)`; **not a percentage of Mars equivalence**. The result's `contributions` uses the same four keys and records each nonnegative weighted squared-distance term. Lower distance ranks better. In the full implementation, filter invalid data, then optionally diversify the top results by 50 km separation.

**Mission focus:** One mode, `rover_mobility`. Sliders may reweight the four **measured** terrain features for slope testing, rough navigation, or traverse planning. Geological information is shown separately, not used as an unsupported scoring feature.

### Example API result (values hypothetical)

```json
{
  "id": "earth_site_001",
  "lat": 38.5,
  "lon": -110.7,
  "distance": 0.14,
  "score": 87.7,
  "contributions": {
    "median_slope_deg": 0.001,
    "steep_fraction": 0.002,
    "relief_m": 0.004,
    "roughness_m": 0.0126
  },
  "features": {
    "median_slope_deg": 4.0,
    "steep_fraction": 0.06,
    "relief_m": 150,
    "roughness_m": 20
  }
}
```

The example output illustrates *shape only*; values are not asserted as an actual calculated match.

## 6. CSV source header (regional preprocessing)

For `data/mars_cells.csv` and `data/earth_cells.csv`, use these shared feature columns:

```csv
id,lat,lon,median_slope_deg,steep_fraction,relief_m,roughness_m,coverage_fraction,data_status
```

Mars CSV may additionally have `name,group,description`; Earth CSV may additionally have `nonvegetated_fraction,landcover`. Export scripts must create the JSON shapes shown above rather than relying on CSV column order. CSV rows are a preprocessing artifact; **JSON is the frontend contract**.

## 7. Detailed science comparison (Person 5 + P1/P3)

Record fine-resolution Jezero-vs-Earth verification in a **separate** document or `frontend/public/data/verified_pairs.json`, with both source datasets, each native resolution, shared analysis resolution, region size, derived features, uncertainty, and explanation (`matches`, `differs`, `unknown`). A verified-pair label is allowed only after actually comparing higher-resolution data. The global 460 m ranking should never silently use the high-resolution fingerprint.

## 8. Frontend integration requirements

```js
const [mars, earth, config] = await Promise.all([
  fetch('/data/mars_cells.json').then(r => r.json()),
  fetch('/data/earth_cells.json').then(r => r.json()),
  fetch('/data/features.json').then(r => r.json()),
]);
const selectedMarsSite = mars.sites[0];
const candidates = rankEarthCells({
  marsSite: selectedMarsSite,
  earthCells: earth.cells,
  weights: config.default_weights,
  limit: 10,
});
```

The production binary loader will return `earthCells` in the same shape as `earth.cells` or expose an equivalent accessor to the ranker. Browser fetch paths are **`/data/...`**, not `/frontend/public/data/...`.

## 9. Team-wide acceptance checklist

- Both planets use exactly the **same four scored keys**, units, 10 km window and 460 m common analysis scale.
- Both data files parse and all numeric values are finite; coordinates and fractions are within valid ranges.
- A real Earth comparison works using sample data before any global export.
- Mars/Earth metadata clearly identifies dataset source, processing resolution and coverage.
- Browser and Python ranking match on fixed test inputs.
- Output explanation distinguishes **matches, differences and unknowns**.
- Final website flags or removes *mock* values; no invented numbers presented as NASA observations.
- Detailed verification is a separate workflow, with its own spatial scale and scientific evidence.

**Freeze after agreement**: Change these field names or file paths only with a team-wide announcement; otherwise parallel work will break at integration.
