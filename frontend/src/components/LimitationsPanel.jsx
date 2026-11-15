import { useEffect, useMemo, useState } from 'react';
import { featureLabel, formatFeature } from '../lib/featureLabels.js';
import './LimitationsPanel.css';

const TERRAIN_FEATURES = [
  'median_slope_deg',
  'steep_fraction',
  'relief_m',
  'roughness_m',
];

const NOT_ASSESSED = [
  ['Soil strength', 'Not measured by the regional elevation model.'],
  ['Wheel traction', 'Cannot be inferred from terrain elevation alone.'],
  ['Gravity', 'Earth and Mars gravity differ; effects on rover operation are not modeled.'],
  ['Atmosphere', 'Only mean wind speed can be compared (optional slider, modeled data). Pressure, temperature and dust are not compared; Mars air pressure is about 150 times lower.'],
  ['Small-scale rockiness', 'Rock size and surface material are not compared: Earth apparent and Mars thermal inertia are different quantities (see Surface & climate context).'],
  ['Radiation', 'Radiation environment is not evaluated by the terrain matching.'],
];

/**
 * Presentational limitations summary for a selected pair.
 * Uses measured feature gaps to describe closest and least-close comparisons.
 * lib/explain.js is currently empty; Person 3 owns the eventual explanation engine.
 */
export default function LimitationsPanel({ site, result }) {
  const [config, setConfig] = useState(null);
  const [configError, setConfigError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    async function loadFeatureConfig() {
      try {
        const response = await fetch('/data/features.json', { signal: controller.signal });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        setConfig(await response.json());
      } catch (error) {
        if (error.name !== 'AbortError') {
          setConfigError(`Could not load feature scales: ${error.message}`);
        }
      }
    }
    loadFeatureConfig();
    return () => controller.abort();
  }, []);

  const comparisons = useMemo(() => {
    if (!config || !site || !result) return [];

    return TERRAIN_FEATURES.flatMap((key) => {
      const mars = site.features?.[key];
      const earth = result.features?.[key];
      const scale = config.normalization_scales?.[key];
      if (!Number.isFinite(mars) || !Number.isFinite(earth) ||
          !Number.isFinite(scale) || scale <= 0) return [];
      return [{
        key,
        label: featureLabel(key, config).label,
        mars: formatFeature(key, mars, config),
        earth: formatFeature(key, earth, config),
        gap: Math.abs(mars - earth) / scale,
      }];
    }).sort((a, b) => a.gap - b.gap);
  }, [config, site, result]);

  const midpoint = Math.min(2, comparisons.length);
  const closest = comparisons.slice(0, midpoint);
  // Only report an actual difference; exact matches shouldn't be labeled mismatches.
  const largestDifferences = comparisons.slice(midpoint).filter((item) => item.gap > 1e-9).reverse();
  const resolution = site?.analysis?.analysis_resolution_m ?? config?.regional_analysis?.analysis_resolution_m ?? 460;

  return (
    <section className="panel limitations-panel">
      <h2>Scientific limitations</h2>
      {!site ? (
        <p className="limitations-intro">Select a Mars site to examine the comparison's limitations.</p>
      ) : !result ? (
        <p className="limitations-intro">
          Select an Earth analog to see which terrain characteristics match, which differ, and what remains unassessed.
        </p>
      ) : (
        <>
          <p className="limitations-intro">
            {site.name} vs Earth Analog №{result.rank ?? '—'}.
            This is a terrain-based candidate match, not a rover-safety certification.
          </p>

          <div className="limitations-group">
            <h3 className="limitations-heading limitations-heading-match">Matches</h3>
            <p className="limitations-caption">Closest two measured terrain features (relative to their normalization scales):</p>
            {configError ? (
              <p className="limitations-caption" role="alert">{configError}</p>
            ) : !config ? (
              <p className="limitations-caption">Loading feature scales…</p>
            ) : closest.length === 0 ? (
              <p className="limitations-caption">No comparable terrain measurements are available.</p>
            ) : (
              <ul>
                {closest.map((item) => (
                  <li key={item.key}>
                    <strong>{item.label}:</strong> Mars {item.mars} · Earth {item.earth}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="limitations-group">
            <h3 className="limitations-heading limitations-heading-differ">Differs</h3>
            <p className="limitations-caption">Largest remaining measured gaps; a larger gap is not necessarily a major physical difference:</p>
            {!config || comparisons.length === 0 ? (
              <p className="limitations-caption">No measured differences available yet.</p>
            ) : largestDifferences.length === 0 ? (
              <p className="limitations-caption">No additional nonzero differences in the remaining features.</p>
            ) : (
              <ul>
                {largestDifferences.map((item) => (
                  <li key={item.key}>
                    <strong>{item.label}:</strong> Mars {item.mars} · Earth {item.earth}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}

      <div className="limitations-group">
        <h3 className="limitations-heading limitations-heading-unknown">Unknown / not assessed</h3>
        <p className="limitations-caption">
          These conditions are not evaluated by the terrain-matching model; some are known to differ between planets.
        </p>
        <ul>
          {NOT_ASSESSED.map(([name, description]) => (
            <li key={name}><strong>{name}:</strong> {description}</li>
          ))}
        </ul>
      </div>

      <p className="limitations-footer">
        Regional terrain measurements use approximately {Math.round(resolution)} m analysis resolution.
        Individual rocks and other small obstacles cannot be reliably resolved.
      </p>
      {site?.quality?.data_status === 'mock' && (
        <p className="limitations-mock" role="note">
          MOCK DATA — current Mars feature values are invented for development, not measured NASA results.
          See the application's mock-data banner for overall dataset status.
        </p>
      )}
    </section>
  );
}
