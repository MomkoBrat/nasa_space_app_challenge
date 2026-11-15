import { useRef } from 'react';
import { EARTH_IMAGE, MARS_IMAGE } from '../planetImages.js';
import './LandingPage.css';

export default function LandingPage({ onBegin }) {
  const marsRef = useRef(null);

  const beginMission = (event) => {
    if (onBegin) {
      event.preventDefault();
      onBegin(marsRef.current);
    }
  };
  return (
    <div className="landing-page">
      <main className="landing-scene" aria-labelledby="landing-title">
        <div className="landing-stars landing-stars-far" aria-hidden="true" />
        <div className="landing-stars landing-stars-near" aria-hidden="true" />
        <div className="landing-stars landing-stars-extra" aria-hidden="true" />
        <div className="landing-nebula" aria-hidden="true" />

        <nav className="landing-navigation" aria-label="Landing page navigation">
          <a className="landing-brand" href="#/" aria-label="Mars-to-Earth Analog Finder home">
            <span className="landing-brand-mark" aria-hidden="true">✦</span>
            <span>NASA SPACE APPS <span className="landing-brand-split">/</span> ANALOG FINDER</span>
          </a>
          <span className="landing-nav-detail">PLANETARY EXPLORATION · 2026</span>
        </nav>

        <div className="landing-planet landing-planet-mars" ref={marsRef} aria-hidden="true">
          <img src={MARS_IMAGE} alt="" decoding="async" fetchPriority="high" />
        </div>
        <div className="landing-planet landing-planet-earth" aria-hidden="true">
          <img src={EARTH_IMAGE} alt="" decoding="async" fetchPriority="high" />
        </div>

        <div className="landing-main-content">
          <h1 id="landing-title">
            Discover Earth&apos;s closest <span>matches to Mars.</span>
          </h1>
          <p className="landing-description">
            Use planetary terrain data to find Earth environments that can help us
            prepare for future missions to Mars.
          </p>

          <a className="landing-cta" href="#/explore" onClick={beginMission}>
            <span>Begin the Mission</span>
            <span className="landing-cta-arrow" aria-hidden="true">
              <img className="landing-cta-rocket" src="/rocket-custom.png" alt="" />
            </span>
          </a>
          <p className="landing-cta-note">MARS TERRAIN <span>·</span> EARTH ANALOGS <span>·</span> SCIENTIFIC DISCOVERY</p>
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
