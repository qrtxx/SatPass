# SatPass — Satellite Pass Predictor

CSS 225 Web Programming Fundamentals · Fall 2026 · Project spec (written 2026-11-05)

## 1. Topic & description

**Topic:** Satellite Pass Predictor: Track Satellites Over Your City

**Description:**
A web app that shows when satellites like the ISS, Hubble, and Starlink will be visible to the naked eye from the user's location. Using real orbital data, it predicts when each satellite will rise and set, how high it will climb in the sky, and whether it will be visible. Users can see live satellite positions on a map, filter upcoming passes, keep a watchlist, and explore details for each satellite.

## 2. Why this project is not "just an API wrapper"

The API returns raw orbital elements: numbers like inclination and mean motion. Everything the user sees comes from logic written in this project:

- Where each satellite is right now, and the track it follows over the ground.
- When it rises above the user's horizon and when it sets, how high it climbs, and in which compass direction.
- Whether it can actually be seen. It is visible only if the satellite is in sunlight while the observer's sky is dark.

This logic is plain JavaScript functions with no React in them, which makes it easy to unit-test (see §9).

## 3. Users & core user stories

Main user: anyone curious about the night sky. They will usually open the app on a phone while standing outside.

1. As a user, I set my location so that predictions are calculated for where I am.
2. As a user, I see tonight's visible passes, sorted by time, so I know when to go outside.
3. As a user, for each pass I see the start time, the direction the satellite rises from and sets toward, its maximum height, and how long it lasts.
4. As a user, I filter passes by satellite group, minimum height, and visible-only.
5. As a user, I search the satellite catalog and open a detail page for any satellite.
6. As a user, I see a satellite's live position and ground track on a map.
7. As a user, I add satellites to a watchlist that stays saved after I close the browser.

## 4. Data sources (checked 2026-11-05)

| Source | Use | Key | CORS | Notes |
|---|---|---|---|---|
| CelesTrak GP API: `https://celestrak.org/NORAD/elements/gp.php` | Orbital elements | No | ✅ `*` | `?GROUP=visual&FORMAT=json` returns a group, `?CATNR=25544&FORMAT=json` returns one satellite by NORAD ID, `?NAME=STARLINK-1234&FORMAT=json` searches by name |
| OpenStreetMap tiles (through Leaflet) | Base map | No | n/a | Show the required attribution on the map |
| Browser Geolocation API | "Use my location" | n/a | n/a | Optional. Falls back to the form if the user denies permission |

**CelesTrak rules to respect:**
- The data refreshes about every 2 hours. CelesTrak blocks clients that keep re-downloading the same data, so the app must cache every response in localStorage with a `fetchedAt` timestamp and re-fetch only once the cached copy is more than 2 hours old.
- Orbital elements get less accurate as they age. Show their age, for example "orbit data from 6 h ago", and warn when it is more than 3 days old.
- The `starlink` group has thousands of objects. Never compute passes for the whole group. Starlink satellites are added one at a time, either by name search or by NORAD ID.

Example JSON record (OMM format):
```json
{ "OBJECT_NAME": "ISS (ZARYA)", "NORAD_CAT_ID": 25544, "EPOCH": "2026-11-04T21:15:15.204960",
  "MEAN_MOTION": 15.49180468, "ECCENTRICITY": 0.00072122, "INCLINATION": 51.6327, ... }
```

## 5. Tech stack

| Tool | Version checked | Purpose |
|---|---|---|
| Vite + React | vite 8.3, react 19.3 | App |
| React Router | 8.5 | Pages |
| satellite.js | 7.1 | Orbit propagation (SGP4) and coordinate conversions |
| Leaflet + react-leaflet | 1.9 / 5.0 | Map |
| Vitest + Testing Library | 5.1 / 16.3 | Tests |
| ESLint + Prettier | latest | Code quality |
| Vercel | — | Hosting |

