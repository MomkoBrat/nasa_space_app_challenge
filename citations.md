### Mars Atmospheric Data — MACDA v2.0

**Source:** Mars Analysis Correction Data Assimilation (MACDA), Version 2.0  
**Authors:** Valeanu, A., Rajendran, K., Montabone, L., and Read, P. L. (2026)  
**Publisher:** NERC EDS Centre for Environmental Data Analysis (CEDA)  
**Dataset URL:** https://data.ceda.ac.uk/badc/mgs/data/macda/v2-0  
**DOI:** https://doi.org/10.5285/cd037a9ea387438fabf4d674dbe53088  
**License:** Open Government Licence v3.0

**Usage:** TerraMatch AI uses MACDA v2.0 atmospheric reanalysis data to calculate mean wind speed, prevailing wind direction, wind-speed variability, 95th-percentile wind speed, and surface atmospheric pressure for selected Mars locations.

The results are derived from four 30-sol periods of Mars Year 25, representing 120 sampled sols distributed across the Martian year. These results do not represent a complete annual climatology.

Wind data is extracted from the lowest atmospheric model sigma level, which does not necessarily correspond to a height of 10 meters above the surface.

**Official Citation:**

Valeanu, A., Rajendran, K., Montabone, L., & Read, P. L. (2026). *Mars Analysis Correction Data Assimilation (MACDA): Atmospheric and surface fields produced from assimilated MGS/TES, ODY/THEMIS, and MRO/MCS observations, v2.0*. NERC EDS Centre for Environmental Data Analysis. https://doi.org/10.5285/cd037a9ea387438fabf4d674dbe53088

---

### Earth Atmospheric Data — NASA MERRA-2

**Source:** Modern-Era Retrospective Analysis for Research and Applications, Version 2 (MERRA-2)  
**Provider:** NASA Global Modeling and Assimilation Office (GMAO)  
**Publisher:** NASA Goddard Earth Sciences Data and Information Services Center (GES DISC)  
**Spatial Resolution:** Approximately 0.5° latitude × 0.625° longitude

TerraMatch AI uses two NASA MERRA-2 monthly datasets to obtain wind and atmospheric-pressure information for Earth locations identified by their geographic coordinates.

#### Dataset 1 — Monthly Mean Single-Level Diagnostics

**Dataset ID:** `M2TMNXSLV`  
**Version:** 5.12.4  
**Dataset URL:** https://search.earthdata.nasa.gov/search?q=M2TMNXSLV  
**DOI:** https://doi.org/10.5067/AP1B0BA5PD2K

**Variables Used:**

- `U10M` — Eastward wind component at 10 meters (m/s).
- `V10M` — Northward wind component at 10 meters (m/s).
- `PS` — Surface atmospheric pressure (Pa).

**Usage:** This dataset provides the averaged wind components needed to calculate prevailing wind direction and mean wind-vector strength, as well as mean surface atmospheric pressure.

**Official Citation:**

Global Modeling and Assimilation Office, & Pawson, S. (2015). *MERRA-2 tavgM_2d_slv_Nx: 2d, Monthly mean, Time-Averaged, Single-Level, Assimilation, Single-Level Diagnostics V5.12.4* [Data set]. NASA Goddard Earth Sciences Data and Information Services Center. https://doi.org/10.5067/AP1B0BA5PD2K

#### Dataset 2 — Monthly Mean Surface Flux Diagnostics

**Dataset ID:** `M2TMNXFLX`  
**Version:** 5.12.4  
**Dataset URL:** https://search.earthdata.nasa.gov/search?q=M2TMNXFLX  
**DOI:** https://doi.org/10.5067/0JRLVL8YV2Y4

**Variable Used:**

- `SPEED` — Mean wind speed in the model's lowest atmospheric layer (m/s).

**Usage:** TerraMatch AI uses the monthly `SPEED` variable to calculate mean modeled wind speed for Earth locations.

