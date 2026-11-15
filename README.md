# Mars-to-Earth Analog Finder

**NASA Space Apps Challenge 2026.** A web app that finds places on Earth whose terrain best matches a chosen site on Mars, so that rovers, instruments and mission teams can practise in realistic conditions before going to Mars.

Pick a Mars site, and the app compares it with **17,735 candidate desert, high-plateau and polar locations on Earth**. It ranks them by terrain similarity, shows the best matches on a map, and explains what matches, what differs and what cannot be compared.

---

## Site features

### 1. Landing page
A short introduction with a "Begin the Mission" button that opens the explorer.

### 2. Explore the terrain: Mars and Earth maps
- **Mars map:** a global elevation map (NASA Mars Trek, MOLA colour shaded relief) with the 5 Mars study sites as pins, coloured by type (crater, landing site, volcanic, other).
- **Site panel:** the selected site's name, coordinates, type and the measured values used for matching: median slope, steep terrain, local relief, roughness and wind speed.
- **Earth map:** a NASA Blue Marble map showing the top Earth matches for the selected Mars site.

### 3. Feature weights: sliders and presets
Users decide which terrain properties matter most for their mission:

| Slider | What it measures |
|---|---|
| Median slope | Typical slope of the ground (°) |
| Steep terrain | Share of the area steeper than 15° |
| Local relief | Height difference between low and high ground (m) |
| Roughness | Bumpiness of the terrain after removing large hills (m) |
| Wind speed | Mean near-surface wind speed (m/s); **off by default** |

Presets: **Balanced**, **Slope & incline**, **Rough terrain** and **Traverse planning**. The ranking updates instantly when a slider moves.

### 4. Analog search: ranked Earth matches
- The 10 closest Earth locations, each at least 50 km from the others so the results cover different places.
- Each result shows its rank and match score. Selecting one highlights it on the Earth map and opens the comparison below.

### 5. Scientific analysis: understand the comparison
- **Terrain comparison chart:** Mars and Earth values side by side for the four terrain features, scaled so they can be compared. Hover over a bar to see the original values and units. Wind speed is shown as a text line under the chart.
- **Scientific limitations panel:**
  - which features match most closely and which differ most;
  - what the app does **not** assess: soil strength, wheel traction, gravity, atmosphere, small-scale rockiness, radiation.
- **Surface & climate context table:** extra measurements shown side by side but **not used in the score**, each with a note on why:
  - thermal inertia and a rockiness class;
  - albedo (surface brightness);
  - day–night temperature range;
  - surface pressure;
  - prevailing wind direction;
  - geology;
  - minerals.

---

## How the score works

Each Mars site and Earth location is described by the same features, measured the same way over a **10 × 10 km area at ~455 m resolution**.

```
distance = √( Σ weightᵢ × ((Marsᵢ − Earthᵢ) / scaleᵢ)² )
score    = 100 / (1 + distance)
```

- **Weights** come from the sliders and are rescaled to add up to 1.
- **Scales** put the features on a common footing. Each one is the typical spread of that feature across all Earth locations: slope 3°, steep terrain 0.1, relief 250 m, roughness 25 m, wind speed 1 m/s.
- A **lower distance means a closer match.** The score is for display only: 100 means identical, 50 means one typical spread away. It is **not a "percentage Mars-like"**.
- Earth locations with missing values are skipped, never filled with zero.

---

## Data

### Mars: 5 study sites
| Site | Context |
|---|---|
| Jezero Western Rim | Perseverance rover area |
| Gale – Bradbury Landing | Curiosity rover landing site |
| Victoria Crater | Opportunity rover, Meridiani Planum |
| Nili Patera | Volcanic caldera with active dunes |
| Athabasca Valles | Young flood channels and lava plains |

| What | Source |
|---|---|
| Terrain (slope, relief, roughness) | High-resolution elevation models (CTX, HRSC), resampled to ~455 m |
| Wind speed, pressure | MACDA v2.0 Mars atmosphere reanalysis (modelled) |
| Thermal inertia | MGS TES (Putzig & Mellon 2007) |
| Albedo | Mars Express OMEGA, 1.08 µm (Ody et al. 2012) |
| Geology, minerals | USGS geologic maps, CRISM mineral maps and published observations |

### Earth: 17,735 locations in 27 regions
Candidate regions include the Atacama, Puna, Sahara, Tibesti, Namib, Taklamakan, Qaidam, Gobi, Lut, Arabian and Afar deserts, the Mojave and Utah, Iceland, Ladakh/Changtang, Devon Island and Svalbard.

A location is used only if it is mostly bare ground:
- **at least 70 % non-vegetated** (MODIS MOD44B);
- **at least 90 % elevation-data coverage**;
- **at most 10 %** cropland, urban area, wetland, snow/ice or water (MODIS MCD12Q1).

| What | Source |
|---|---|
| Terrain | Copernicus DEM GLO-30, processed with the **same code** as Mars |
| Wind speed, direction, pressure | NASA MERRA-2 reanalysis, 2025 monthly means |
| Surface temperature, albedo, apparent thermal inertia | MODIS MOD11A2 and MCD43A3, 2023 |
| Rock type | GLiM global lithological map (Hartmann & Moosdorf 2012) |

Full references are in [citations.md](citations.md) and the method in [docs/methodology.md](docs/methodology.md).

---

## Limitations

- **Terrain only:** matches are based on terrain shape at ~455 m resolution. They say nothing about soil strength, traction or rock size.
- **Not directly comparable between the planets:**
  - Thermal inertia: Mars TES measures physical thermal inertia; on Earth only an apparent index is available, which is also strongly affected by moisture.
  - Albedo: the two planets are measured at different wavelengths.
  - Pressure: Mars air is about 150× thinner.
  - These are therefore shown, not scored.
- **Wind comes from atmosphere models,** not measurements. Mars wind covers only parts of a Martian year.
- **Earth locations are area centres,** not checked for access or permission.
- **The scales and default weights** are engineering choices, not scientifically calibrated.

---

## Running the site locally

You need [Node.js](https://nodejs.org) (version 18 or newer).

```bash
cd frontend
npm install       # once: downloads the libraries
npm run dev       # starts the site at http://localhost:5173
npm run build     # production build in frontend/dist
```

## Rebuilding the data (optional)

The ready-to-use data is already in `frontend/public/data/`. To regenerate it from the processed sources (Python 3 with numpy):

```bash
python prep/mars_to_json.py     # data/combined/*.json -> mars_cells.json
python prep/earth_to_json.py    # Earth CSVs in data/ -> earth_cells.json
```

The full Earth pipeline is in `prep/`:
- `earth_export.js`: Google Earth Engine eligibility filter;
- `earth_terrain.py`: terrain features;
- `earth_atmosphere.py`: wind and pressure;
- `earththermal_prep.py`: MODIS thermal and albedo;
- `earth_surface_enrich.py`: geology.

## Repository layout

```
frontend/          React + Vite web app (maps: Leaflet, charts: Recharts)
frontend/public/data/
  mars_cells.json  Mars sites used by the app
  earth_cells.json Earth locations used by the app
  features.json    Feature list, scales and default weights
prep/              Python / Earth Engine data processing scripts
data/              Processed intermediate data (CSV / JSON)
docs/              Data contract and methodology
```