satellite.js 7.1 functions used (each was checked to exist and the pass check was run against live ISS data): `json2satrec`, `propagate`, `gstime`, `eciToEcf`, `ecfToLookAngles`, `eciToGeodetic`, `degreesLat`, `degreesLong`, `jday`, `sunPos`. `sunPos(jday(date)).rsun` returns the Sun's position in **AU**; multiply by 149,597,870.7 to get km.

## 6. Core algorithms (`src/lib/`)

### 6.1 Satellite position
```
satrec  = json2satrec(ommRecord)
eci     = propagate(satrec, date).position          // km
gmst    = gstime(date)
geo     = eciToGeodetic(eci, gmst)                   // lat/lon in radians
look    = ecfToLookAngles(observer, eciToEcf(eci, gmst))  // azimuth/elevation in radians
observer = { latitude: rad, longitude: rad, height: km }
```

### 6.2 Pass prediction
1. Step through the next 24 hours in 60-second steps and compute the elevation at each step.
2. A pass is any run of steps where the elevation is above 0°.
3. Find the exact rise and set times by bisection between the last step below the horizon and the first step above it, accurate to 1 second (about 6 halvings).
4. Find the peak by sampling inside the pass every 10 seconds and keeping the highest elevation.
5. Drop passes whose peak elevation is below the user's minimum (default 10°). Passes lower than that are hidden by buildings and haze.

Output:
```js
{ noradId, name,
  rise: { time, azimuth }, peak: { time, azimuth, elevation }, set: { time, azimuth },
  durationSec, visible, visibleFrom, visibleTo }
```

### 6.3 Visibility (naked eye)
A pass is **visible** if at some moment during it all three of these are true:
- **Satellite is sunlit.** Use a cylindrical shadow model. With `s` as the unit vector toward the Sun and `r` as the satellite's position: if `r·s > 0`, the satellite is sunlit. Otherwise it is sunlit only if the distance from the Earth–Sun line, `|r − (r·s)s|`, is greater than 6371 km (Earth's radius).
- **Observer's sky is dark.** The Sun's elevation at the observer is below −6° (civil twilight). Compute it by passing the Sun's position in km through the same `eciToEcf` → `ecfToLookAngles` steps used for satellites.
- **Satellite is above the minimum elevation.**

### 6.4 Ground track
Propagate over one orbital period (`1440 / MEAN_MOTION` minutes) in 30-second steps. Split the line into separate segments wherever the longitude jumps by more than 180°, which happens when it crosses the antimeridian. Without the split, the map draws a line across the whole world.

### 6.5 Helpers
- `azimuthToCompass(deg)` returns one of 16 compass points: `["N","NNE","NE",…][Math.round(deg/22.5) % 16]`.
- `formatDuration(sec)` returns text like `"6 min 20 s"`.
- `validateLocation({lat, lon})`: latitude must be between −90 and 90, longitude between −180 and 180, and both must be numbers.
- Times are shown with `Intl.DateTimeFormat` in the user's time zone.

### 6.6 Performance
For example, 100 satellites × 1,440 steps is about 144,000 propagations, which is fine to run once but not on every render.
- Wrap the pass computation in `useMemo`, keyed on the satellite data, the observer and the time window.
- Compute passes only for the watchlist and the currently filtered satellites, never for the whole catalog.
- Stretch goal: move the computation into a Web Worker.

## 7. Architecture

### 7.1 Folder structure
```
SatPass/
├─ public/
├─ src/
│  ├─ lib/                 # pure functions, no React, unit-tested
│  │  ├─ orbit.js          # toSatrec, getPosition, getLookAngles, groundTrack
│  │  ├─ passes.js         # predictPasses, refineCrossing
│  │  ├─ visibility.js     # sunEci, isSunlit, sunElevation
│  │  ├─ format.js         # azimuthToCompass, formatDuration, formatTime
│  │  └─ validate.js       # validateLocation
│  ├─ api/
│  │  └─ celestrak.js      # fetchGroup, fetchById, searchByName + 2-hour cache
│  ├─ hooks/
│  │  ├─ useSatellites.js  # { data, loading, error, reload }
│  │  ├─ useNow.js         # current time, ticks every second
│  │  └─ useLocalStorage.js
│  ├─ context/
│  │  └─ ObserverContext.jsx   # location, shared by all pages
│  ├─ components/          # reusable UI pieces
│  ├─ pages/               # one component per route
│  ├─ data/
│  │  └─ sample-gp.json    # offline snapshot of 20 satellites (stations + Hubble), used in A1 and in tests
│  ├─ App.jsx
│  └─ main.jsx
├─ .env.example
├─ vercel.json
└─ PROJECT.md
```

