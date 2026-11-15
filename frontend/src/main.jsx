import React, { useEffect, useRef, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { flushSync } from 'react-dom';
import 'leaflet/dist/leaflet.css';
import './App.css';
import './components/LandingPage.css';
import App from './App.jsx';
import LandingPage from './components/LandingPage.jsx';
import { MARS_IMAGE } from './planetImages.js';

// Simple hash navigation, supported on static hosts without router configuration.
function routeFromHash() {
  return window.location.hash === '#/explore' ? 'explore' : 'home';
}

function rectToBox(rect) {
  return { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
}

function Root() {
  const [route, setRoute] = useState(routeFromHash);
  const [fallbackFlight, setFallbackFlight] = useState(null);
  const navigating = useRef(false);
  const cachedData = useRef(null);
  const preloadPromise = useRef(null);

  // Warm the lightweight scientific JSON while the landing page is visible.
  // This ensures the explorer's maps and panels exist in the NEW snapshot,
  // so they truly morph in instead of appearing after a loading screen.
  useEffect(() => {
    if (routeFromHash() !== 'home') return;
    preloadPromise.current = Promise.all([
      fetch('/data/mars_cells.json').then((r) => { if (!r.ok) throw new Error('Mars data'); return r.json(); }),
      fetch('/data/earth_cells.json').then((r) => { if (!r.ok) throw new Error('Earth data'); return r.json(); }),
      fetch('/data/features.json').then((r) => { if (!r.ok) throw new Error('Feature configuration'); return r.json(); }),
    ]).then(([mars, earth, config]) => {
      cachedData.current = { marsSites: mars.sites, earthCells: earth.cells, config };
    }).catch(() => {
      // The explorer retains its own existing fetch-and-error handling.
    });
  }, []);

  useEffect(() => {
    const syncRoute = () => setRoute(routeFromHash());
    window.addEventListener('hashchange', syncRoute);
    window.addEventListener('popstate', syncRoute);
    return () => {
      window.removeEventListener('hashchange', syncRoute);
      window.removeEventListener('popstate', syncRoute);
    };
  }, []);

  const enterExplorer = () => {
    window.history.pushState(null, '', '#/explore');
    // View Transitions require a synchronous DOM update to capture the new state.
    flushSync(() => setRoute('explore'));
    window.scrollTo(0, 0);
  };

  const beginMission = async (marsElement) => {
    if (navigating.current) return;
    navigating.current = true;

    // Ordinarily already resolved by the time the user clicks.
    if (preloadPromise.current) await preloadPromise.current;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) {
      enterExplorer();
      navigating.current = false;
      return;
    }

    // Modern browsers: capture the REAL Mars element on both pages, then
    // physically interpolate its size and position as the interface morphs.
    if (typeof document.startViewTransition === 'function') {
      try {
        const transition = document.startViewTransition(enterExplorer);
        transition.finished.catch(() => {}).finally(() => {
          navigating.current = false;
        });
        return;
      } catch {
        // Fall back to an animated image overlay if the browser declines it.
      }
    }

    // Browser fallback: move an identical Mars image across the viewport.
    if (marsElement) {
      setFallbackFlight({ phase: 'start', start: rectToBox(marsElement.getBoundingClientRect()) });
    }
    enterExplorer();
    if (!marsElement) navigating.current = false;
  };

  useEffect(() => {
    if (fallbackFlight?.phase !== 'start' || route !== 'explore') return undefined;
    let nextFrame;
    const frame = requestAnimationFrame(() => {
      const target = document.querySelector('.explorer-mars-planet');
      if (!target) {
        setFallbackFlight(null);
        navigating.current = false;
        return;
      }
      const destination = rectToBox(target.getBoundingClientRect());
      nextFrame = requestAnimationFrame(() => {
        setFallbackFlight((current) => current?.phase === 'start'
          ? { ...current, phase: 'moving', destination }
          : current);
      });
    });
    return () => {
      cancelAnimationFrame(frame);
      if (nextFrame) cancelAnimationFrame(nextFrame);
    };
  }, [fallbackFlight?.phase, route]);

  useEffect(() => {
    if (fallbackFlight?.phase !== 'moving') return undefined;
    const timeout = window.setTimeout(() => {
      setFallbackFlight(null);
      navigating.current = false;
    }, 1510);
    return () => window.clearTimeout(timeout);
  }, [fallbackFlight?.phase]);

  const flying = fallbackFlight?.phase === 'moving';
  const flightBox = flying ? fallbackFlight.destination : fallbackFlight?.start;

  return (
    <>
      <div className={route === 'explore' && fallbackFlight ? 'explorer-route-entering' : ''}>
        {route === 'explore' ? <App initialData={cachedData.current} /> : <LandingPage onBegin={beginMission} />}
      </div>
      {fallbackFlight && flightBox && (
        <div
          className={`mars-flight ${flying ? 'mars-flight-moving' : ''}`}
          style={{
            left: flightBox.left,
            top: flightBox.top,
            width: flightBox.width,
            height: flightBox.height,
          }}
          aria-hidden="true"
        >
          <img src={MARS_IMAGE} alt="" />
        </div>
      )}
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