Unlike the magnitude of averaged wind components, this variable represents average wind-speed magnitude and therefore avoids the cancellation of winds blowing in opposite directions.

The `SPEED` variable represents the model's lowest atmospheric layer, whose height varies by location and time and is typically approximately 60 meters above the surface. It is not equivalent to wind measured at exactly 10 meters.

**Official Citation:**

Global Modeling and Assimilation Office (GMAO). (2015). *MERRA-2 tavgM_2d_flx_Nx: 2d, Monthly mean, Time-Averaged, Single-Level, Assimilation, Surface Flux Diagnostics V5.12.4* [Data set]. NASA Goddard Earth Sciences Data and Information Services Center. https://doi.org/10.5067/0JRLVL8YV2Y4

#### Earth Data Processing

The analysis uses 12 monthly files from each dataset, covering January through December 2025.

TerraMatch AI extracts atmospheric values from the nearest available MERRA-2 grid points using the geographic coordinates of Earth candidate locations.

The monthly values are combined to calculate annual atmospheric summaries, accounting for the number of days represented by each month.

The processed measurements are appended to the Earth location records for use in atmospheric comparisons.

**Limitations:** MERRA-2 provides modeled atmospheric conditions rather than direct observations at every location. Its spatial resolution is substantially coarser than TerraMatch AI's 10 × 10 km Earth terrain cells, so multiple nearby locations may share the same modeled atmospheric values.

Although monthly `SPEED` data supports mean wind-speed calculations, it cannot reconstruct the complete distribution of hourly wind speeds, including short-term variability and extreme-wind statistics.

---

### Earth–Mars Atmospheric Comparison Methodology

TerraMatch AI compares atmospheric conditions between Mars and Earth using statistics derived from MACDA v2.0 and the two NASA MERRA-2 monthly datasets.

The atmospheric properties selected for comparison are:

- **Mean wind speed (m/s):** Calculated from individual modeled wind-speed samples for Mars and the monthly mean `SPEED` variable for Earth. Both describe mean wind-speed magnitude, although the modeled wind heights and sampled time periods differ.
- **Mean surface atmospheric pressure (Pa):** Calculated from available surface-pressure measurements for each planet.
- **Prevailing wind direction (degrees):** Calculated from averaged eastward and northward wind components using meteorological wind-direction conventions.
- **Mean wind-vector strength (m/s):** Calculated from the magnitude of averaged wind components. This is retained as a separate quantity and is not treated as equivalent to mean wind speed.

#### Differences in Temporal Resolution

Mars MACDA data contains multiple atmospheric samples per sol, while the Earth MERRA-2 datasets provide monthly averages.

For Mars, mean wind speed is calculated from the available individual wind-speed samples across four selected 30-sol periods.

For Earth, annual mean wind speed is calculated by combining the 12 monthly mean `SPEED` values, weighted by the number of days in each month.

This allows the project to compare average wind-speed magnitudes, while acknowledging that the datasets differ in temporal coverage and modeled measurement height.

#### Wind Variability and Extreme Winds

MACDA provides enough temporal detail to calculate additional Martian wind statistics, including the 95th-percentile wind speed and wind-speed standard deviation.

These statistics are retained as additional information but are not directly compared with Earth statistics derived from monthly averages.

#### Scientific Limitations

The Martian analysis covers four selected 30-sol periods rather than an entire Martian year. The Earth analysis covers all 12 months of 2025.

The datasets also differ in spatial resolution and modeled wind height. In particular, Earth's `SPEED` variable represents wind in the lowest model layer, while `U10M` and `V10M` represent wind components at 10 meters.

Furthermore, atmospheric pressure and density differ substantially between Earth and Mars. Similar wind speeds do not necessarily produce similar aerodynamic forces or surface conditions.

These limitations are acknowledged when interpreting atmospheric similarities between Earth and Mars.

## Mars Terrain Elevation Data

