# Landing page integration

The landing screen is in `src/components/LandingPage.jsx` and `LandingPage.css`.
The existing explorer (`src/App.jsx`) is untouched.

## Routes

- `http://localhost:5173/` – landing page
- `http://localhost:5173/#/explore` – existing Mars-to-Earth explorer

The **Begin the Mission** button navigates to `#/explore`. Browser Back returns to
landing. Hash routing avoids adding dependencies or configuring Vercel/Netlify
rewrite rules.

## Planet imagery

The landing page uses direct image URLs to original NASA-sourced imagery:

- Earth: NASA Apollo 17 Blue Marble (transparent cutout, Wikimedia Commons)
  https://commons.wikimedia.org/wiki/File:Blue_Marble_transparent.png
- Mars: NASA/JPL/USGS Viking Orbiter 1 global color view, PIA00407
  https://science.nasa.gov/photojournal/global-color-views-of-mars/

Images require an internet connection. If you need fully offline hosting, download
those exact credited images into `public/assets/` and update the two URL constants
in `LandingPage.jsx` accordingly.

## No dependencies added

Only these existing source files were edited/added:

- Modified: `frontend/src/main.jsx`
- Added: `frontend/src/components/LandingPage.jsx`
- Added: `frontend/src/components/LandingPage.css`

`App.jsx`, `App.css`, `package.json`, and `package-lock.json` are unchanged.
