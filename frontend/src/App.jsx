import { MARS_IMAGE } from './planetImages.js';
import { useEffect, useMemo, useState } from 'react';
import MarsMap from './components/MarsMap.jsx';
import EarthMap from './components/EarthMap.jsx';
import WeightSliders from './components/WeightSliders.jsx';
import SiteInfo from './components/SiteInfo.jsx';
import ResultsList from './components/ResultsList.jsx';
import ComparisonCharts from './components/ComparisonCharts.jsx';
import LimitationsPanel from './components/LimitationsPanel.jsx';
import SurfaceContext from './components/SurfaceContext.jsx';
import { rankEarthCells } from './lib/similarity.js';
import { canRecommend } from './lib/siteRules.js';

async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function normalizeWeights(weights) {
  const total = Object.values(weights).reduce((sum, weight) => sum + weight, 0);
  if (total <= 0) return null;
  return Object.fromEntries(Object.entries(weights).map(([key, weight]) => [key, weight / total]));
}

export default function App({ initialData = null }) {
  const [config, setConfig] = useState(initialData?.config ?? null);
  const [marsSites, setMarsSites] = useState(initialData?.marsSites ?? []);
  const [earthCells, setEarthCells] = useState(initialData?.earthCells ?? []);
  const [loadError, setLoadError] = useState(null);

  const [selectedSite, setSelectedSite] = useState(null);
  const [weights, setWeights] = useState(initialData?.config ? { ...initialData.config.default_weights } : null);
  const [selectedResult, setSelectedResult] = useState(null);

  useEffect(() => {
    if (initialData) return;
    Promise.all([
      loadJson('/data/mars_cells.json'),
      loadJson('/data/earth_cells.json'),
      loadJson('/data/features.json'),
    ])
      .then(([mars, earth, cfg]) => {
        setMarsSites(mars.sites);
        setEarthCells(earth.cells);
        setConfig(cfg);
        setWeights({ ...cfg.default_weights });
      })
      .catch((error) => setLoadError(error.message));
  }, [initialData]);

  // Switching Mars locations clears the selected Earth result.
  useEffect(() => setSelectedResult(null), [selectedSite]);

  const results = useMemo(() => {
    if (!config || !weights || !canRecommend(selectedSite)) return [];
    const normalized = normalizeWeights(weights);
    if (!normalized) return [];
    return rankEarthCells({
      marsSite: selectedSite,
      earthCells,
      weights: normalized,
      scales: config.normalization_scales,
      limit: config.ranking.default_results,
      minSeparationKm: config.ranking.min_separation_km,
    }).map((result, index) => ({ ...result, rank: index + 1 }));
  }, [selectedSite, earthCells, weights, config]);

  const usingMock =
    marsSites.some((site) => site.quality?.data_status === 'mock') ||
    earthCells.some((cell) => cell.quality?.data_status === 'mock');

  return (
    <div className="app explorer-app">
      <header className="app-header explorer-hero">
        <nav className="explorer-hero-nav" aria-label="Explorer heading">
          <span className="explorer-brand"><span className="explorer-brand-star" aria-hidden="true">✦</span> NASA SPACE APPS <span className="explorer-brand-divider">/</span> NEW HORIZON</span>
          <span className="explorer-nav-note">PLANETARY FIELD LAB <span>•</span> 2026</span>
        </nav>

        <div className="explorer-mars-planet" aria-hidden="true">
          <img src={MARS_IMAGE} alt="" />
        </div>
        {/* The single page backdrop is painted above the lower portion of Mars,
            making the planet disappear behind the photographed rocky horizon. */}
        <div className="explorer-terrain-foreground" aria-hidden="true" />

        <div className="explorer-hero-copy">
          <p className="explorer-hero-eyebrow">DISCOVER TWO WORLDS. CONNECT THEIR TERRAIN.</p>
          <h1>New<br />Horizon</h1>
          <p className="subtitle">Mars-to-Earth Analog Finder</p>
        </div>
        <div className="explorer-hero-bottom" aria-hidden="true">
          <span>REAL PLANETARY DATA <span>•</span> TERRAIN ANALYSIS</span>
          <span>SCROLL TO EXPLORE <span className="scroll-chevron">⌄</span></span>
        </div>
        <span className="explorer-landscape-credit">Mars terrain imagery: NASA/JPL-Caltech/ASU/MSSS</span>
      </header>

      {loadError ? (
        <div className="app-status error">Could not load data: {loadError}</div>
      ) : !config ? (
        <div className="app-status">Loading terrain data…</div>
      ) : (
        <>
          {usingMock && (
            <div className="mock-banner">MOCK DATA — values on this page are invented for development and are not NASA measurements.</div>
          )}

          <main className="explorer-main">
            <section className="explorer-section mission-maps-section" aria-labelledby="explorer-maps-title">
              <div className="explorer-section-title">
                <div>
                  <span className="explorer-step">01 / SELECT &amp; EXPLORE</span>
                  <h2 id="explorer-maps-title">Explore the terrain</h2>
                </div>
                <p>Choose a Martian region to find its closest terrestrial analogs.</p>
              </div>

              <div className="layout mission-map-grid">
                <div className="column mars-column">
                  <section className="panel map-panel mars-map-panel">
                    <div className="map-panel-heading"><span className="map-panel-world">01 <span>/</span> MARS</span><span className="map-panel-caption">SELECT TARGET SITE</span></div>
                    <MarsMap sites={marsSites} selectedId={selectedSite?.id} onSelect={setSelectedSite} />
                  </section>
                  <SiteInfo site={selectedSite} />
                </div>
                <div className="column earth-column">
                  <section className="panel map-panel earth-map-panel">
                    <div className="map-panel-heading"><span className="map-panel-world">02 <span>/</span> EARTH</span><span className="map-panel-caption">TOP TERRAIN ANALOGS</span></div>
                    <EarthMap results={results} selectedRank={selectedResult?.rank} onSelect={setSelectedResult} />
                  </section>
                  <WeightSliders config={config} weights={weights} onChange={setWeights} />
                </div>
              </div>
            </section>

            <section className="explorer-section ranking-section" aria-labelledby="explorer-ranking-title">
              <div className="explorer-section-title">
                <div>
                  <span className="explorer-step">02 / ANALOG SEARCH</span>
                  <h2 id="explorer-ranking-title">The closest Earth matches</h2>
                </div>
                <p>Select any result to inspect it on the Earth map.</p>
              </div>
              <section className="panel ranking-panel">
                <ResultsList
                  results={selectedSite ? results : null}
                  selectedRank={selectedResult?.rank}
                  onSelect={setSelectedResult}
                />
              </section>
            </section>

            <section className="explorer-section science-section" aria-labelledby="explorer-science-title">
              <div className="explorer-section-title">
                <div>
                  <span className="explorer-step">03 / SCIENTIFIC ANALYSIS</span>
                  <h2 id="explorer-science-title">Understand the comparison</h2>
                </div>
                <p>Explore measurements and limitations behind each match.</p>
              </div>
              <div className="comparison-row">
                <ComparisonCharts site={selectedSite} result={selectedResult} />
                <LimitationsPanel site={selectedSite} result={selectedResult} />
              </div>
              <SurfaceContext
                site={selectedSite}
                earthCell={selectedResult ? earthCells.find((c) => c.id === selectedResult.id) : null}
              />
            </section>
          </main>
        </>
      )}
    </div>
  );
}