### NASA Mars Orbiter Laser Altimeter — MOLA

**Source:** Mars Orbiter Laser Altimeter (MOLA), Mars Global Surveyor mission  
**Provider:** NASA Planetary Data System (PDS)  
**Spatial Resolution:** 128 pixels per degree, approximately 460 m near the equator  
**Dataset URL:** https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg128/

**Files Used:**
- `megt44n000hb.img` — Nili Patera
- `megt44n090hb.img` — Athabasca Valles
- `megt00n270hb.img` — Victoria Crater

**Usage:** TerraMatch AI uses MOLA gridded elevation measurements to calculate terrain characteristics for the selected Martian locations.

The four principal terrain features are:

- Median slope (degrees).
- Steep terrain fraction, defined as the proportion of slopes exceeding 15°.
- Local relief, calculated as the difference between the 95th and 5th elevation percentiles.
- Terrain roughness, calculated from elevation residuals relative to a smoothed surface.

Terrain statistics are calculated for 10 × 10 km regional and 5 × 5 km detailed analysis areas.

**Limitations:** MOLA's approximately 460 m resolution cannot resolve small rocks, narrow channels or steep crater walls. In particular, the Victoria Crater profile uses MOLA-only elevation statistics, which do not adequately capture the approximately 800 m-wide crater's rim and interior.

---

### Jezero Crater — CTX Digital Elevation Model

**Source:** Mars 2020 Jezero Crater CTX Digital Elevation Model  
**Instrument:** Context Camera (CTX), Mars Reconnaissance Orbiter  
**Resolution:** Approximately 20 m per pixel  
**Dataset File:** `M20_JezeroCrater_CTXDEM_20m.tif`

**Usage:** TerraMatch AI uses the CTX digital elevation model to calculate terrain characteristics for the Jezero Western Rim reference location.

The elevation model provides substantially finer spatial detail than the global MOLA dataset.

**Limitations:** The resulting terrain statistics depend on the spatial coverage, quality and resolution of the available CTX elevation product.

---

### Gale Crater — HRSC Digital Elevation Model

**Source:** Gale Crater HRSC Digital Terrain Model Mosaic  
**Instrument:** High Resolution Stereo Camera (HRSC), Mars Express  
**Dataset URL:** https://doi.org/10.5281/zenodo.5808354  
**Resolution Used:** Approximately 30 m per pixel  
**Dataset File:** `hrsc_km09_h1938_h1927_h1916-dtm-mosaic.tif`

**Usage:** TerraMatch AI uses this elevation mosaic to calculate detailed terrain properties around Bradbury Landing in Gale Crater.

The regional analysis uses a coarser comparison grid, while the detailed analysis retains approximately 30 m spatial resolution.

**Limitations:** The measurements represent terrain morphology at the selected scales and cannot resolve individual surface rocks or directly measure rover traction.

---

## Mars Geological Data

### Global Geologic Map of Mars — USGS SIM 3292

**Source:** Global Geologic Map of Mars  
**Authors:** Tanaka et al. (2014)  
**Publisher:** United States Geological Survey (USGS)  
**Map Scale:** 1:20,000,000  
**DOI:** https://doi.org/10.3133/sim3292

**Geological Feature Service:**  
https://services.arcgis.com/nzS0F0zdNLvs7nc8/ArcGIS/rest/services/Mars_Geology_feature_layer/FeatureServer/0

**Usage:** TerraMatch AI uses the USGS geological map to classify surface geological units at Gale Crater, Nili Patera, Athabasca Valles and Victoria Crater.

Geological polygons are transformed into local Mars coordinate systems and intersected with the selected 5 × 5 km analysis areas.

The resulting records include:

- Dominant geological unit.
- Mapped geological unit classifications.
- Fraction of the analysis area represented by each mapped unit.
- Geological map coverage and quality information.

**Limitations:** The global geological map is too coarse to resolve all local lava flows, sedimentary layers and impact-related structures.

