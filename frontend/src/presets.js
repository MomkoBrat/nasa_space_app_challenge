// Weight presets for the single mission mode (rover mobility). Proposed — confirm with Person 3.
// `weights: null` means "use config.default_weights from features.json".
export const PRESETS = {
  default: { label: 'Balanced', weights: null },
  slope: {
    label: 'Slope & incline',
    weights: { median_slope_deg: 0.4, steep_fraction: 0.4, relief_m: 0.1, roughness_m: 0.1 },
  },
  rough: {
    label: 'Rough terrain',
    weights: { median_slope_deg: 0.15, steep_fraction: 0.15, relief_m: 0.2, roughness_m: 0.5 },
  },
  traverse: {
    label: 'Traverse planning',
    weights: { median_slope_deg: 0.2, steep_fraction: 0.3, relief_m: 0.4, roughness_m: 0.1 },
  },
};

export function presetWeights(presetKey, config) {
  const p = PRESETS[presetKey];
  // Features a preset doesn't mention (e.g. wind speed) start at 0.
  const zeros = Object.fromEntries(config.feature_keys.map((k) => [k, 0]));
  return { ...zeros, ...(p?.weights ?? config.default_weights) };
}