### 7.2 Routes
| Path | Page | Content |
|---|---|---|
| `/` | Tonight | Location summary, the next visible passes from the watchlist, a countdown to the next one |
| `/passes` | Passes | All upcoming passes with filters |
| `/satellites` | Catalog | Search and group filter, grid of satellite cards |
| `/satellites/:noradId` | Satellite detail | Orbit facts, live position on the map, ground track, next passes, watchlist button |
| `/watchlist` | Watchlist | Saved satellites |
| `/settings` | Settings | Location form, default minimum elevation |
| `*` | Not found | Link back home |

### 7.3 Components
`Layout`, `Header`, `NavBar`, `Footer`, `LocationBadge`, `SatelliteCard`, `SatelliteGrid`, `PassCard`, `PassTable`, `PassFilters`, `SearchBox`, `LocationForm`, `WatchButton`, `SatelliteMap`, `Countdown`, `OrbitFacts`, `Loader`, `ErrorMessage`, `EmptyState`.

Each component has one job. Components that only display data receive it through props, and the data loading happens in pages or hooks.

### 7.4 State
| State | Where it lives | Persisted |
|---|---|---|
| Observer location | `ObserverContext` | localStorage |
| Watchlist (NORAD IDs) | `useLocalStorage` | localStorage |
| Orbital data | `useSatellites` → api cache | localStorage, 2-hour cache |
| Filters (group, minimum elevation, visible only, search) | Page state, mirrored in URL search params from A3 on | URL |
| Filtered and sorted passes | **Derived** with `useMemo`, never stored as separate state | — |
| Current time | `useNow` | — |

## 8. Assignment roadmap

> The project starts in week 10. A1 builds on everything taught up to then (weeks 1–10: HTML/CSS, JavaScript, DOM, localStorage, fetch/async, React basics). Each later assignment adds that week's topic.

### Setup (before A1)
- [x] Choose the idea, check that the API works and allows browser requests
- [x] Submit the topic in the Google Form
- [x] Scaffold with `npm create vite@latest` (React template) and `git init`
- [ ] Create the GitHub repository and push `main`
- [x] Save `src/data/sample-gp.json`, a snapshot of the `stations` group plus Hubble

### A1 (Week 10): React fundamentals, plus everything from weeks 1–9
**Goal:** a working app. Passes are computed for one fixed location (Almaty), starting from the bundled snapshot, with a button to load live data.
- [ ] Layout: `Header`, `NavBar`, `Footer`, mobile-first responsive CSS with a dark theme by default
- [ ] `SatelliteCard` and `SatelliteGrid` rendering the snapshot
- [ ] `lib/orbit.js` and `lib/passes.js`: predict passes above the horizon (no visibility check yet)
- [ ] `PassCard` and `PassTable` showing rise time, direction, peak elevation and duration
- [ ] One piece of interactive state, for example toggling between the card and table views or expanding a pass to see details
- [ ] Week 9 skills: a "Load live data" button that fetches the `stations` group from CelesTrak inside its click handler (`async`/`await`, `response.ok` check, loading and error states). This needs no `useEffect`, which comes in week 12.
- [ ] Week 7 skills: the chosen view (cards or table) is remembered in localStorage
- [ ] Commit history shows the work in small steps