Geological polygon coverage represents the mapped surface classification, not mineral abundance or direct geochemical composition.

**Official Citation:**

Tanaka, K. L., et al. (2014). *Geologic Map of Mars*. U.S. Geological Survey Scientific Investigations Map 3292. https://doi.org/10.3133/sim3292

---

### Jezero Crater Geological Map — USGS SIM 3464

**Source:** Geologic Map of Jezero Crater and the Nili Planum Region, Mars  
**Authors:** Sun, V. Z., and Stack, K. M. (2020)  
**Publisher:** United States Geological Survey (USGS)  
**DOI:** https://doi.org/10.3133/sim3464

**Usage:** TerraMatch AI uses the detailed Jezero geological map to classify geological units within the Jezero Western Rim analysis area.

Mapped geological units are intersected with the selected footprint to determine their spatial coverage.

**Limitations:** Geological units represent scientific interpretations based on mapped morphology, stratigraphy and remote-sensing observations. They are not direct measurements of mineral abundance.

---

## Mars Mineralogical Data

### Jezero Western Rim — CRISM Mineral Maps

**Source:** Jezero Western Rim Mineral Maps  
**Authors:** Valantinas et al.  
**Dataset URL:** https://doi.org/10.5281/zenodo.22257754  
**Instrument:** Compact Reconnaissance Imaging Spectrometer for Mars (CRISM)

**Usage:** TerraMatch AI uses the published mineral classification maps to identify mapped spectral mineral classes within the Jezero Western Rim region.

The mineral classifications are geographically intersected with the analysis footprint where map coverage is available.

**Limitations:** Mapped spectral mineral classes do not represent direct mineral mass percentages. Areas without mapped classifications are treated as unknown rather than mineral-free.

---

### Gale Crater — Mineralogical Observations

**Primary Source:** Seelos et al. (2014)  
**Title:** *Mineralogy of the MSL Curiosity Landing Site in Gale Crater as Observed by MRO/CRISM*  
**DOI:** https://doi.org/10.1002/2014GL060310

**Supporting Source:** Sautter et al. (2014)  
**Title:** *Igneous Mineralogy at Bradbury Rise: The First ChemCam Campaign at Gale Crater*  
**Publication URL:** https://www.usgs.gov/publications/igneous-mineralogy-bradbury-rise-first-chemcam-campaign-gale-crater

**Usage:** TerraMatch AI incorporates published observations concerning pyroxene, olivine, basaltic materials and hydroxylated silica in the Gale Crater region.

**Limitations:** These are qualitative mineralogical observations. They do not establish mineral abundance percentages throughout the selected 5 × 5 km footprint.

---

### Nili Patera — Volcanic Mineralogy

**Sources:**

1. Fawdon et al. (2015). *The Geological History of Nili Patera, Mars.*  
   https://doi.org/10.1002/2015JE004795

2. Eggers et al. (2021). *Compositional Mapping of the Nili Patera Feldspathic Unit: Extent and Implications for Formation.*  
   https://doi.org/10.1029/2020JE006383

3. Skok et al. (2010). *Silica Deposits in the Nili Patera Caldera on the Syrtis Major Volcanic Complex on Mars.*  
   https://doi.org/10.1038/ngeo990

**Usage:** TerraMatch AI incorporates literature-supported mineral observations concerning olivine, pyroxene, feldspathic materials and hydrated silica in Nili Patera.

**Limitations:** The published observations describe mineral occurrences across the caldera and nearby localities. Their presence and abundance within the selected 5 km footprint are not independently verified by a complete mineral classification map.

---

### Athabasca Valles — Volcanic Material Composition

**Sources:**

1. Jaeger et al. (2010). *Emplacement of the Youngest Flood Lava on Mars: A Short, Turbulent Story.*  
   https://doi.org/10.1016/j.icarus.2009.09.011

