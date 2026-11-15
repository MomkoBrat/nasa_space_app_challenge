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
              <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4.5 16.5c-1.7 1.3-2 4.5-2 4.5s3.2-.3 4.5-2" />
                <path d="m9 15-2.5 2.5-2.2-2.2 2.5-2.5" />
                <path d="m15 9 2.5-2.5 2.2 2.2-2.5 2.5" />
                <path d="M7.2 12.8 11.4 8.6c2.9-2.9 6.4-4.1 10.1-4.1 0 3.7-1.2 7.2-4.1 10.1l-4.2 4.2-6-6Z" />
                <circle cx="15.5" cy="10.5" r="1.6" />
              </svg>
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
