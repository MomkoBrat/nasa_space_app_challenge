import { useEffect, useMemo, useState } from 'react';
import MarsMap from './components/MarsMap.jsx';
import EarthMap from './components/EarthMap.jsx';
import WeightSliders from './components/WeightSliders.jsx';
import SiteInfo from './components/SiteInfo.jsx';
import ResultsList from './components/ResultsList.jsx';
import ComparisonCharts from './components/ComparisonCharts.jsx';
import LimitationsPanel from './components/LimitationsPanel.jsx';
import { rankEarthCells } from './lib/similarity.js';
import { canRecommend } from './lib/siteRules.js';

async function loadJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

// similarity.js expects weights that sum to 1 (DATA_CONTRACT §5).
function normalizeWeights(weights) {
  const total = Object.values(weights).reduce((s, w) => s + w, 0);
  if (total <= 0) return null;
  return Object.fromEntries(Object.entries(weights).map(([k, w]) => [k, w / total]));
}

export default function App() {
  const [config, setConfig] = useState(null);
  const [marsSites, setMarsSites] = useState([]);
  const [earthCells, setEarthCells] = useState([]);
  const [loadError, setLoadError] = useState(null);

  const [selectedSite, setSelectedSite] = useState(null);
  const [weights, setWeights] = useState(null);
  const [selectedResult, setSelectedResult] = useState(null);

  useEffect(() => {
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
      .catch((err) => setLoadError(err.message));
  }, []);

  // A new site invalidates the selected result.
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
    }).map((r, i) => ({ ...r, rank: i + 1 }));
  }, [selectedSite, earthCells, weights, config]);

  if (loadError) {
    return <div className="app-status error">Could not load data: {loadError}</div>;
  }
  if (!config) {
    return <div className="app-status">Loading terrain data…</div>;
  }

  const usingMock =
    marsSites.some((s) => s.quality?.data_status === 'mock') ||
    earthCells.some((c) => c.quality?.data_status === 'mock');

  return (
    <div className="app">
      <header className="app-header">
        <h1>Mars-to-Earth Analog Finder</h1>
        <p className="subtitle">Rover mobility &amp; surface testing — terrain-only matching</p>
      </header>

      {usingMock && (
        <div className="mock-banner">
          MOCK DATA — values on this page are invented for development and are not NASA measurements.
        </div>
      )}

      <main className="layout">
        <div className="column mars-column">
          <MarsMap sites={marsSites} selectedId={selectedSite?.id} onSelect={setSelectedSite} />
          <SiteInfo site={selectedSite} />
          <WeightSliders config={config} weights={weights} onChange={setWeights} />
        </div>

        <div className="column earth-column">
          <section className="panel">
            <h2>Earth map</h2>
            <EarthMap results={results} selectedRank={selectedResult?.rank} onSelect={setSelectedResult} />
          </section>
          <section className="panel">
            {/* null = no Mars site selected; [] = site selected but no recommendations (e.g. polar). */}
            <ResultsList
              results={selectedSite ? results : null}
              selectedRank={selectedResult?.rank}
              onSelect={setSelectedResult}
            />
          </section>
        </div>

        {/* Full-width row: one shared selectedResult drives map, list, chart and limitations. */}
        <div className="comparison-row">
          <ComparisonCharts site={selectedSite} result={selectedResult} />
          <LimitationsPanel site={selectedSite} result={selectedResult} />
        </div>
      </main>
    </div>
  );
}
