// A true equirectangular NASA Blue Marble image is required for a rotatable
// globe. The landing page's Apollo 17 image is a full-disk photograph, which
// cannot be accurately wrapped around a sphere.
// Source: NASA/GSFC Scientific Visualization Studio, Blue Marble mosaic.
export const EARTH_TEXTURE_SOURCES = [
  'https://svs.gsfc.nasa.gov/vis/a000000/a002900/a002915/bluemarble-2048.png',
  // Alternate public copy in case the NASA image CDN blocks cross-origin images.
  'https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg',
];

let texturePromise;

export function preloadEarthTexture() {
  if (!texturePromise) {
    texturePromise = new Promise((resolve, reject) => {
      const trySource = (index) => {
        if (index === EARTH_TEXTURE_SOURCES.length) {
          reject(new Error('The Earth texture could not be downloaded. Check your internet connection.'));
          return;
        }
        const image = new Image();
        image.crossOrigin = 'anonymous';
        image.onload = () => resolve(image);
        image.onerror = () => trySource(index + 1);
        image.src = EARTH_TEXTURE_SOURCES[index];
      };
      trySource(0);
    });
  }
  return texturePromise;
}
