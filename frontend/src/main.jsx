import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import 'leaflet/dist/leaflet.css';
import './App.css';
import App from './App.jsx';
import LandingPage from './components/LandingPage.jsx';

// Hash navigation works on static hosting without a router or server rewrites.
// /#/explore opens the existing explorer; the default URL opens the start page.
function routeFromHash() {
  return window.location.hash === '#/explore' ? 'explore' : 'home';
}

function Root() {
  const [route, setRoute] = useState(routeFromHash);

  useEffect(() => {
    const update = () => setRoute(routeFromHash());
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);

  return route === 'explore' ? <App /> : <LandingPage />;
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
