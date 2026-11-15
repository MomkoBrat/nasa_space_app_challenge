// Display labels for the scored features (4 terrain + optional wind speed). features.json may later provide
// `feature_labels` (proposed in CLAUDE.md); if present it overrides these.
const FALLBACK_LABELS = {
  median_slope_deg: { label: 'Median slope', unit: '°' },
  steep_fraction: { label: 'Steep terrain', unit: '%' },
  relief_m: { label: 'Local relief', unit: 'm' },
  roughness_m: { label: 'Roughness', unit: 'm' },
  mean_wind_speed_ms: { label: 'Wind speed', unit: 'm/s' },
  albedo: { label: 'Albedo (approx.)', unit: 'ratio' },
};

export function featureLabel(key, config) {
  return config?.feature_labels?.[key] ?? FALLBACK_LABELS[key] ?? { label: key, unit: '' };
}

// steep_fraction is stored as 0..1 but shown as a percentage.
export function formatFeature(key, value, config) {
  if (!Number.isFinite(value)) return 'n/a';
  const { unit } = featureLabel(key, config);
  if (unit === '%') return `${(value * 100).toFixed(1)} %`;
  if (unit === '°') return `${value.toFixed(1)}°`;
  if (unit === 'm/s') return `${value.toFixed(1)} m/s`;
  if (unit === 'ratio') return value.toFixed(2);
  return `${Math.round(value)} ${unit}`;
}
