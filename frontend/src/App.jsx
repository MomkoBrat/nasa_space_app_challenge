import { useEffect, useMemo, useState } from 'react';
import MarsMap from './components/MarsMap.jsx';
import EarthMap from './components/EarthMap.jsx';
import WeightSliders from './components/WeightSliders.jsx';
import SiteInfo from './components/SiteInfo.jsx';
import { rankEarthCells } from './lib/similarity.js';
import { canRecommend } from './lib/siteRules.js';
import { formatFeature } from './lib/featureLabels.js';

// TODO: replace the temporary results table below with Person B's components once stubbed:
// <EarthMap results={results} selectedRank={selectedResult?.rank} onSelect={setSelectedResult} />
// <ResultsList results={results} selectedRank={selectedResult?.rank} onSelect={setSelectedResult} />
// <ComparisonCharts site={selectedSite} result={selectedResult} />
// <LimitationsPanel site={selectedSite} result={selectedResult} />

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
            <EarthMap />
          </section>
          <section className="panel temp-results">
            <h2>Earth analogs (temporary view)</h2>
            {!selectedSite && <p>Select a Mars site to see results.</p>}
            {selectedSite && !canRecommend(selectedSite) && (
              <p>No Earth recommendations for polar sites.</p>
            )}
            {results.length > 0 && (
              <table>
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Lat, lon</th>
                    <th>Slope</th>
                    <th>Steep</th>
                    <th>Relief</th>
                    <th>Rough.</th>
                    <th>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r) => (
                    <tr
                      key={r.id}
                      className={r.rank === selectedResult?.rank ? 'selected' : ''}
                      onClick={() => setSelectedResult(r)}
                    >
                      <td className="rank">#{r.rank}</td>
                      <td>
                        {r.lat.toFixed(2)}, {r.lon.toFixed(2)}
                      </td>
                      {config.feature_keys.map((k) => (
                        <td key={k}>{formatFeature(k, r.features[k], config)}</td>
                      ))}
                      <td className="score">{r.score.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
