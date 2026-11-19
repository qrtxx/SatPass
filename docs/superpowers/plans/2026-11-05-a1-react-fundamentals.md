# A1 — React Fundamentals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Provisional.** Written from `PROJECT.md` §8 before the official A1 brief was published. When the brief arrives, re-check the "Assumptions" section below first. Every task is self-contained, so a changed requirement should only change the tasks it touches.

**Goal:** A single-page React app that shows the ISS's next passes over Almaty, computed in the browser from the bundled CelesTrak snapshot, with a button to swap in live data.

**Architecture:** Orbit math lives in pure functions in `src/lib/` (no React), which are unit-tested with Vitest. `App.jsx` holds all state (satellites, selected satellite, view mode, loading/error) and passes data down to display-only components through props. There is no router yet (A3). The CelesTrak fetch runs inside a click handler (no `useEffect` until week 12).

**Tech Stack:** Vite 8.3, React 19.3, satellite.js 7.1 (SGP4), Vitest 5.1 (lib tests only), oxlint (already set up).

**Spec:** `PROJECT.md` — §6 (algorithms), §7 (architecture), §8 A1 (scope), §9 (tests), §10 (UX).

## Global Constraints

- Fixed observer: Almaty, lat `43.2389`, lon `76.8897`, height `0.8` km.
- Pass search window: next 24 h, 60 s steps, rise/set to 1 s, peak sampled every 10 s, default minimum peak elevation 10°.
- Passes are "above the horizon" only. No visibility check in A1 (that is A2).
- CelesTrak base URL: `https://celestrak.org/NORAD/elements/gp.php`. Never fetch the `starlink` group.
- Every CelesTrak response is cached in localStorage with a `fetchedAt` timestamp and re-fetched only after 2 h.
- `src/lib/` has no React imports. Components only receive data through props.
- Dark theme by default, mobile-first CSS, semantic HTML (`header`, `nav`, `main`, `table`), visible focus styles.
- Times are shown with `Intl.DateTimeFormat` in the user's time zone, including the zone name.
- Small commits: at least one per task.

## Assumptions to re-check against the official brief

| Assumption | Why | If the brief says otherwise |
|---|---|---|
| Vitest is added in A1 (spec lists tests under A4) | Pass math is easy to get wrong, and tests are cheap here | Keep the tests anyway. They don't hurt the grade |
| 2-hour cache is built in A1 (spec puts it in A3) | CelesTrak blocks clients that re-download, and clicking "Load live data" during development would trigger that | Nothing to change |
| Passes are shown for one selected satellite (default ISS), picked by clicking a card | The stations group has several objects with the ISS's orbit (POISK, NAUKA), so a combined list would show duplicates | Drop the selection and map `predictPasses` over all satellites |
| Interactive state = card/table toggle (+ satellite selection) | Spec suggests the toggle, and it doubles as the localStorage item | Add "expand pass details" to `PassCard` |
| No component tests (Testing Library is A4) | UI is verified manually in the browser | Add `@testing-library/react` + `jsdom` |
| `Loader` / `ErrorMessage` / `EmptyState` are inline `<p>` elements | Extracted as components in A3 | Extract them now |

## Before you start (owner action, not part of the tasks)

- [ ] Create the GitHub repository and push `main` (the only unchecked item in PROJECT.md "Setup"). Commits from the tasks below should land on a pushed repo so the grader sees the history.

## File map

| File | Action | Responsibility |
|---|---|---|
| `package.json` | Modify | Add `vitest`, `test` script |
| `src/lib/format.js` (+ `.test.js`) | Create | `azimuthToCompass`, `formatDuration`, `formatTime` |
| `src/lib/orbit.js` (+ `.test.js`) | Create | `toSatrec`, `getPosition`, `getLookAngles` |
| `src/lib/passes.js` (+ `.test.js`) | Create | `refineCrossing`, `findPasses`, `predictPasses` |
| `src/api/celestrak.js` (+ `.test.js`) | Create | `fetchGroup` with 2 h localStorage cache |
| `src/components/Header.jsx`, `NavBar.jsx`, `Footer.jsx` | Create | Page chrome |
| `src/components/SatelliteCard.jsx`, `SatelliteGrid.jsx` | Create | Satellite list |
| `src/components/PassCard.jsx`, `PassTable.jsx` | Create | Two pass views |
| `src/App.jsx` | Replace | State + layout |
| `src/index.css` | Replace | Dark, mobile-first styles |
| `index.html` | Modify | Title, theme color |
| `src/App.css`, `src/assets/*`, `public/icons.svg` | Delete | Vite boilerplate |

Deferred to later assignments on purpose: `groundTrack`, `visibility.js`, `validate.js`, `fetchById`/`searchByName`, hooks, context, router.

---

### Task 1: Test setup + `lib/format.js`

**Files:**
- Modify: `package.json`
- Create: `src/lib/format.js`
- Test: `src/lib/format.test.js`

**Interfaces:**
- Produces: `azimuthToCompass(deg: number): string`, `formatDuration(sec: number): string`, `formatTime(date: Date, timeZone?: string): string`

- [ ] **Step 1: Install Vitest and add the script**

Run: `npm install -D vitest@5.1`

Then add the script in `package.json`:

