import React, { useEffect, useRef, useState } from 'react';
import ReactDOM from 'react-dom/client';
import 'leaflet/dist/leaflet.css';
import './App.css';
import './components/LandingPage.css';
import App from './App.jsx';
import LandingPage from './components/LandingPage.jsx';
import { MARS_IMAGE } from './planetImages.js';

// Hash navigation works on static hosting without a router or server rewrites.
function routeFromHash() {
  return window.location.hash === '#/explore' ? 'explore' : 'home';
}

function toBox(rect) {
  return { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
}

function Root() {
  const [route, setRoute] = useState(routeFromHash);
  const [flight, setFlight] = useState(null);
  const frameRef = useRef([]);

  useEffect(() => {
    const update = () => setRoute(routeFromHash());
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);

  // The rocket button changes pages but leaves a floating real-Mars image behind.
  // Its animated endpoint is measured from the actual planet in the explorer header.
  const beginMission = (planetElement) => {
    if (flight) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !planetElement) {
      window.location.hash = '#/explore';
      setRoute('explore');
      return;
    }
    setFlight({ phase: 'start', start: toBox(planetElement.getBoundingClientRect()) });
    window.location.hash = '#/explore';
    setRoute('explore');
    window.scrollTo({ top: 0, behavior: 'instant' });
  };

  useEffect(() => {
    if (!flight || flight.phase !== 'start' || route !== 'explore') return;

    // The first frame mounts the explorer; the second frame starts the FLIP motion.
    const frame1 = window.requestAnimationFrame(() => {
      const target = document.querySelector('.explorer-mars-planet');
      if (!target) {
        setFlight(null);
        return;
      }
      const destination = toBox(target.getBoundingClientRect());
      const frame2 = window.requestAnimationFrame(() => {
        setFlight((current) => current?.phase === 'start'
          ? { ...current, phase: 'moving', destination }
          : current);
      });
      frameRef.current.push(frame2);
    });
    frameRef.current.push(frame1);
    return () => frameRef.current.forEach((frame) => window.cancelAnimationFrame(frame));
  }, [route, flight?.phase]);

  useEffect(() => {
    if (flight?.phase !== 'moving') return;
    const timeout = window.setTimeout(() => setFlight(null), 1260);
    return () => window.clearTimeout(timeout);
  }, [flight?.phase]);

  const flying = flight?.phase === 'moving';
  const flightBox = flying ? flight.destination : flight?.start;

  return (
    <>
      <div className={route === 'explore' && flight ? 'explorer-route-entering' : ''}>
        {route === 'explore' ? <App /> : <LandingPage onBegin={beginMission} />}
      </div>
      {flight && flightBox && (
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