2. Cataldo et al. (2015). *Limited Role for Thermal Erosion by Turbulent Lava in Proximal Athabasca Valles, Mars.*  
   https://doi.org/10.1002/2014JE004761

3. Voigt et al. (2023). *Revealing Elysium Planitia's Young Geologic History: Constraints on Lava Emplacement, Areas, and Volumes.*  
   https://doi.org/10.1029/2023JE007947

**Usage:** TerraMatch AI uses published observations to describe the predominantly mafic to ultramafic volcanic interpretation of Athabasca Valles.

The mineral profile records a tentative high-calcium pyroxene signature and possible olivine-related spectral characteristics.

**Limitations:** Dust coverage limits orbital mineral identification. These observations do not establish confirmed mineral abundances within the selected analysis area.

---

### Victoria Crater — Opportunity Rover Mineralogy

**Sources:**

1. Arvidson et al. (2015). *Mars Reconnaissance Orbiter and Opportunity Observations of the Burns Formation: Crater Hopping at Meridiani Planum.*  
   https://doi.org/10.1002/2014JE004686

2. Squyres et al. (2009). *Exploration of Victoria Crater by the Mars Rover Opportunity.*  
   https://doi.org/10.1126/science.1170355

3. Morris et al. (2006). *Mössbauer Mineralogy of Rock, Soil, and Dust at Meridiani Planum, Mars.*  
   https://doi.org/10.1029/2006JE002791

4. Arvidson et al. (2006). *Nature and Origin of the Hematite-Bearing Plains of Terra Meridiani Based on Analyses of Orbital and Mars Exploration Rover Data Sets.*  
   https://doi.org/10.1029/2006JE002728

**Usage:** TerraMatch AI uses Opportunity rover and CRISM observations to describe mineralogical characteristics of Victoria Crater.

The reported minerals include hematite, jarosite and pyroxene identified in rover investigations, together with a CRISM-based interpretation of kieserite-bearing material.

**Limitations:** Rover measurements represent individual rock exposures rather than the entire 5 × 5 km area. The kieserite identification is an orbital spectral interpretation, not a direct in-situ confirmation.

No quantitative mineral-area fractions are assigned to the complete footprint.

---

## Earth Geological Data — GLiM

### Global Lithological Map Database

**Source:** Global Lithological Map Database (GLiM)  
**Authors:** Hartmann, J., and Moosdorf, N. (2012)  
**Publication:** *Geochemistry, Geophysics, Geosystems*  
**DOI:** https://doi.org/10.1029/2012GC004370

**Usage:** TerraMatch AI uses the GLiM global lithological database to assign geological surface classifications to Earth candidate locations.

Geological classes are retrieved through geographic point queries using the latitude and longitude of each Earth location.

The resulting dataset contains:

- `geo_lithology` — Mapped lithological classification.
- `geo_group` — Broader geological category.
- `geo_status` — Mapping availability or processing status.

**Processing Results:**

- **Total Earth locations:** 17,735
- **Successfully mapped:** 17,679
- **Locations without mapped geological information:** 56
- **Successful coverage:** 99.68%
- **Unresolved query errors:** 0

The final geological classification dataset is stored in:

`data/earth_geology_by_id.csv`

Records are associated with Earth locations through their unique IDs, allowing the geological data to be joined with the team's terrain and atmospheric datasets.

**Limitations:** GLiM provides mapped lithological interpretations rather than site-specific measurements of mineral chemistry or rock properties.

The spatial resolution and mapping methods vary across regions. A point classification does not imply uniform geology throughout the corresponding 10 × 10 km Earth terrain cell.

**Official Citation:**

Hartmann, J., & Moosdorf, N. (2012). *The New Global Lithological Map Database GLiM: A Representation of Rock Properties at the Earth Surface.* Geochemistry, Geophysics, Geosystems, 13. https://doi.org/10.1029/2012GC004370

---

## Additional Martian Surface Datasets

