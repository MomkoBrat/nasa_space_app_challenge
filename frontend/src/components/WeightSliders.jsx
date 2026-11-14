import { PRESETS, presetWeights } from '../presets.js';
import { featureLabel } from '../lib/featureLabels.js';

// Sliders are independent 0–1 values; the share column shows each one's % of the total.
export default function WeightSliders({ config, weights, onChange }) {
  const keys = config.feature_keys;
  const total = keys.reduce((s, k) => s + (weights[k] ?? 0), 0);

  return (
    <section className="panel weight-sliders">
      <h2>Feature weights</h2>

      <div className="presets">
        {Object.entries(PRESETS).map(([key, preset]) => (
          <button key={key} type="button" onClick={() => onChange(presetWeights(key, config))}>
            {preset.label}
          </button>
        ))}
      </div>

      {keys.map((k) => {
        const { label } = featureLabel(k, config);
        const share = total > 0 ? (weights[k] / total) * 100 : 0;
        return (
          <label key={k} className="slider-row">
            <span className="slider-label">{label}</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={weights[k]}
              onChange={(e) => onChange({ ...weights, [k]: Number(e.target.value) })}
            />
            <span className="slider-share">{share.toFixed(0)} %</span>
          </label>
        );
      })}

      {total === 0 && <p className="warning">All weights are zero — raise at least one slider.</p>}
    </section>
  );
}
