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