### Mars Thermal Inertia — MGS/TES

**Source:** Mars Global Surveyor Thermal Emission Spectrometer (TES) dayside thermal inertia  
**Authors:** Putzig and Mellon (2007)  
**DOI:** https://doi.org/10.1016/j.icarus.2007.05.013

**Usage:** TerraMatch AI includes TES-based thermal inertia statistics in the combined Mars location profiles.

**Usage (rockiness class):** Each Mars site is assigned a display-only surface class from its regional median thermal inertia, using commonly applied Mars ranges: below 150 tiu dust / very fine-grained; 150–350 sand / fine-grained; 350–700 coarse or mixed with rock or crust; above 700 rock / bedrock dominated (after Putzig & Mellon, 2007 and Fergason et al., 2006).

**Limitations:** The source data has a coarse spatial resolution and is not directly equivalent to an Earth surface-material measurement.

**Additional Reference:**

Fergason, R. L., Christensen, P. R., & Kieffer, H. H. (2006). *High-resolution thermal inertia derived from the Thermal Emission Imaging System (THEMIS): Thermal model and applications.* Journal of Geophysical Research: Planets, 111, E12004. https://doi.org/10.1029/2006JE002735

---

### Mars Near-Infrared Albedo — OMEGA

**Source:** OMEGA, Mars Express near-infrared albedo product  
**Reference:** Ody et al. (2012)  
**Instrument:** Observatoire pour la Minéralogie, l'Eau, les Glaces et l'Activité (OMEGA)  
**Source File:** `ALBEDO_R1080_EQU_MAP.tiff`  
**Wavelength:** Approximately 1.08 μm

**Usage:** TerraMatch AI includes near-infrared albedo statistics for the selected Mars locations. The regional median albedo is also used by the optional **"Albedo (approx.)"** slider (default weight 0), where it is compared with Earth MODIS broadband albedo (see *Earth Surface Temperature, Albedo and Apparent Thermal Inertia*).

**Limitations:** Near-infrared albedo at 1.08 μm is not directly equivalent to broadband Earth albedo. Differences in observation conditions, wavelength and surface properties must be considered before interpreting Earth–Mars similarity.

---

## Earth–Mars Geology and Mineralogy Comparison Limitations

TerraMatch AI uses mapped geology and published mineral observations to provide scientific context alongside terrain comparisons.

However, the data sources differ in their mapping techniques, spatial resolutions and classifications.

- **Earth geology:** Derived from the GLiM global lithological database.
- **Mars geology:** Derived from USGS geological maps.
- **Mars mineralogy:** Derived from CRISM classifications and published orbital or rover observations.
- **Earth mineralogy:** No quantitative Earth mineral dataset was incorporated into this contribution.

Because geological classifications are not automatically equivalent across planets, they cannot be directly compared without a shared classification scheme.

Similarly, literature-supported Martian mineral occurrences cannot be interpreted as quantitative mineral abundance or spatial coverage.

**Therefore, geological and mineralogical information is retained as scientific context rather than treated as a fully validated quantitative Earth–Mars mineral similarity score.**

The quantitative comparison is based on median slope, local relief and roughness, with mean wind speed and albedo available as optional sliders (default weight 0). The steep terrain fraction (slopes above 15°) is still computed and stored but is not scored or shown, because at the ~455 m analysis resolution it is zero for almost every site.

---

## Earth Terrain and Candidate Selection

### Copernicus DEM GLO-30

**Source:** Copernicus Digital Elevation Model, GLO-30 (30 m global)  
**Provider:** European Space Agency (ESA) and Airbus, distributed through the Copernicus programme  
**Access:** AWS Open Data Registry, `copernicus-dem-30m` bucket — https://registry.opendata.aws/copernicus-dem/  
**DOI:** https://doi.org/10.5270/ESA-c5d3d65  
**Resolution:** Approximately 30 m