**Done when:** opening the app shows the ISS's next passes over Almaty from the snapshot. "Load live data" replaces the snapshot with live data and shows loading and error states. The pass times roughly match those on heavens-above.com, a well-known satellite-pass prediction site, for the same location.

### A2 (Week 11): State & forms
**Goal:** the app works for the user's own location and preferences.
- [ ] `LocationForm` with controlled inputs: city name, latitude, longitude, and a select with preset cities (Almaty, Astana, Shymkent, …)
- [ ] Validation with inline error messages, linked to the inputs with `aria-describedby`
- [ ] "Use my location" button using the Geolocation API, with an error message if permission is denied
- [ ] Observer state lifted into `ObserverContext`, so every page uses the same location
- [ ] `lib/visibility.js`: sunlit and dark-sky checks, then mark each pass as visible or not
- [ ] `PassFilters`: satellite group, minimum elevation slider, visible-only checkbox, time window (tonight, 24 h, 48 h)
- [ ] `SearchBox` for searching satellites by name
- [ ] Filtered and sorted lists are derived values, not separate state
- [ ] Watchlist add and remove, saved in localStorage

**Done when:** changing the location, the filters or the watchlist updates the passes immediately, and everything except the filters survives a page reload.

### A3 (Week 12): Routing & data fetching
**Goal:** live data, multiple pages.
- [ ] React Router with every route in §7.2, including the 404 page
- [ ] `api/celestrak.js` and the `useSatellites` hook replace A1's "Load live data" button with automatic loading: `useEffect` with fetch, `AbortController` to cancel requests on cleanup, `response.ok` check, 2-hour localStorage cache
- [ ] A clear UI for each data state: `Loader` while loading, `ErrorMessage` with a Retry button on error, `EmptyState` for an empty list or no passes in the window
- [ ] Satellite detail page that fetches by `CATNR` and shows a "not found" state for an unknown ID
- [ ] `SatelliteMap`: live position updated every second (`setInterval` in `useEffect`, cleared on cleanup) plus the ground track (§6.4)
- [ ] Countdown to the next visible pass on the home page
- [ ] Filters kept in URL search params, so a filtered view can be shared as a link
- [ ] Orbit data age shown, with a warning when it is old

**Done when:** every page loads live data. Turning off the network (DevTools → Offline) shows an error with Retry or uses cached data, and refreshing any URL works.

### A4 (Week 13): Code quality & deployment
**Goal:** tested, linted, reviewed, deployed.
- [ ] Vitest unit tests for all of `src/lib/` (see §9)
- [ ] Testing Library component tests for `LocationForm` validation, `PassFilters` and `ErrorMessage` Retry
- [ ] ESLint and Prettier set up, with no lint errors; scripts `lint`, `format`, `test`
- [ ] Git: feature branch, then a pull request, then a review from a classmate, then the review comments addressed, then merge
- [ ] `.env` with values read from `import.meta.env`, and `.env.example` committed:
  ```
  VITE_CELESTRAK_BASE_URL=https://celestrak.org/NORAD/elements/gp.php
  VITE_DEFAULT_CITY=Almaty
  VITE_DEFAULT_LAT=43.2389
  VITE_DEFAULT_LON=76.8897
  ```
  (`VITE_` variables end up in the public bundle, so never put secrets in them.)
- [ ] `vite build` passes, then the app is deployed to Vercel with an SPA rewrite in `vercel.json` so that deep links like `/satellites/25544` work:
  ```json
  { "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }
  ```
- [ ] Lighthouse on the deployed URL: Accessibility ≥ 90 and Performance ≥ 80, with screenshots in the README
- [ ] README: description, screenshots, live URL, how to run the app, how to run the tests

**Done when:** a public Vercel URL works on a phone, the tests pass, the pull request is merged, and the Lighthouse scores are recorded.

### Week 15: Endterm & final project
- Demo (about 5 minutes): set the location, show tonight's visible ISS pass, open its detail page with the live map, apply filters, show the watchlist, show the tests and the deployed URL.
- Technical reflection: why the pass logic is kept in pure functions, how the caching works and why it is needed, one bug and how DevTools helped find it, what you would do next.

