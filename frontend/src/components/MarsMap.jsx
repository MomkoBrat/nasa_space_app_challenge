import L from 'leaflet';
import { MapContainer, CircleMarker, Tooltip } from 'react-leaflet';

// Equirectangular CRS so the full ±90° latitude range (polar sites) is visible
// and so it lines up with Mars Trek / OpenPlanetary equirectangular tiles later.
// TODO(Person A): add a Mars basemap <TileLayer> once the URL + attribution are verified.
const BOUNDS = [[-90, -180], [90, 180]];

const GROUP_COLORS = {
  landing_site: '#f59e0b',
  crater: '#f97316',
  volcanic: '#ef4444',
  canyon: '#a855f7',
  dune: '#eab308',
  polar: '#38bdf8',
  other: '#94a3b8',
};

export default function MarsMap({ sites, selectedId, onSelect }) {
  return (
    <div className="map mars-map">
      <MapContainer
        crs={L.CRS.EPSG4326}
        center={[0, 0]}
        zoom={0}
        minZoom={0}
        maxZoom={6}
        maxBounds={BOUNDS}
        maxBoundsViscosity={1}
        worldCopyJump={false}
        style={{ height: '100%', width: '100%' }}
      >
        {sites.map((site) => {
          const selected = site.id === selectedId;
          return (
            <CircleMarker
              key={site.id}
              center={[site.lat, site.lon]}
              radius={selected ? 10 : 7}
              pathOptions={{
                color: selected ? '#ffffff' : '#111827',
                weight: selected ? 3 : 1,
                fillColor: GROUP_COLORS[site.group] ?? GROUP_COLORS.other,
                fillOpacity: 0.9,
              }}
              eventHandlers={{ click: () => onSelect(site) }}
            >
              <Tooltip direction="top" offset={[0, -6]}>
                {site.name}
              </Tooltip>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