**Usage:** TerraMatch AI uses GLO-30 to calculate the terrain features of all 17,735 Earth candidate locations. For each location, a 10 × 10 km square centred on the location is average-resampled onto a 22 × 22 grid (~455 m pixels) in a local Transverse Mercator projection. The terrain features are then computed with **the same code as for Mars** (`terrain_features()` in `prep/mars_prep.py`): median slope, steep terrain fraction (slopes above 15°), local relief (95th minus 5th elevation percentile) and roughness (Gaussian smoothing, σ = 1000 m).

**Limitations:** At ~455 m resolution, individual rocks, small channels and short steep slopes are not resolved.

**Official Citation:**

European Space Agency, & Airbus. (2022). *Copernicus DEM* [Data set]. European Space Agency. https://doi.org/10.5270/ESA-c5d3d65

---

### MODIS Vegetation Continuous Fields — MOD44B

**Source:** MODIS/Terra Vegetation Continuous Fields Yearly L3 Global 250 m, Version 6.1 (`MOD44B`)  
**Provider:** NASA Land Processes Distributed Active Archive Center (LP DAAC)  
**DOI:** https://doi.org/10.5067/MODIS/MOD44B.061

**Usage:** The `Percent_NonVegetated` band, averaged over 2022–2024, is used to keep only Earth locations that are **at least 70 % non-vegetated**.

**Official Citation:**

DiMiceli, C., Sohlberg, R., & Townshend, J. (2022). *MODIS/Terra Vegetation Continuous Fields Yearly L3 Global 250m SIN Grid V061* [Data set]. NASA EOSDIS Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MODIS/MOD44B.061

---

### MODIS Land Cover Type — MCD12Q1

**Source:** MODIS/Terra+Aqua Land Cover Type Yearly L3 Global 500 m, Version 6.1 (`MCD12Q1`), IGBP classification (`LC_Type1`)  
**Provider:** NASA LP DAAC  
**DOI:** https://doi.org/10.5067/MODIS/MCD12Q1.061

**Usage:** A mosaic of the 2020–2025 land-cover maps (newest year on top) is used to exclude Earth locations where more than 10 % of the area is cropland, urban, cropland/natural vegetation mosaic, snow and ice, or water (IGBP classes 12, 13, 14, 15 and 17), and to record the barren fraction (class 16). Locations must also have **at least 90 % elevation-data coverage** (Copernicus DEM).

**Official Citation:**

Friedl, M., & Sulla-Menashe, D. (2022). *MODIS/Terra+Aqua Land Cover Type Yearly L3 Global 500m SIN Grid V061* [Data set]. NASA EOSDIS Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MODIS/MCD12Q1.061

---

### Google Earth Engine

**Source:** Google Earth Engine (cloud platform for geospatial analysis)  
**Reference:** Gorelick et al. (2017)

**Usage:** Earth Engine is used to evaluate the eligibility filters (MOD44B, MCD12Q1, Copernicus DEM coverage) for 25,467 candidate cells in 29 regions (`prep/earth_export.js`), and to compute the MODIS temperature and albedo statistics per cell (`prep/earththermal_prep.py`).

**Official Citation:**

Gorelick, N., Hancher, M., Dixon, M., Ilyushchenko, S., Thau, D., & Moore, R. (2017). *Google Earth Engine: Planetary-scale geospatial analysis for everyone.* Remote Sensing of Environment, 202, 18–27. https://doi.org/10.1016/j.rse.2017.06.031

---

## Earth Surface Temperature, Albedo and Apparent Thermal Inertia

### MODIS Land Surface Temperature — MOD11A2

**Source:** MODIS/Terra Land Surface Temperature/Emissivity 8-Day L3 Global 1 km, Version 6.1 (`MOD11A2`)  
**Provider:** NASA LP DAAC  
**DOI:** https://doi.org/10.5067/MODIS/MOD11A2.061

