import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { featureLabel, formatFeature } from '../lib/featureLabels.js';
import './ComparisonCharts.css';

const TERRAIN_FEATURES = [
  'median_slope_deg',
  'steep_fraction',
  'relief_m',
  'roughness_m',
];

function RawValuesTooltip({ active, payload, config }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;

  return (
    <div className="comparison-tooltip">
      <strong>{row.label}</strong>
      <div>Mars: {formatFeature(row.key, row.rawMars, config)}</div>
      <div>Earth: {formatFeature(row.key, row.rawEarth, config)}</div>
      <div className="comparison-tooltip-scale">
        Normalization scale: {formatFeature(row.key, row.scale, config)}
      </div>
    </div>
  );
}

/**
 * Read-only comparison of the selected Mars and Earth regions.
 * All chart bars are normalized against the SAME scales as similarity.js.
 * Props are deliberately limited to { site, result } for App.jsx integration.
 */
export default function ComparisonCharts({ site, result }) {
  const [config, setConfig] = useState(null);
  const [configError, setConfigError] = useState('');

  useEffect(() => {
    const controller = new AbortController();

    async function loadFeatureConfig() {
      try {
        const response = await fetch('/data/features.json', { signal: controller.signal });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        setConfig(data);
      } catch (error) {
        if (error.name !== 'AbortError') {
          setConfigError(`Could not load feature scales: ${error.message}`);
        }
      }
    }

    loadFeatureConfig();
    return () => controller.abort();
  }, []);

  const { chartData, missingFeatures } = useMemo(() => {
    if (!config || !site || !result) return { chartData: [], missingFeatures: [] };

    const chartData = [];
    const missingFeatures = [];

    for (const key of TERRAIN_FEATURES) {
      const rawMars = site.features?.[key];
      const rawEarth = result.features?.[key];
      const scale = config.normalization_scales?.[key];

      if (!Number.isFinite(rawMars) || !Number.isFinite(rawEarth) ||
          !Number.isFinite(scale) || scale <= 0) {
        missingFeatures.push(featureLabel(key, config).label);
        continue;
      }

      chartData.push({
        key,
        label: featureLabel(key, config).label,
        rawMars,
        rawEarth,
        scale,
        mars: rawMars / scale,
        earth: rawEarth / scale,
      });
    }
    return { chartData, missingFeatures };
  }, [config, site, result]);

  if (!site) {
    return (
      <section className="panel comparison-charts">
        <h2>Mars vs Earth — terrain comparison</h2>
        <p className="comparison-empty">Select a Mars location to begin.</p>
      </section>
    );
  }

  if (!result) {
    return (
      <section className="panel comparison-charts">
        <h2>Mars vs Earth — terrain comparison</h2>
        <p className="comparison-empty">
          Select an Earth analog from the map or results list to compare it with {site.name}.
        </p>
      </section>
    );
  }

  return (
    <section className="panel comparison-charts">
      <h2>Mars vs Earth — terrain comparison</h2>
      <p className="comparison-subtitle">
        {site.name} vs Earth Analog №{result.rank ?? '—'}
      </p>
      <p className="comparison-note">
        Each measurement is divided by its feature-specific normalization scale from features.json.
        Bar lengths are normalized measurements, not similarity percentages.
        Hover over the bars for the original values and units.
      </p>

      {configError ? (
        <p className="comparison-error" role="alert">{configError}</p>
      ) : !config ? (
        <p className="comparison-empty">Loading comparison scales…</p>
      ) : chartData.length === 0 ? (
        <p className="comparison-empty">No valid comparable measurements are available.</p>
      ) : (
        <div className="comparison-chart-container" role="img" aria-label="Normalized terrain features for Mars and the selected Earth analog">
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={chartData} layout="vertical" margin={{ top: 8, right: 18, left: 0, bottom: 12 }} barGap={2}>
              <CartesianGrid stroke="#343946" strokeDasharray="3 3" horizontal={false} />
              <XAxis
                type="number"
                stroke="#9ca3af"
                tick={{ fill: '#b6bbc6', fontSize: 11 }}
                tickFormatter={(value) => Number(value).toFixed(2)}
                allowDecimals
              />
              <YAxis
                type="category"
                dataKey="label"
                width={105}
                stroke="#9ca3af"
                tick={{ fill: '#e5e7eb', fontSize: 11 }}
              />
              <Tooltip
                cursor={{ fill: 'rgba(255,255,255,0.035)' }}
                content={<RawValuesTooltip config={config} />}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: '#e5e7eb' }} />
              <Bar dataKey="mars" name="Mars" fill="#f97316" radius={[0, 3, 3, 0]} maxBarSize={16} />
              <Bar dataKey="earth" name="Earth" fill="#60a5fa" radius={[0, 3, 3, 0]} maxBarSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {missingFeatures.length > 0 && (
        <p className="comparison-note" role="status">
          Not plotted because measurements or valid scales are missing: {missingFeatures.join(', ')}.
        </p>
      )}
      {site.quality?.data_status === 'mock' && (
        <p className="comparison-mock">MOCK DATA — Mars measurements are invented for testing.</p>
      )}
    </section>
  );
}