```json
"scripts": {
  "dev": "vite",
  "build": "vite build",
  "lint": "oxlint",
  "preview": "vite preview",
  "test": "vitest run"
},
```

- [ ] **Step 2: Write the failing test** — `src/lib/format.test.js`

```js
import { describe, expect, it } from 'vitest'
import { azimuthToCompass, formatDuration, formatTime } from './format.js'

describe('azimuthToCompass', () => {
  it.each([
    [0, 'N'],
    [45, 'NE'],
    [90, 'E'],
    [227, 'SW'],
    [350, 'N'],
    [359.9, 'N'],
  ])('%s° → %s', (deg, expected) => {
    expect(azimuthToCompass(deg)).toBe(expected)
  })
})

describe('formatDuration', () => {
  it('shows minutes and seconds', () => {
    expect(formatDuration(380)).toBe('6 min 20 s')
  })
  it('shows only seconds under a minute', () => {
    expect(formatDuration(45)).toBe('45 s')
  })
  it('rounds fractional seconds', () => {
    expect(formatDuration(59.6)).toBe('1 min 0 s')
  })
})

describe('formatTime', () => {
  it('formats in the given time zone with the zone name', () => {
    expect(formatTime(new Date('2026-11-05T15:59:25Z'), 'UTC')).toBe('Thu, 15:59 UTC')
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npm test`
Expected: FAIL — `Failed to resolve import "./format.js"`

- [ ] **Step 4: Write the implementation** — `src/lib/format.js`

```js
const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']

export function azimuthToCompass(deg) {
  return COMPASS[Math.round(deg / 22.5) % 16]
}

export function formatDuration(sec) {
  const total = Math.round(sec)
  const min = Math.floor(total / 60)
  return min ? `${min} min ${total % 60} s` : `${total} s`
}

// timeZone is only passed in tests; the app uses the browser's zone.
export function formatTime(date, timeZone) {
  return new Intl.DateTimeFormat('en-GB', {
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
    timeZoneName: 'short',
  }).format(date)
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm test`
Expected: PASS (10 tests)

- [ ] **Step 6: Commit**

```bash
git add package.json package-lock.json src/lib/format.js src/lib/format.test.js
git commit -m "Add Vitest and format helpers (compass, duration, time)"
```

---

### Task 2: `lib/orbit.js`

**Files:**
- Create: `src/lib/orbit.js`
- Test: `src/lib/orbit.test.js`

**Interfaces:**
- Consumes: satellite.js `json2satrec`, `propagate`, `gstime`, `eciToEcf`, `ecfToLookAngles`, `eciToGeodetic`, `degreesLat`, `degreesLong`. Note: `propagate` returns `null` when SGP4 fails (e.g. decayed satellite).
- Produces:
  - `toSatrec(omm: object): SatRec`
  - `getPosition(satrec, date: Date): { lat, lon, altitudeKm } | null` (degrees)
  - `getLookAngles(satrec, observer: { lat, lon, heightKm }, date: Date): { azimuth, elevation } | null` (degrees; azimuth 0–360, 0 = North)

- [ ] **Step 1: Write the failing test** — `src/lib/orbit.test.js`

```js
import { describe, expect, it } from 'vitest'
import snapshot from '../data/sample-gp.json'
import { getLookAngles, getPosition, toSatrec } from './orbit.js'

const iss = toSatrec(snapshot.find((s) => s.NORAD_CAT_ID === 25544))
const date = new Date('2026-11-05T00:00:00Z')
const almaty = { lat: 43.2389, lon: 76.8897, heightKm: 0.8 }

describe('getPosition', () => {
  it('puts the ISS between 370 and 460 km up', () => {
    const { altitudeKm } = getPosition(iss, date)
    expect(altitudeKm).toBeGreaterThan(370)
    expect(altitudeKm).toBeLessThan(460)
  })
  it('keeps latitude within the orbit inclination (51.6°)', () => {
    expect(Math.abs(getPosition(iss, date).lat)).toBeLessThanOrEqual(51.7)
  })
})

describe('getLookAngles', () => {
  it('returns azimuth in [0, 360) and elevation in [-90, 90] degrees', () => {
    const { azimuth, elevation } = getLookAngles(iss, almaty, date)
    expect(azimuth).toBeGreaterThanOrEqual(0)
    expect(azimuth).toBeLessThan(360)
    expect(elevation).toBeGreaterThanOrEqual(-90)
    expect(elevation).toBeLessThanOrEqual(90)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test`
Expected: FAIL — `Failed to resolve import "./orbit.js"`

- [ ] **Step 3: Write the implementation** — `src/lib/orbit.js`

```js
import {
  degreesLat,
  degreesLong,
  ecfToLookAngles,
  eciToEcf,
  eciToGeodetic,
  gstime,
  json2satrec,
  propagate,
} from 'satellite.js'

const DEG = 180 / Math.PI

export function toSatrec(omm) {
  return json2satrec(omm)
}

export function getPosition(satrec, date) {
  const pv = propagate(satrec, date)
  if (!pv) return null
  const geo = eciToGeodetic(pv.position, gstime(date))
  return { lat: degreesLat(geo.latitude), lon: degreesLong(geo.longitude), altitudeKm: geo.height }
}

export function getLookAngles(satrec, { lat, lon, heightKm = 0 }, date) {
  const pv = propagate(satrec, date)
  if (!pv) return null
  const observer = { latitude: lat / DEG, longitude: lon / DEG, height: heightKm }
  const look = ecfToLookAngles(observer, eciToEcf(pv.position, gstime(date)))
  return { azimuth: (look.azimuth * DEG + 360) % 360, elevation: look.elevation * DEG }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/orbit.js src/lib/orbit.test.js
git commit -m "Add orbit helpers: satrec, position, look angles"
```