**Usage:** Day and night land surface temperatures for 2023 are averaged over each 10 × 10 km Earth location, using only composites in which both day and night values are valid and of good quality. Their difference gives the day–night temperature range.

**Official Citation:**

Wan, Z., Hook, S., & Hulley, G. (2021). *MODIS/Terra Land Surface Temperature/Emissivity 8-Day L3 Global 1km SIN Grid V061* [Data set]. NASA EOSDIS Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MODIS/MOD11A2.061

---

### MODIS Albedo — MCD43A3

**Source:** MODIS/Terra+Aqua BRDF/Albedo Daily L3 Global 500 m, Version 6.1 (`MCD43A3`)  
**Provider:** NASA LP DAAC  
**DOI:** https://doi.org/10.5067/MODIS/MCD43A3.061

**Usage:** The 2023 annual mean shortwave (0.3–5 µm) black-sky albedo is computed per Earth location (quality-filtered). It is shown as context and used by the optional **"Albedo (approx.)"** slider, compared with Mars OMEGA 1.08 µm albedo.

**Limitations:** Broadband shortwave albedo and single-wavelength near-infrared albedo are different measurements, so the albedo comparison is approximate.

**Official Citation:**

Schaaf, C., & Wang, Z. (2021). *MODIS/Terra+Aqua BRDF/Albedo Daily L3 Global – 500m V061* [Data set]. NASA EOSDIS Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MODIS/MCD43A3.061

---

### Apparent Thermal Inertia (ATI)

**Method:** ATI = (1 − albedo) / (day–night temperature range), after Price (1977).

**Usage:** ATI is computed for every Earth location and shown as display-only context, together with a relative class (low, medium or high: the lower, middle and upper thirds of all valid candidate locations). ATI is set to "not available" for 276 locations above 60° latitude or with a day–night range below 5 K, where the method does not apply. Locations with few valid MODIS observations (359) or processed without the MODIS quality filter (125) are flagged.

**Limitations:** ATI is a relative index (1/K), not a physical thermal inertia, and it is strongly affected by soil moisture. It is **not comparable** with Mars TES thermal inertia (J m⁻² K⁻¹ s⁻½) and is therefore not used in the score.

**Official Citation:**

Price, J. C. (1977). *Thermal inertia mapping: A new view of the Earth.* Journal of Geophysical Research, 82(18), 2582–2590. https://doi.org/10.1029/JC082i018p02582

---

## Maps and Imagery in the Web Application

### Mars Base Map — Viking MDIM 2.1 Colour Mosaic

**Source:** Viking Mars Digital Image Model (MDIM) 2.1 colour mosaic, ~232 m per pixel (NASA / JPL / USGS)  
**Access:** NASA Mars Trek WMTS tile service, layer `Mars_Viking_MDIM21_ClrMosaic_global_232m` — https://trek.nasa.gov/mars/

**Usage:** Background map on which the Mars study sites are selected.

---

### Earth Base Map — NASA GIBS Blue Marble

**Source:** Blue Marble Shaded Relief and Bathymetry  
**Access:** NASA Global Imagery Browse Services (GIBS), part of NASA EOSDIS — https://earthdata.nasa.gov/gibs

**Usage:** Background map showing the Earth analog locations.

---

### Country Borders — Natural Earth

**Source:** Natural Earth 1:110m Admin 0 – Countries (public domain) — https://www.naturalearthdata.com/

**Usage:** Country outlines on the Earth map and the approximate country names in `data/earth_eligible_locations.csv`. At this scale, a few coastal locations fall outside the outlines and have no country name.

---

### Page Imagery

- **Mars landscape (explorer header):** NASA/JPL-Caltech/ASU/MSSS
- **Earth (landing page):** NASA / Apollo 17, "Blue Marble" — https://commons.wikimedia.org/wiki/File:Blue_Marble_transparent.png
- **Mars (landing page):** NASA / JPL / USGS — https://science.nasa.gov/photojournal/global-color-views-of-mars/
