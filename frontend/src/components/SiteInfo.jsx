import { featureLabel, formatFeature } from '../lib/featureLabels.js';
import { canRecommend } from '../lib/siteRules.js';

const FEATURE_KEYS = ['median_slope_deg', 'relief_m', 'roughness_m', 'mean_wind_speed_ms', 'albedo'];

export default function SiteInfo({ site }) {
  if (!site) {
    return (
      <section className="panel site-info empty">
        <p>Select a Mars site on the map to find Earth terrain analogs.</p>
      </section>
    );
  }

  const res = site.analysis?.analysis_resolution_m;
  const isMock = site.quality?.data_status === 'mock';

  return (
    <section className="panel site-info">
      <h2>{site.name}</h2>
      <div className="badges">
        {site.detail_available ? (
          <span className="badge verified">Verified (high-resolution)</span>
        ) : (
          <span className="badge regional">Regional match{res ? ` (~${Math.round(res)} m data)` : ''}</span>
        )}
        {isMock && <span className="badge mock">MOCK data</span>}
        <span className="badge group">{site.group.replace('_', ' ')}</span>
      </div>

      <p className="coords">
        {site.lat.toFixed(2)}°, {site.lon.toFixed(2)}° (planetocentric, east-positive)
      </p>
      {site.description && <p>{site.description}</p>}

      {!canRecommend(site) && (
        <p className="warning">Shown for context only — no Earth recommendations for this site.</p>
      )}

      <table className="feature-table">
        <tbody>
          {FEATURE_KEYS.map((k) => (
            <tr key={k}>
              <th>{featureLabel(k).label}</th>
              <td>{formatFeature(k, site.features?.[k])}</td>
            </tr>
          ))}
          {Number.isFinite(site.quality?.coverage_fraction) && (
            <tr>
              <th>DEM coverage</th>
              <td>{(site.quality.coverage_fraction * 100).toFixed(0)} %</td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