---

### Task 3: `lib/passes.js`

**Files:**
- Create: `src/lib/passes.js`
- Test: `src/lib/passes.test.js`

**Interfaces:**
- Consumes: `toSatrec`, `getLookAngles` from Task 2.
- Produces:
  - `refineCrossing(elevationAt: (ms) => deg, a: ms, b: ms): ms` — horizon crossing between `a` and `b`, within 1 s
  - `findPasses(elevationAt, start: ms, end: ms, minElevation = 10): Array<{ rise, set, peak, peakElevation }>` (times in ms)
  - `predictPasses(omm, observer, { start = Date.now(), hours = 24, minElevation = 10 } = {})` returning
    `Array<{ noradId, name, rise: { time: Date, azimuth }, peak: { time: Date, azimuth, elevation }, set: { time: Date, azimuth }, durationSec }>` sorted by rise time

`findPasses` takes an elevation *function* so the tests can use fake ones (spec §9) instead of real orbits.

- [ ] **Step 1: Write the failing test** — `src/lib/passes.test.js`

```js
import { describe, expect, it } from 'vitest'
import snapshot from '../data/sample-gp.json'
import { azimuthToCompass } from './format.js'
import { findPasses, predictPasses, refineCrossing } from './passes.js'

const HOUR = 3_600_000
// Triangle-shaped fake pass: `height` degrees at `center` ms, 0° at center ± height*10 s.
const bump = (center, height) => (t) => height - Math.abs(t - center) / 10_000

describe('refineCrossing', () => {
  it('finds a rising edge to within 1 s', () => {
    expect(Math.abs(refineCrossing(bump(600_000, 30), 300_000, 360_000) - 300_000)).toBeLessThanOrEqual(1000)
  })
  it('finds a setting edge to within 1 s', () => {
    expect(Math.abs(refineCrossing(bump(600_000, 30), 840_000, 900_000) - 900_000)).toBeLessThanOrEqual(1000)
  })
})

describe('findPasses', () => {
  it('finds one pass with rise, set and peak', () => {
    const [pass, ...rest] = findPasses(bump(600_000, 30), 0, HOUR)
    expect(rest).toHaveLength(0)
    expect(Math.abs(pass.rise - 300_000)).toBeLessThanOrEqual(1000)
    expect(Math.abs(pass.set - 900_000)).toBeLessThanOrEqual(1000)
    expect(Math.abs(pass.peak - 600_000)).toBeLessThanOrEqual(10_000)
    expect(pass.peakElevation).toBeGreaterThan(29.4)
  })

  it('finds two passes in order', () => {
    const twoBumps = (t) => Math.max(bump(600_000, 30)(t), bump(2_400_000, 20)(t))
    const passes = findPasses(twoBumps, 0, HOUR)
    expect(passes).toHaveLength(2)
    expect(Math.abs(passes[1].rise - 2_200_000)).toBeLessThanOrEqual(1000)
  })

  it('starts a pass that is already in progress at the start time', () => {
    const [pass] = findPasses(bump(0, 30), 0, HOUR)
    expect(pass.rise).toBe(0)
    expect(Math.abs(pass.set - 300_000)).toBeLessThanOrEqual(1000)
  })

  it('returns nothing when the satellite never rises', () => {
    expect(findPasses(() => -10, 0, HOUR)).toEqual([])
  })

  it('drops passes that peak below the minimum elevation', () => {
    expect(findPasses(bump(600_000, 5), 0, HOUR)).toEqual([])
    expect(findPasses(bump(600_000, 5), 0, HOUR, 0)).toHaveLength(1)
  })
})

describe('predictPasses (ISS over Almaty, snapshot epoch 2026-11-04)', () => {
  // Regression values from the first run; cross-checked by hand against heavens-above.com in Task 8.
  const iss = snapshot.find((s) => s.NORAD_CAT_ID === 25544)
  const almaty = { lat: 43.2389, lon: 76.8897, heightKm: 0.8 }
  const passes = predictPasses(iss, almaty, { start: Date.parse('2026-11-05T00:00:00Z') })

  it('finds 5 passes above 10° in 24 h, sorted by time', () => {
    expect(passes).toHaveLength(5)
    const rises = passes.map((p) => p.rise.time.getTime())
    expect(rises).toEqual([...rises].sort((a, b) => a - b))
  })

  it('first pass rises at ~15:59:26 UTC in the SW and peaks at ~61°', () => {
    const [first] = passes
    expect(Math.abs(first.rise.time - Date.parse('2026-11-05T15:59:26Z'))).toBeLessThanOrEqual(2000)
    expect(azimuthToCompass(first.rise.azimuth)).toBe('SW')
    expect(first.peak.elevation).toBeCloseTo(61.5, 0)
    expect(first.durationSec).toBe(650)
    expect(first).toMatchObject({ noradId: 25544, name: 'ISS (ZARYA)' })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test`