## 9. Testing plan

| Unit | Test cases |
|---|---|
| `passes.js` | Pass detection with a fake elevation function: one pass, two passes, a pass already in progress at the start time, no passes. Bisection result accurate to 1 s. Minimum-elevation filter. |
| `visibility.js` | Point on the Sun side → sunlit. Point directly behind Earth → in shadow. Point behind Earth but further than Earth's radius from the Earth–Sun line → sunlit. Sun elevation sign at a known noon and midnight. |
| `orbit.js` | Ground track splits at the antimeridian. ISS altitude from the snapshot is between 370 and 460 km. |
| `format.js` | 0° → N, 45° → NE, 350° → N, 359.9° → N. Duration formatting. |
| `validate.js` | Edge values (−90, 90, −180, 180), out-of-range values, empty input, non-numeric input. |
| `celestrak.js` | Mock `fetch`: cache hit inside 2 h means no fetch, a stale cache is re-fetched, a non-OK response throws. |
| Components | Form shows errors and blocks submit. Filters change the visible rows. Retry calls `reload`. |

Tests use `sample-gp.json` and fixed dates, never live data, so results are always the same.

## 10. UX, accessibility, responsive design

- **Mobile-first.** The main use case is a phone outdoors at night.
- **Dark theme by default.** Use low-glare colors so they don't ruin night vision; a red "night mode" is a stretch goal.
- **Semantic HTML.** Use `<header>`, `<nav>`, `<main>`, `<table>` for passes, and `<form>` with a `<label>` for every input.
- **The map is not accessible on its own.** Always show a text version next to it: the latitude and longitude, the altitude, and the next pass.
- **Visible and not visible must not be shown by color alone.** Add an icon and a text label as well.
- **Keyboard and motion.** Everything works with the keyboard and has visible focus styles. Respect `prefers-reduced-motion` for the live animations.
- **Times are always local.** Each time shows its time zone, and the countdown says e.g. "in 2 h 14 min".

## 11. Risks & mitigations

| Risk | Mitigation |
|---|---|
| CelesTrak blocks the app for fetching too often | 2-hour cache, no polling, fetch only the groups needed |
| CelesTrak is down | Use cached data plus a banner. In development, fall back to `sample-gp.json` |
| Orbital data goes stale, so predictions drift | Show the data age and warn after 3 days |
| Pass computation is slow | `useMemo`, compute only what is needed, 60 s steps; Web Worker as a stretch goal |
| User denies geolocation | Manual form and preset cities |
| Deep links return 404 on Vercel | SPA rewrite in `vercel.json` |
| Leaflet's default marker icons break under Vite | Use `CircleMarker` instead of the default `Marker` |

## 12. Stretch goals (only if time allows)

- Sky chart: an SVG polar plot of the pass path (azimuth and elevation).
- Browser notification 5 minutes before a watched pass (Notification API).
- Calendar export of a pass (`.ics` file).
- Estimated brightness (magnitude).
- Red night-vision mode.
- Web Worker for the pass computation.
- PWA for offline use.

## 13. Glossary

- **NORAD ID / CATNR:** a satellite's catalog number. The ISS is 25544.
- **TLE / OMM:** two formats for orbital elements, which describe a satellite's orbit at a moment called the *epoch*. This project uses OMM JSON.
- **SGP4:** the standard model for predicting where a satellite will be from its orbital elements, as implemented in satellite.js.
- **Azimuth:** compass direction (0° = North, 90° = East).
- **Elevation:** angle above the horizon (0° = horizon, 90° = straight up).
- **Pass:** one appearance of a satellite above the horizon, from rise to set.
- **Ground track:** the path on Earth's surface directly beneath the satellite.
- **Civil twilight:** the Sun between 0° and −6° below the horizon. The sky is dark enough for satellites to be seen once the Sun is below −6°.
