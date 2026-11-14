// PLACEHOLDER — owned by Person 3, who will replace this file.
// Implements the DATA_CONTRACT §5 signature and v1 math so the UI can be built now:
//   distance = sqrt(sum(w_i * ((mars_i - earth_i) / scale_i)^2)),  score = 100 / (1 + distance)
// Lower distance ranks better. The score is display-only, NOT a percentage of Mars equivalence.

const EARTH_RADIUS_KM = 6371;

function haversineKm(lat1, lon1, lat2, lon2) {
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(a));
}

export function rankEarthCells({
  marsSite,
  earthCells,
  weights,
  scales,
  limit = 10,
  minSeparationKm = 50,
}) {
  const keys = Object.keys(weights);
  const mars = marsSite.features;
  if (!keys.every((k) => Number.isFinite(mars[k]))) return [];

  const scored = [];
  for (const cell of earthCells) {
    const f = cell.features;
    // Skip cells with missing / non-finite values — never substitute 0.
    if (!keys.every((k) => Number.isFinite(f[k]))) continue;

    const contributions = {};
    let sum = 0;
    for (const k of keys) {
      const term = weights[k] * ((mars[k] - f[k]) / scales[k]) ** 2;
      contributions[k] = term;
      sum += term;
    }
    const distance = Math.sqrt(sum);
    scored.push({
      id: cell.id,
      lat: cell.lat,
      lon: cell.lon,
      distance,
      score: 100 / (1 + distance),
      contributions,
      features: f,
    });
  }

  scored.sort((a, b) => a.distance - b.distance);

  // Greedy diversification: keep a result only if it is far enough from all kept ones.
  const results = [];
  for (const r of scored) {
    if (results.length >= limit) break;
    if (results.every((k) => haversineKm(k.lat, k.lon, r.lat, r.lon) >= minSeparationKm)) {
      results.push(r);
    }
  }
  return results;
}