Expected: FAIL — `Failed to resolve import "./passes.js"`

- [ ] **Step 3: Write the implementation** — `src/lib/passes.js`

```js
import { getLookAngles, toSatrec } from './orbit.js'

const STEP_MS = 60_000
const PEAK_STEP_MS = 10_000

// Bisects [a, b], where one end is above the horizon and the other is not, down to 1 s.
export function refineCrossing(elevationAt, a, b) {
  const upAtA = elevationAt(a) > 0
  while (b - a > 1000) {
    const mid = (a + b) / 2
    if (elevationAt(mid) > 0 === upAtA) a = mid
    else b = mid
  }
  return Math.round((a + b) / 2)
}

function findPeak(elevationAt, rise, set) {
  let best = { time: rise, elevation: -90 }
  for (let t = rise; t <= set; t += PEAK_STEP_MS) {
    const elevation = elevationAt(t)
    if (elevation > best.elevation) best = { time: t, elevation }
  }
  return best
}

// shortcut: a pass still in progress at `end` is dropped, and one shorter than 60 s can be missed; fine for a 24 h list.
export function findPasses(elevationAt, start, end, minElevation = 10) {
  const passes = []
  let rise = elevationAt(start) > 0 ? start : null
  for (let t = start + STEP_MS; t <= end; t += STEP_MS) {
    const up = elevationAt(t) > 0
    if (up && rise === null) rise = refineCrossing(elevationAt, t - STEP_MS, t)
    if (!up && rise !== null) {
      const set = refineCrossing(elevationAt, t - STEP_MS, t)
      const peak = findPeak(elevationAt, rise, set)
      if (peak.elevation >= minElevation) {
        passes.push({ rise, set, peak: peak.time, peakElevation: peak.elevation })
      }
      rise = null
    }
  }
  return passes
}

export function predictPasses(omm, observer, { start = Date.now(), hours = 24, minElevation = 10 } = {}) {
  const satrec = toSatrec(omm)
  const look = (t) => getLookAngles(satrec, observer, new Date(t))
  // A failed propagation counts as "below the horizon".
  const elevationAt = (t) => look(t)?.elevation ?? -90
  return findPasses(elevationAt, start, start + hours * 3_600_000, minElevation).map((p) => ({
    noradId: omm.NORAD_CAT_ID,
    name: omm.OBJECT_NAME,
    rise: { time: new Date(p.rise), azimuth: look(p.rise).azimuth },
    peak: { time: new Date(p.peak), azimuth: look(p.peak).azimuth, elevation: p.peakElevation },
    set: { time: new Date(p.set), azimuth: look(p.set).azimuth },
    durationSec: Math.round((p.set - p.rise) / 1000),
  }))
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/passes.js src/lib/passes.test.js
git commit -m "Add pass prediction: 60 s scan, bisection, peak search"
```

---

### Task 4: `api/celestrak.js`

**Files:**
- Create: `src/api/celestrak.js`
- Test: `src/api/celestrak.test.js`

**Interfaces:**
- Produces: `fetchGroup(group: string): Promise<object[]>` — resolves to OMM records. It throws an `Error` with a readable message on a non-OK response, a non-JSON body, or an empty list. Cache key: `satpass.gp.<group>`, value: `{ fetchedAt: ms, data }`.

- [ ] **Step 1: Write the failing test** — `src/api/celestrak.test.js`

```js
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchGroup } from './celestrak.js'

const RECORDS = [{ OBJECT_NAME: 'ISS (ZARYA)', NORAD_CAT_ID: 25544 }]
const KEY = 'satpass.gp.stations'

function memoryStorage() {
  const map = new Map()
  return { getItem: (k) => map.get(k) ?? null, setItem: (k, v) => map.set(k, String(v)) }
}
const okResponse = (body) => ({ ok: true, status: 200, json: async () => body })

beforeEach(() => {
  vi.stubGlobal('localStorage', memoryStorage())
  vi.stubGlobal('fetch', vi.fn(async () => okResponse(RECORDS)))
})
afterEach(() => vi.unstubAllGlobals())

describe('fetchGroup', () => {
  it('fetches the group as JSON and caches it', async () => {
    expect(await fetchGroup('stations')).toEqual(RECORDS)
    expect(fetch).toHaveBeenCalledWith('https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=json')
    expect(JSON.parse(localStorage.getItem(KEY)).data).toEqual(RECORDS)
  })

  it('serves a cache younger than 2 h without fetching', async () => {
    localStorage.setItem(KEY, JSON.stringify({ fetchedAt: Date.now() - 60_000, data: RECORDS }))
    expect(await fetchGroup('stations')).toEqual(RECORDS)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('re-fetches a cache older than 2 h', async () => {
    localStorage.setItem(KEY, JSON.stringify({ fetchedAt: Date.now() - 3 * 3_600_000, data: [] }))
    expect(await fetchGroup('stations')).toEqual(RECORDS)
    expect(fetch).toHaveBeenCalledOnce()
  })

  it('throws on a non-OK response', async () => {
    fetch.mockResolvedValueOnce({ ok: false, status: 403 })
    await expect(fetchGroup('stations')).rejects.toThrow('CelesTrak returned 403')
  })

  it('throws on an empty list', async () => {
    fetch.mockResolvedValueOnce(okResponse([]))
    await expect(fetchGroup('stations')).rejects.toThrow('No satellites')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test`
