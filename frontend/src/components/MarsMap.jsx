import { useEffect } from 'react';
import L from 'leaflet';
import {
  MapContainer,
  TileLayer,
  Pane,
  Rectangle,
  Polyline,
  CircleMarker,
  Tooltip,
  useMap,
} from 'react-leaflet';

// Equirectangular CRS so the full ±90° latitude range (polar sites) is visible.
// It matches Mars Trek's tiling: zoom 0 = 2×1 tiles covering −180…180, east-positive.
const BOUNDS = [[-90, -180], [90, 180]];

// NASA Mars Trek WMTS — MOLA colour shaded relief (~463 m/px, close to our 460 m
// analysis scale). Verified: tile order z/row/col, zoom 0–7, CORS open.
const MOLA_URL =
  'https://trek.nasa.gov/tiles/Mars/EQ/Mars_MGS_MOLA_ClrShade_merge_global_463m/1.0.0/default/default028mm/{z}/{y}/{x}.jpg';
const MOLA_ATTRIBUTION =
  'Elevation: MOLA (NASA/JPL/GSFC) via <a href="https://trek.nasa.gov/mars/">NASA Mars Trek</a>';
const MOLA_MAX_NATIVE_ZOOM = 7;

const GROUP_COLORS = {
  landing_site: '#f59e0b',
  crater: '#f97316',
  volcanic: '#ef4444',
  canyon: '#a855f7',
  dune: '#eab308',
  polar: '#38bdf8',
  other: '#94a3b8',
};

// Graticule every 30°; the equator and prime meridian are slightly stronger.
const GRID_STEP = 30;
const GRID_LINES = [];
for (let lat = -90 + GRID_STEP; lat < 90; lat += GRID_STEP) {
  GRID_LINES.push({ key: `lat${lat}`, positions: [[lat, -180], [lat, 180]], main: lat === 0 });
}
for (let lon = -180 + GRID_STEP; lon < 180; lon += GRID_STEP) {
  GRID_LINES.push({ key: `lon${lon}`, positions: [[-90, lon], [90, lon]], main: lon === 0 });
}

// Keeps the whole planet as the furthest zoom-out level, re-measured when the
// window (and so the map box) changes size. Leaflet clamps the current zoom itself.
function FitPlanet() {
  const map = useMap();
  useEffect(() => {
    const updateMinZoom = () => map.setMinZoom(map.getBoundsZoom(BOUNDS));
    updateMinZoom();
    map.on('resize', updateMinZoom);
    return () => {
      map.off('resize', updateMinZoom);
    };
  }, [map]);
  return null;
}

export default function MarsMap({ sites, selectedId, onSelect }) {
  return (
    <div className="map mars-map">
      <MapContainer
        crs={L.CRS.EPSG4326}
        bounds={BOUNDS}
        zoomSnap={0.1}
        maxZoom={MOLA_MAX_NATIVE_ZOOM + 1}
        maxBounds={BOUNDS}
        maxBoundsViscosity={1}
        worldCopyJump={false}
        style={{ height: '100%', width: '100%' }}
      >
        <FitPlanet />

        {/* Fallback planet below the imagery: if tiles fail, the planet's extent stays visible. */}
        <Pane name="planet-base" style={{ zIndex: 150 }}>
          <Rectangle
            bounds={BOUNDS}
            interactive={false}
            pathOptions={{ stroke: false, fillColor: '#3b2418', fillOpacity: 1 }}
          />
        </Pane>

        <TileLayer
          url={MOLA_URL}
          attribution={MOLA_ATTRIBUTION}
          bounds={BOUNDS}
          noWrap
          maxNativeZoom={MOLA_MAX_NATIVE_ZOOM}
        />

        {/* Grid above the imagery, below the site markers. */}
        <Pane name="graticule" style={{ zIndex: 350, pointerEvents: 'none' }}>
          {GRID_LINES.map((line) => (
            <Polyline
              key={line.key}
              positions={line.positions}
              interactive={false}
              pathOptions={{
                color: '#ffffff',
                weight: 1,
                opacity: line.main ? 0.45 : 0.2,
                dashArray: line.main ? null : '4 4',
              }}
            />
          ))}
        </Pane>

        {sites.map((site) => {
          const selected = site.id === selectedId;
          return (
            <CircleMarker
              key={site.id}
              center={[site.lat, site.lon]}
              radius={selected ? 10 : 7}
              pathOptions={{
                // Thick dark outline so dots stay visible on the colourful relief map.
                color: selected ? '#ffffff' : '#0b0d12',
                weight: selected ? 3 : 2,
                fillColor: GROUP_COLORS[site.group] ?? GROUP_COLORS.other,
                fillOpacity: 1,
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
