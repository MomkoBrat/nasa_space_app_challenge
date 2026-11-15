import { useEffect, useMemo, useRef, useState } from 'react';
import { divIcon, latLngBounds } from 'leaflet';
import { MapContainer, Marker, TileLayer, Tooltip, useMap } from 'react-leaflet';

// NASA GIBS Blue Marble (static, no date needed). Native tiles stop at zoom 8;
// beyond that Leaflet enlarges the zoom-8 tiles.
const GIBS_URL =
  'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg';
const GIBS_ATTRIBUTION =
  'Imagery: <a href="https://earthdata.nasa.gov/gibs">NASA EOSDIS GIBS</a>, Blue Marble · Borders: <a href="https://www.naturalearthdata.com/">Natural Earth</a>';

// EPSG:3857 (the projection used by the NASA GIBS tiles) stops at ±85.0511°.
// Constrain panning to a single copy of Earth, rather than wrapping endlessly.
const EARTH_BOUNDS = latLngBounds(
  [-85.05112878, -180],
  [85.05112878, 180],
);
// Web Mercator world tiles are 256 px wide at zoom 0. Match the world width
// to the available panel width, avoiding blank bands on either side.
const worldWidthZoom = (width) => Math.log2(Math.max(256, width) / 256);

// Keep the full world at least as wide as the visible panel. At the
// furthest zoom out, turn dragging off; zooming in restores bounded panning.
function BoundPanToZoom({ minimumZoom }) {
  const map = useMap();
  const previousMinimum = useRef(minimumZoom);

  useEffect(() => {
    map.invalidateSize({ animate: false });
    const oldMin = previousMinimum.current;
    const wasZoomedOut = map.getZoom() <= oldMin + 0.01;
    map.setMinZoom(minimumZoom);
    if (wasZoomedOut) {
      map.setView([0, 0], minimumZoom, { animate: false });
    } else if (map.getZoom() < minimumZoom) {
      map.setZoom(minimumZoom, { animate: false });
    }
    previousMinimum.current = minimumZoom;
  }, [map, minimumZoom]);

  useEffect(() => {
    const updateDragging = () => {
      if (map.getZoom() <= map.getMinZoom() + 0.01) {
        map.dragging.disable();
      } else {
        map.dragging.enable();
      }
    };
    updateDragging();
    map.on('zoomend', updateDragging);
    return () => map.off('zoomend', updateDragging);
  }, [map, minimumZoom]);

  return null;
}

// The parent App supplies the already-ranked Earth results.
function numberedIcon(rank, isSelected) {
  return divIcon({
    className: 'earth-numbered-pin-wrapper',
    html: `<span class="earth-numbered-pin${isSelected ? ' selected' : ''}">${rank}</span>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });
}

// Country names are derived from the Natural Earth (1:110m) boundary dataset.
// These boundaries are approximate; prefer a supplied country field when available.
function isInsideRing(lon, lat, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

function isInsidePolygon(lon, lat, rings) {
  if (!isInsideRing(lon, lat, rings[0])) return false;
  // A point inside a hole is outside the country's land area.
  return !rings.slice(1).some((hole) => isInsideRing(lon, lat, hole));
}

function lookupCountry(lat, lon, countries) {
  for (const feature of countries) {
    const { type, coordinates } = feature.geometry;
    const polygons = type === 'Polygon' ? [coordinates] : coordinates;
    if (polygons.some((polygon) => isInsidePolygon(lon, lat, polygon))) {
      return feature.properties.name;
    }
  }
  return null;
}

function formatCoordinates(lat, lon) {
  const latitude = `${Math.abs(lat).toFixed(2)}° ${lat < 0 ? 'S' : 'N'}`;
  const longitude = `${Math.abs(lon).toFixed(2)}° ${lon < 0 ? 'W' : 'E'}`;
  return `${latitude}, ${longitude}`;
}

// Zoom to the current results whenever the set of results changes, so clustered
// pins spread out. Single results get a regional view instead of maximum zoom.
function FitResults({ results }) {
  const map = useMap();
  const key = results.map((r) => r.id).join(',');
  useEffect(() => {
    if (results.length === 0) return;
    map.fitBounds(latLngBounds(results.map((r) => [r.lat, r.lon])), {
      padding: [40, 40],
      maxZoom: 5,
    });
    // `key` captures every change to the result set that matters here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, key]);
  return null;
}

// Rank 1 draws on top of rank 2 etc.; the selected pin draws above all of them.
function pinZIndex(rank, isSelected) {
  return isSelected ? 10000 : (100 - rank) * 10;
}

export default function EarthMap({ results = [], selectedRank = null, onSelect }) {
  const [countries, setCountries] = useState([]);
  const mapFrame = useRef(null);
  const [frameWidth, setFrameWidth] = useState(0);

  useEffect(() => {
    const frame = mapFrame.current;
    if (!frame) return undefined;
    const updateSize = () => setFrameWidth(frame.clientWidth);
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(frame);
    return () => observer.disconnect();
  }, []);

  const minimumZoom = worldWidthZoom(frameWidth);

  useEffect(() => {
    let active = true;
    fetch('/data/countries.geojson')
      .then((response) => {
        if (!response.ok) throw new Error('Could not load country boundaries');
        return response.json();
      })
      .then((data) => {
        if (active) setCountries(data.features);
      })
      .catch((error) => console.warn('Country labels unavailable:', error));
    return () => { active = false; };
  }, []);

  const countryById = useMemo(() => {
    return new Map(results.map((result) => [
      result.id,
      result.country || lookupCountry(result.lat, result.lon, countries) || 'Not available',
    ]));
  }, [results, countries]);

  return (
    <div className="map earth-map" ref={mapFrame}>
      {frameWidth > 0 && <MapContainer
        center={[0, 0]}
        zoom={minimumZoom}
        minZoom={minimumZoom}
        zoomSnap={0}
        zoomDelta={0.5}
        maxBounds={EARTH_BOUNDS}
        maxBoundsViscosity={1.0}
        maxZoom={10}
        worldCopyJump={false}
        dragging={false}
        scrollWheelZoom={true}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          url={GIBS_URL}
          attribution={GIBS_ATTRIBUTION}
          maxNativeZoom={8}
          maxZoom={10}
          noWrap={true}
        />
        <BoundPanToZoom minimumZoom={minimumZoom} />
        <FitResults results={results} />
        {results.map((result) => (
          <Marker
            key={result.id}
            position={[result.lat, result.lon]}
            icon={numberedIcon(result.rank, result.rank === selectedRank)}
            zIndexOffset={pinZIndex(result.rank, result.rank === selectedRank)}
            riseOnHover
            eventHandlers={{ click: () => onSelect?.(result) }}
          >
            <Tooltip direction="top" offset={[0, -16]} opacity={1} className="earth-pin-tooltip">
              <div className="earth-pin-tooltip-title">Earth Analog №{result.rank}</div>
              <div>Country: {countryById.get(result.id)}</div>
              <div>Coordinates: {formatCoordinates(result.lat, result.lon)}</div>
              {/* Display-only score: compresses near 100 and is NOT a % of Mars equivalence. */}
              <div>Match score: {result.score.toFixed(1)} (relative, not a %)</div>
            </Tooltip>
          </Marker>
        ))}
      </MapContainer>}
    </div>
  );
}