Expected: FAIL — `Failed to resolve import "./celestrak.js"`

- [ ] **Step 3: Write the implementation** — `src/api/celestrak.js`

```js
const BASE_URL = 'https://celestrak.org/NORAD/elements/gp.php'
// CelesTrak updates every ~2 h and blocks clients that re-download unchanged data.
const MAX_AGE_MS = 2 * 3_600_000

function readCache(key) {
  try {
    return JSON.parse(localStorage.getItem(key))
  } catch {
    return null
  }
}

export async function fetchGroup(group) {
  const key = `satpass.gp.${group}`
  const cached = readCache(key)
  if (cached && Date.now() - cached.fetchedAt < MAX_AGE_MS) return cached.data

  const response = await fetch(`${BASE_URL}?GROUP=${encodeURIComponent(group)}&FORMAT=json`)
  if (!response.ok) throw new Error(`CelesTrak returned ${response.status}`)
  // CelesTrak answers bad queries with plain text, which makes json() throw.
  const data = await response.json()
  if (!Array.isArray(data) || data.length === 0) throw new Error('No satellites in the response')

  try {
    localStorage.setItem(key, JSON.stringify({ fetchedAt: Date.now(), data }))
  } catch {
    // Storage full or blocked: still return the data, just uncached.
  }
  return data
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/celestrak.js src/api/celestrak.test.js
git commit -m "Add CelesTrak fetchGroup with 2-hour localStorage cache"
```

---

### Task 5: Layout — remove boilerplate, dark theme, Header/NavBar/Footer

**Files:**
- Delete: `src/App.css`, `src/assets/hero.png`, `src/assets/react.svg`, `src/assets/vite.svg`, `public/icons.svg`
- Modify: `index.html`
- Replace: `src/index.css`, `src/App.jsx`
- Create: `src/components/Header.jsx`, `src/components/NavBar.jsx`, `src/components/Footer.jsx`

**Interfaces:**
- Produces: `<Header locationName: string />`, `<NavBar />`, `<Footer />`. CSS classes used by later tasks: `.toolbar`, `.status`, `.error`, `.sat-grid`, `.sat-card`, `.sat-card.selected`, `.pass-list`, `.pass-card`, `.table-scroll`.

- [ ] **Step 1: Delete boilerplate**

```bash
git rm src/App.css src/assets/hero.png src/assets/react.svg src/assets/vite.svg public/icons.svg
```

- [ ] **Step 2: Update `index.html`** — replace the `<title>` line and add two meta tags after the viewport meta:

```html
    <meta name="description" content="Predict when satellites pass over your city." />
    <meta name="theme-color" content="#0b0f17" />
    <title>SatPass</title>
```

- [ ] **Step 3: Replace `src/index.css`**

```css
:root {
  color-scheme: dark;
  --bg: #0b0f17;
  --surface: #141a26;
  --border: #253047;
  --text: #d8dee9;
  --muted: #8b95a7;
  --accent: #7aa2f7;
  --danger: #f7768e;
  font-family: system-ui, sans-serif;
  line-height: 1.5;
  background: var(--bg);
  color: var(--text);
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

a {
  color: var(--accent);
}

:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

button {
  font: inherit;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
}

button[aria-pressed='true'] {
  border-color: var(--accent);
  color: var(--accent);
}

button:disabled {
  opacity: 0.6;
  cursor: progress;
}

.site-header,
main,
.site-footer {
  max-width: 60rem;
  margin: 0 auto;
  padding: 1rem;
}

.site-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 1rem;
  border-bottom: 1px solid var(--border);
}

.logo,
.location {
  margin: 0;
}

.logo {
  font-size: 1.25rem;
}

.location,
.status,
.site-footer,
caption,
dt {
  color: var(--muted);
}

.nav-list {
  display: flex;
  gap: 1rem;
  list-style: none;
  margin: 0;
  padding: 0;
}

.site-footer {
  font-size: 0.875rem;
  border-top: 1px solid var(--border);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.error {
  color: var(--danger);
}

.sat-grid,
.pass-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
  list-style: none;
  padding: 0;
}

@media (min-width: 40rem) {
  .sat-grid,
  .pass-list {
    grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
  }
}

.sat-card,
.pass-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.75rem;
}

.sat-card.selected {
  border-color: var(--accent);
}

.sat-card h3,
.pass-card h3 {
  margin: 0 0 0.5rem;
  font-size: 1rem;
}

dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.25rem 0.75rem;
  margin: 0 0 0.75rem;
}

dd {
  margin: 0;
}

.table-scroll {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  text-align: left;
  padding: 0.5rem;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

caption {
  text-align: left;
  padding-bottom: 0.5rem;
}
```

- [ ] **Step 4: Create the components**

`src/components/NavBar.jsx`:

```jsx
export default function NavBar() {
  return (
    <nav aria-label="Main">
      <ul className="nav-list">
        <li>
          <a href="#passes">Passes</a>
        </li>
        <li>
          <a href="#satellites">Satellites</a>
        </li>
      </ul>
    </nav>
  )
}
```

`src/components/Header.jsx`:

```jsx
import NavBar from './NavBar.jsx'

export default function Header({ locationName }) {
  return (
    <header className="site-header">
      <h1 className="logo">SatPass</h1>
      <p className="location">Location: {locationName}</p>
      <NavBar />
    </header>
  )
}
```

`src/components/Footer.jsx`:

```jsx
export default function Footer() {
  return (
    <footer className="site-footer">
      <p>
        Orbital data from <a href="https://celestrak.org">CelesTrak</a>. Positions computed with{' '}
        <a href="https://github.com/shashwatak/satellite-js">satellite.js</a>.
      </p>
    </footer>
  )
}
```

- [ ] **Step 5: Replace `src/App.jsx`** with the skeleton

```jsx
import Footer from './components/Footer.jsx'
import Header from './components/Header.jsx'

const ALMATY = { name: 'Almaty', lat: 43.2389, lon: 76.8897, heightKm: 0.8 }

export default function App() {
  return (
    <>
      <Header locationName={ALMATY.name} />
      <main>
        <section id="passes" aria-labelledby="passes-title">
          <h2 id="passes-title">Next passes</h2>
        </section>
        <section id="satellites" aria-labelledby="satellites-title">
          <h2 id="satellites-title">Satellites</h2>
        </section>
      </main>
      <Footer />
    </>
  )
}
```

- [ ] **Step 6: Verify**

Run: `npm run build && npm run lint`
Expected: build succeeds, 0 lint errors.

Run `npm run dev` and open the URL it prints. Expected: dark page with the SatPass header, "Location: Almaty", two nav links that jump to the sections, and the footer. Tab through the page: every link shows a blue focus ring. At 375 px width (DevTools device toolbar) nothing scrolls horizontally.

- [ ] **Step 7: Commit**

```bash
git add -A index.html src
git commit -m "Replace Vite boilerplate with dark mobile-first layout"
```

---

### Task 6: Satellite cards from the snapshot

**Files:**
- Create: `src/components/SatelliteCard.jsx`, `src/components/SatelliteGrid.jsx`
- Replace: `src/App.jsx`

**Interfaces:**
- Consumes: `src/data/sample-gp.json` (array of OMM records: `OBJECT_NAME`, `NORAD_CAT_ID`, `INCLINATION`, `MEAN_MOTION`, …)
- Produces: `<SatelliteCard satellite selected: bool onSelect: (noradId) => void />`, `<SatelliteGrid satellites selectedId onSelect />`. App state: `satellites`, `selectedId` (default `25544`), derived `selected`.

- [ ] **Step 1: Create `src/components/SatelliteCard.jsx`**

```jsx
export default function SatelliteCard({ satellite, selected, onSelect }) {
  const periodMin = 1440 / satellite.MEAN_MOTION
  return (
    <article className={selected ? 'sat-card selected' : 'sat-card'}>
      <h3>{satellite.OBJECT_NAME}</h3>
      <dl>
        <dt>NORAD ID</dt>
        <dd>{satellite.NORAD_CAT_ID}</dd>
        <dt>Inclination</dt>
        <dd>{satellite.INCLINATION.toFixed(1)}°</dd>
        <dt>Orbit period</dt>
        <dd>{periodMin.toFixed(1)} min</dd>
      </dl>
      <button type="button" aria-pressed={selected} onClick={() => onSelect(satellite.NORAD_CAT_ID)}>
        {selected ? 'Showing passes' : 'Show passes'}
      </button>
    </article>
  )
}
```

- [ ] **Step 2: Create `src/components/SatelliteGrid.jsx`**

```jsx
import SatelliteCard from './SatelliteCard.jsx'

export default function SatelliteGrid({ satellites, selectedId, onSelect }) {
  return (
    <ul className="sat-grid">
      {satellites.map((sat) => (
        <li key={sat.NORAD_CAT_ID}>
          <SatelliteCard satellite={sat} selected={sat.NORAD_CAT_ID === selectedId} onSelect={onSelect} />
        </li>
      ))}
    </ul>
  )
}
```

- [ ] **Step 3: Replace `src/App.jsx`**

```jsx
import { useState } from 'react'
import Footer from './components/Footer.jsx'
import Header from './components/Header.jsx'
import SatelliteGrid from './components/SatelliteGrid.jsx'
import snapshot from './data/sample-gp.json'

const ALMATY = { name: 'Almaty', lat: 43.2389, lon: 76.8897, heightKm: 0.8 }
const ISS_ID = 25544

export default function App() {
  const [satellites] = useState(snapshot)
  const [selectedId, setSelectedId] = useState(ISS_ID)
  const selected = satellites.find((s) => s.NORAD_CAT_ID === selectedId) ?? satellites[0]

  return (
    <>
      <Header locationName={ALMATY.name} />
      <main>
        <section id="passes" aria-labelledby="passes-title">
          <h2 id="passes-title">Next passes: {selected.OBJECT_NAME}</h2>
        </section>
        <section id="satellites" aria-labelledby="satellites-title">
          <h2 id="satellites-title">Satellites</h2>
          <SatelliteGrid satellites={satellites} selectedId={selected.NORAD_CAT_ID} onSelect={setSelectedId} />
        </section>
      </main>
      <Footer />
    </>
  )
}
```

- [ ] **Step 4: Verify**

Run: `npm run build && npm run lint`
Expected: build succeeds, 0 lint errors.

