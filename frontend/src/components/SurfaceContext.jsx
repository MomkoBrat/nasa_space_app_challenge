import './SurfaceContext.css';

// Display-only surface & climate context for the selected Mars site and Earth analog.
// None of these values enter the similarity score: they are measured with different
// instruments / quantities on the two planets (see the "Comparable?" column).

const fmt = (v, digits = 0, unit = '') =>
  Number.isFinite(v) ? `${v.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits })}${unit}` : 'n/a';

const ATI_CLASS_TEXT = {
  low: 'Low ATI — likely loose / fine material',
  medium: 'Medium ATI',
  high: 'High ATI — rockier or moister surface',
};

function rows(mars, earth) {
  const m = mars?.context ?? {};
  const e = earth?.context ?? {};
  return [
    {
      label: 'Thermal inertia',
      mars: Number.isFinite(m.thermal_inertia_tiu) ? `${fmt(m.thermal_inertia_tiu)} tiu (TES)` : 'n/a',
      earth: Number.isFinite(e.ati) ? `ATI ${fmt(e.ati, 3)} 1/K (MODIS)` : 'n/a',
      note: 'No — different quantities',
    },
    {
      label: 'Small-scale rockiness',
      mars: m.surface_class ?? 'n/a',
      earth: e.ati_class ? ATI_CLASS_TEXT[e.ati_class] : 'n/a',
      note: 'No — class per planet; Earth ATI is affected by moisture',
    },
    {
      label: 'Albedo',
      mars: Number.isFinite(m.albedo_1080nm) ? `${fmt(m.albedo_1080nm, 2)} (1.08 µm)` : 'n/a',
      earth: Number.isFinite(e.albedo_shortwave) ? `${fmt(e.albedo_shortwave, 2)} (broadband)` : 'n/a',
      note: 'Partly — different wavelengths',
    },
    {
      label: 'Day–night surface temperature range',
      mars: 'n/a',
      earth: Number.isFinite(e.day_night_range_k) ? `${fmt(e.day_night_range_k, 0)} K (MODIS)` : 'n/a',
      note: 'Earth only',
    },
    {
      label: 'Surface pressure',
      mars: Number.isFinite(m.surface_pressure_pa) ? `${fmt(m.surface_pressure_pa)} Pa` : 'n/a',
      earth: Number.isFinite(e.surface_pressure_pa) ? `${fmt(e.surface_pressure_pa)} Pa` : 'n/a',
      note: 'No — Mars air is ~150× thinner',
    },
    {
      label: 'Prevailing wind direction',
      mars: Number.isFinite(m.prevailing_wind_direction_deg) ? `${fmt(m.prevailing_wind_direction_deg)}°` : 'n/a',
      earth: Number.isFinite(e.prevailing_wind_direction_deg) ? `${fmt(e.prevailing_wind_direction_deg)}°` : 'n/a',
      note: 'No — display only',
    },
    {
      label: 'Geology',
      mars: m.geology_dominant_unit ?? 'n/a',
      earth: e.geology ?? 'n/a',
      note: 'No — different maps and classifications',
    },
    {
      label: 'Minerals (mapped / reported)',
      mars: m.minerals?.length ? m.minerals.join(', ') : 'n/a',
      earth: 'n/a',
      note: 'Mars only',
    },
  ];
}

export default function SurfaceContext({ site, earthCell }) {
  if (!site) return null;
  const flags = earthCell?.quality?.flags ?? [];

  return (
    <section className="panel surface-context">
      <h2>Surface &amp; climate context</h2>
      <p className="comparison-note">
        Shown for context only — these values are <strong>not used in the score</strong>, because Earth and
        Mars measure them with different instruments or physical quantities.
      </p>
      <div className="surface-context-scroll">
        <table className="surface-context-table">
          <thead>
            <tr>
              <th scope="col">Property</th>
              <th scope="col">Mars — {site.name}</th>
              <th scope="col">{earthCell ? `Earth — ${earthCell.id}` : 'Earth'}</th>
              <th scope="col">Comparable?</th>
            </tr>
          </thead>
          <tbody>
            {rows(site, earthCell).map((r) => (
              <tr key={r.label}>
                <th scope="row">{r.label}</th>
                <td>{r.mars}</td>
                <td>{earthCell ? r.earth : '—'}</td>
                <td className="surface-context-note">{r.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!earthCell && <p className="comparison-note">Select an Earth analog to fill in the Earth column.</p>}
      {flags.length > 0 && (
        <p className="comparison-note">Earth data flags: {flags.map((f) => f.replaceAll('_', ' ')).join('; ')}.</p>
      )}
      <p className="comparison-note">
        Rockiness classes: Mars from TES thermal inertia (Putzig &amp; Mellon 2007 ranges); Earth relative to
        all candidate desert cells (thirds of apparent thermal inertia). The classes are not on a common scale.
      </p>
    </section>
  );
}
