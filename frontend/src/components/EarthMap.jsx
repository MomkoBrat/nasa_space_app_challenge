import { MapContainer, TileLayer } from 'react-leaflet';

// Basic Earth map. Ranked analog markers will be added later.
export default function EarthMap() {
  return (
    <div className="map earth-map">
      <MapContainer
        center={[15, 0]}
        zoom={1}
        minZoom={1}
        scrollWheelZoom={true}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />
      </MapContainer>
    </div>
  );
}