In `npm run dev`: 20 cards appear, one column on a phone and several on desktop. ISS (ZARYA) is outlined, and its button reads "Showing passes". Clicking "Show passes" on HST changes the passes heading to "Next passes: HST" and moves the outline.

- [ ] **Step 5: Commit**

```bash
git add src/App.jsx src/components/SatelliteCard.jsx src/components/SatelliteGrid.jsx
git commit -m "Render snapshot satellites as selectable cards"
```

---

### Task 7: Pass views (cards / table) with a remembered toggle

**Files:**
- Create: `src/components/PassCard.jsx`, `src/components/PassTable.jsx`
- Replace: `src/App.jsx`

**Interfaces:**
- Consumes: `predictPasses` (Task 3), `azimuthToCompass`, `formatDuration`, `formatTime` (Task 1).
- Produces: `<PassCard pass />`, `<PassTable passes />`. App state `view: 'cards' | 'table'`, stored in localStorage under `satpass.view`.

- [ ] **Step 1: Create `src/components/PassCard.jsx`**

```jsx
import { azimuthToCompass, formatDuration, formatTime } from '../lib/format.js'

export default function PassCard({ pass }) {
  return (
    <article className="pass-card">
      <h3>
        <time dateTime={pass.rise.time.toISOString()}>{formatTime(pass.rise.time)}</time>
      </h3>
      <dl>
        <dt>Rises</dt>
        <dd>{azimuthToCompass(pass.rise.azimuth)}</dd>
        <dt>Sets</dt>
        <dd>{azimuthToCompass(pass.set.azimuth)}</dd>
        <dt>Max height</dt>
        <dd>{Math.round(pass.peak.elevation)}°</dd>
        <dt>Duration</dt>
        <dd>{formatDuration(pass.durationSec)}</dd>
      </dl>
    </article>
  )
}
```

- [ ] **Step 2: Create `src/components/PassTable.jsx`**

```jsx
import { azimuthToCompass, formatDuration, formatTime } from '../lib/format.js'

export default function PassTable({ passes }) {
  return (
    <div className="table-scroll">
      <table>
        <caption>Upcoming passes</caption>
        <thead>
          <tr>
            <th scope="col">Rise time</th>
            <th scope="col">Rises</th>
            <th scope="col">Max height</th>
            <th scope="col">Sets</th>
            <th scope="col">Duration</th>
          </tr>
        </thead>
        <tbody>
          {passes.map((pass) => (
            <tr key={pass.rise.time.getTime()}>
              <td>
                <time dateTime={pass.rise.time.toISOString()}>{formatTime(pass.rise.time)}</time>
              </td>
              <td>{azimuthToCompass(pass.rise.azimuth)}</td>
              <td>{Math.round(pass.peak.elevation)}°</td>
              <td>{azimuthToCompass(pass.set.azimuth)}</td>
              <td>{formatDuration(pass.durationSec)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 3: Replace `src/App.jsx`**

```jsx
import { useMemo, useState } from 'react'
import Footer from './components/Footer.jsx'
import Header from './components/Header.jsx'
import PassCard from './components/PassCard.jsx'
import PassTable from './components/PassTable.jsx'
import SatelliteGrid from './components/SatelliteGrid.jsx'
import snapshot from './data/sample-gp.json'
import { predictPasses } from './lib/passes.js'

const ALMATY = { name: 'Almaty', lat: 43.2389, lon: 76.8897, heightKm: 0.8 }
const ISS_ID = 25544
const VIEW_KEY = 'satpass.view'

function readSavedView() {
  try {
    return localStorage.getItem(VIEW_KEY) === 'table' ? 'table' : 'cards'
  } catch {
    return 'cards'
  }
}

