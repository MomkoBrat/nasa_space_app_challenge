### Mars Atmospheric Data — MACDA v2.0

**Source:** Mars Analysis Correction Data Assimilation (MACDA), Version 2.0  
**Authors:** Valeanu, A., Rajendran, K., Montabone, L., and Read, P. L. (2026)  
**Publisher:** NERC EDS Centre for Environmental Data Analysis (CEDA)  
**Dataset URL:** https://data.ceda.ac.uk/badc/mgs/data/macda/v2-0  
**DOI:** https://doi.org/10.5285/cd037a9ea387438fabf4d674dbe53088  
**License:** Open Government Licence v3.0

**Usage:** TerraMatch AI uses MACDA v2.0 atmospheric reanalysis data to calculate wind speed, prevailing wind direction, wind variability, and surface atmospheric pressure for selected Mars locations.

The results are derived from four 30-sol periods of Mars Year 25 and do not represent a complete annual climatology. Wind data is extracted from the lowest atmospheric model sigma level, which does not necessarily correspond to a height of 10 meters above the surface.

**Official Citation:**

Valeanu, A., Rajendran, K., Montabone, L., & Read, P. L. (2026). *Mars Analysis Correction Data Assimilation (MACDA): Atmospheric and surface fields produced from assimilated MGS/TES, ODY/THEMIS, and MRO/MCS observations, v2.0*. NERC EDS Centre for Environmental Data Analysis. https://doi.org/10.5285/cd037a9ea387438fabf4d674dbe53088

---

### Earth Atmospheric Data — NASA MERRA-2

**Source:** Modern-Era Retrospective Analysis for Research and Applications, Version 2 (MERRA-2)  
**Dataset:** Monthly Mean Single-Level Diagnostics (`M2TMNXSLV`, Version 5.12.4)  
**Provider:** NASA Global Modeling and Assimilation Office (GMAO)  
**Publisher:** NASA Goddard Earth Sciences Data and Information Services Center (GES DISC)  
**Dataset URL:** https://search.earthdata.nasa.gov/search?q=M2TMNXSLV  
**DOI:** https://doi.org/10.5067/AP1B0BA5PD2K

**Usage:** TerraMatch AI uses NASA MERRA-2 atmospheric reanalysis data to obtain near-surface wind components and surface atmospheric pressure for Earth locations identified by their geographic coordinates.

The analysis uses 12 monthly datasets covering January through December 2025. These datasets are combined to produce annual atmospheric summaries for Earth candidate locations.

The variables used are:

- `U10M` — Eastward wind component at 10 meters (m/s).
- `V10M` — Northward wind component at 10 meters (m/s).
- `PS` — Surface atmospheric pressure (Pa).

Atmospheric values are extracted from the nearest available MERRA-2 grid points.

**Limitations:** The dataset provides monthly averages at approximately 0.5° × 0.625° spatial resolution. Consequently, it cannot provide true hourly wind variability or extreme-wind statistics, and multiple nearby Earth locations may share the same atmospheric estimates.

**Official Citation:**

Global Modeling and Assimilation Office, & Pawson, S. (2015). *MERRA-2 tavgM_2d_slv_Nx: 2d, Monthly mean, Time-Averaged, Single-Level, Assimilation, Single-Level Diagnostics V5.12.4* [Data set]. NASA Goddard Earth Sciences Data and Information Services Center. https://doi.org/10.5067/AP1B0BA5PD2K

---

### Earth–Mars Atmospheric Comparison Methodology

TerraMatch AI compares atmospheric conditions between Mars and Earth using compatible statistics derived from the MACDA v2.0 and NASA MERRA-2 datasets.

The atmospheric properties selected for direct comparison are:

- **Mean surface atmospheric pressure (Pa):** Calculated from available surface-pressure data for each location.
- **Mean wind-vector strength (m/s):** Calculated from the magnitude of the averaged eastward and northward wind components.
- **Prevailing wind direction (degrees):** Calculated from the averaged wind components using meteorological wind-direction conventions.

Mars MACDA data contains higher-frequency observations, whereas Earth MERRA-2 data provides monthly averages. To support a consistent comparison, the Martian wind components are aggregated into mean values before calculating wind-vector strength and prevailing direction.

High-frequency Martian wind statistics, including the 95th-percentile wind speed and wind-speed standard deviation, are retained as additional information but are not directly compared against monthly Earth wind averages.

**Scientific Limitations:** The Mars analysis covers four selected 30-sol periods rather than an entire Martian year, while the Earth analysis covers all 12 months of 2025. The datasets also use different modeled wind heights and spatial resolutions.

Furthermore, Martian atmospheric pressure is substantially lower than Earth's, so similar wind speeds do not necessarily produce similar physical forces. These differences are acknowledged when interpreting Earth–Mars atmospheric similarities.