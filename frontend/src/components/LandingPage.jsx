import './LandingPage.css';

// Full-disk imagery from NASA; the two assets remain unmodified photographs/mosaics.
// Earth: NASA Apollo 17 "Blue Marble" (transparent cutout hosted on Wikimedia Commons).
// Mars: NASA/JPL/USGS Viking Orbiter 1 global color mosaic, PIA00407.
const EARTH_IMAGE =
  'https://upload.wikimedia.org/wikipedia/commons/thumb/1/19/Blue_Marble_transparent.png/960px-Blue_Marble_transparent.png';
const MARS_IMAGE =
  'https://d2pn8kiwq2w21t.cloudfront.net/original_images/jpegPIA00407.jpg';

export default function LandingPage() {
  return (
    <div className="landing-page">
      <main className="landing-scene" aria-labelledby="landing-title">
        <div className="landing-stars landing-stars-far" aria-hidden="true" />
        <div className="landing-stars landing-stars-near" aria-hidden="true" />
        <div className="landing-nebula" aria-hidden="true" />

        <nav className="landing-navigation" aria-label="Landing page navigation">
          <a className="landing-brand" href="#/" aria-label="Mars-to-Earth Analog Finder home">
            <span className="landing-brand-mark" aria-hidden="true">✦</span>
            <span>NASA SPACE APPS <span className="landing-brand-split">/</span> ANALOG FINDER</span>
          </a>
          <div className="landing-nav-right">
            <span className="landing-nav-detail">PLANETARY EXPLORATION · 2026</span>
            <a className="landing-nav-link" href="#/explore">
              Explore <span aria-hidden="true">↗</span>
            </a>
          </div>
        </nav>

        <div className="landing-planet landing-planet-mars" aria-hidden="true">
          <img src={MARS_IMAGE} alt="" decoding="async" fetchPriority="high" />
        </div>
        <div className="landing-planet landing-planet-earth" aria-hidden="true">
          <img src={EARTH_IMAGE} alt="" decoding="async" fetchPriority="high" />
        </div>

        <div className="landing-main-content">
          <p className="landing-eyebrow">
            <span className="landing-eyebrow-line" />
            EXPLORE THE SCIENCE OF SIMILAR WORLDS
            <span className="landing-eyebrow-line" />
          </p>
          <h1 id="landing-title">
            Discover Earth&apos;s closest <span>matches to Mars.</span>
          </h1>
          <p className="landing-description">
            Use planetary terrain data to find Earth environments that can help us
            prepare for future missions to Mars.
          </p>

          <a className="landing-cta" href="#/explore">
            <span>Begin the Mission</span>
            <span className="landing-cta-arrow" aria-hidden="true">→</span>
          </a>
          <p className="landing-cta-note">MARS TERRAIN <span>·</span> EARTH ANALOGS <span>·</span> SCIENTIFIC DISCOVERY</p>
        </div>

        <div className="landing-corner-label landing-corner-label-earth" aria-hidden="true">
          <span className="landing-label-line" />
          <span>01 / EARTH</span>
        </div>
        <div className="landing-corner-label landing-corner-label-mars" aria-hidden="true">
          <span className="landing-label-line" />
          <span>02 / MARS</span>
        </div>

        <footer className="landing-credits">
          Imagery: <a href="https://commons.wikimedia.org/wiki/File:Blue_Marble_transparent.png" target="_blank" rel="noreferrer">NASA / Apollo 17</a>
          <span aria-hidden="true"> · </span>
          <a href="https://science.nasa.gov/photojournal/global-color-views-of-mars/" target="_blank" rel="noreferrer">NASA / JPL / USGS</a>
        </footer>
      </main>
    </div>
  );
}