export default function App() {
  const [satellites] = useState(snapshot)
  const [selectedId, setSelectedId] = useState(ISS_ID)
  const [view, setView] = useState(readSavedView)
  const [start] = useState(() => Date.now())

  const selected = satellites.find((s) => s.NORAD_CAT_ID === selectedId) ?? satellites[0]
  // ~1,500 SGP4 calls: only redo them when the satellite changes, not on every toggle.
  const passes = useMemo(() => predictPasses(selected, ALMATY, { start }), [selected, start])

  function changeView(next) {
    setView(next)
    try {
      localStorage.setItem(VIEW_KEY, next)
    } catch {
      // Private mode: the choice just isn't remembered.
    }
  }

  return (
    <>
      <Header locationName={ALMATY.name} />
      <main>
        <section id="passes" aria-labelledby="passes-title">
          <h2 id="passes-title">Next passes: {selected.OBJECT_NAME}</h2>
          <p className="status">Over {ALMATY.name} in the next 24 h, peaking above 10°.</p>
          <div className="toolbar" role="group" aria-label="Pass view">
            <button type="button" aria-pressed={view === 'cards'} onClick={() => changeView('cards')}>
              Cards
            </button>
            <button type="button" aria-pressed={view === 'table'} onClick={() => changeView('table')}>
              Table
            </button>
          </div>
          {passes.length === 0 ? (
            <p>No passes above 10° in the next 24 hours.</p>
          ) : view === 'table' ? (
            <PassTable passes={passes} />
          ) : (
            <ol className="pass-list">
              {passes.map((pass) => (
                <li key={pass.rise.time.getTime()}>
                  <PassCard pass={pass} />
                </li>
              ))}
            </ol>
          )}
        </section>
        <section id="satellites" aria-labelledby="satellites-title">
          <h2 id="satellites-title">Satellites</h2>
          <SatelliteGrid satellites={satellites} selectedId={selected.NORAD_CAT_ID} onSelect={setSelectedId} />
        </section>
      </main>
      <Footer />
    </>
  )
}
```

- [ ] **Step 4: Verify**

Run: `npm test && npm run build && npm run lint`
Expected: all pass.

In `npm run dev`: the ISS passes show as cards with local times (e.g. `Thu, 20:59 GMT+5` in Almaty). Switch to "Table": the same passes appear as a table, and on a 375 px screen the table scrolls sideways inside its box, not the page. Reload: the table view is still selected. Select a satellite with no passes above 10° (try a few): the empty message shows.

- [ ] **Step 5: Commit**

```bash
git add src/App.jsx src/components/PassCard.jsx src/components/PassTable.jsx
git commit -m "Show predicted passes as cards or table, remember the choice"
```

---

### Task 8: "Load live data" button + final check

**Files:**
- Modify: `src/App.jsx`
- Modify: `PROJECT.md` (tick the A1 checkboxes)

**Interfaces:**
- Consumes: `fetchGroup` (Task 4).
- Produces: App state `source: 'snapshot' | 'live'`, `loading: bool`, `error: string | null`. `satellites` becomes settable.

- [ ] **Step 1: Edit `src/App.jsx`**

Add the import:

```jsx
import { fetchGroup } from './api/celestrak.js'
```

Replace `const [satellites] = useState(snapshot)` with:

```jsx
  const [satellites, setSatellites] = useState(snapshot)
  const [source, setSource] = useState('snapshot')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
```

Add this handler right after `changeView`:

```jsx
  async function handleLoadLive() {
    setLoading(true)
    setError(null)
    try {
      setSatellites(await fetchGroup('stations'))
      setSource('live')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }
```

Replace the status paragraph and toolbar with:

```jsx
          <p className="status">
            Over {ALMATY.name} in the next 24 h, peaking above 10°. Orbit data:{' '}
            {source === 'live' ? 'live from CelesTrak' : 'bundled snapshot (4 Nov 2026)'}.
          </p>
          <div className="toolbar">
            <div className="toolbar" role="group" aria-label="Pass view">
              <button type="button" aria-pressed={view === 'cards'} onClick={() => changeView('cards')}>
                Cards
              </button>
              <button type="button" aria-pressed={view === 'table'} onClick={() => changeView('table')}>
                Table
              </button>
            </div>
            <button type="button" onClick={handleLoadLive} disabled={loading}>
              {loading ? 'Loading…' : 'Load live data'}
            </button>
          </div>
          {loading && <p role="status">Loading live orbit data from CelesTrak…</p>}
          {error && (
            <p role="alert" className="error">
              Could not load live data ({error}). Still showing the {source === 'live' ? 'last live' : 'snapshot'} data.
            </p>
          )}
```

- [ ] **Step 2: Verify the happy path**

Run: `npm test && npm run build && npm run lint`
Expected: all pass.

In `npm run dev`, click "Load live data". Expected: the button shows "Loading…" and is disabled, then the status line says "live from CelesTrak" and the satellite grid now holds the live `stations` group. The ISS stays selected and its passes are recomputed. In DevTools → Network, click again: **no** new request to celestrak.org (served from the 2 h cache).

- [ ] **Step 3: Verify the error path**

DevTools → Application → Local Storage: delete `satpass.gp.stations`. DevTools → Network: set throttling to "Offline". Click "Load live data". Expected: a red message "Could not load live data (Failed to fetch). Still showing …", and the passes are unchanged. Set throttling back to "No throttling".

- [ ] **Step 4: Cross-check against heavens-above.com**

Open heavens-above.com → ISS → set location to Almaty (43.2389 N, 76.8897 E) → "All passes" (not only visible ones). Compare the next 2–3 passes with the app (after loading live data). Expected: start times within ~1 min, max heights within a few degrees, same rise/set compass directions. Heavens-above lists rise from 10° by default, so its start times can be a minute or two after ours (we count from 0°). Note the comparison in the commit message.

- [ ] **Step 5: Tick the A1 items in `PROJECT.md` §8** (change `- [ ]` to `- [x]` for each finished A1 line).

- [ ] **Step 6: Commit**

```bash
git add src/App.jsx PROJECT.md
git commit -m "Add Load live data button with loading and error states"
```

---

## Spec coverage (A1, PROJECT.md §8)

| A1 requirement | Task |
|---|---|
| Layout: Header, NavBar, Footer, mobile-first dark CSS | 5 |
| SatelliteCard + SatelliteGrid from snapshot | 6 |
| `lib/orbit.js` + `lib/passes.js`, above-horizon passes | 2, 3 |
| PassCard + PassTable: rise time, direction, peak, duration | 7 |
| One piece of interactive state | 6 (selection), 7 (view toggle) |
| "Load live data" in click handler, `response.ok`, loading/error | 4, 8 |
| View remembered in localStorage | 7 |
| Small-step commit history | every task |
| Done when: ISS passes over Almaty; matches heavens-above | 7, 8 |
