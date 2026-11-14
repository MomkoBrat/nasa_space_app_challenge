// Display labels for the four scored features. features.json may later provide
// `feature_labels` (proposed in CLAUDE.md); if present it overrides these.
const FALLBACK_LABELS = {
  median_slope_deg: { label: 'Median slope', unit: '°' },
  steep_fraction: { label: 'Steep terrain', unit: '%' },
  relief_m: { label: 'Local relief', unit: 'm' },
  roughness_m: { label: 'Roughness', unit: 'm' },
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
  return `${Math.round(value)} ${unit}`;
}
