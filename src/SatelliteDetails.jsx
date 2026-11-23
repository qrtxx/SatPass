import { useEffect, useRef, useState } from 'react'
import { api, daysSince, formatDuration, formatPassTime, formatTime, MAX_SELECTED } from './api.js'
import { formatLat, formatLon, orbitShape } from './orbit.js'

const REFRESH_MS = 5000

export default function SatelliteDetails({ noradId, observer, selected, onToggle, onClose, onChange, onDeleted }) {
  const [sat, setSat] = useState(null)
  const [error, setError] = useState('')
  const [position, setPosition] = useState(null)
  const [positionError, setPositionError] = useState('')
  const [report, setReport] = useState(null)
  const [passesError, setPassesError] = useState('')
  const [actionError, setActionError] = useState('')
  const observerId = observer?.id
  const panelRef = useRef(null)
  const headingRef = useRef(null)

  // Bring the panel into view and move focus to it: on narrow screens it opens above the table.
  useEffect(() => {
    const { top } = panelRef.current.getBoundingClientRect()
    // Only when its top is off screen (narrow layout); instant, because a smooth scroll gets cancelled as content loads.
    if (top < 0 || top > innerHeight) panelRef.current.scrollIntoView({ block: 'start' })
    headingRef.current.focus({ preventScroll: true })
  }, [])

  useEffect(() => {
    api(`/satellites/${noradId}`).then(setSat, (e) => setError(e.message))
  }, [noradId])

  // Where it is now, refreshed every 5 s. Stops when the panel closes or the position can't be computed.
  useEffect(() => {
    let current = true
    const load = () =>
      api(`/satellites/${noradId}/position`).then(
        (p) => current && (setPosition(p), setPositionError('')),
        (e) => {
          if (!current) return
          setPositionError(e.message)
          clearInterval(timer)
        },
      )
    const timer = setInterval(load, REFRESH_MS)
    load()
    return () => {
      current = false
      clearInterval(timer)
    }
  }, [noradId])

  useEffect(() => {
    if (!observerId) return
    let current = true
    const params = new URLSearchParams({ norad_id: noradId, hours: 24 })
    api(`/observers/${observerId}/passes?${params}`).then(
      (r) => current && (setReport(r), setPassesError('')),
      (e) => current && setPassesError(e.message),
    )
    return () => {
      current = false
    }
  }, [noradId, observerId])

  const watched = observer?.watchlist.includes(noradId)
  const isSelected = selected.has(noradId)

  async function run(action) {
    setActionError('')
    try {
      await action()
    } catch (e) {
      setActionError(e.message)
    }
  }

  const toggleWatch = () =>
    run(async () => {
      const url = `/observers/${observerId}/watchlist`
      if (watched) await api(`${url}/${noradId}`, { method: 'DELETE' })
      else await api(url, { method: 'POST', body: { norad_id: noradId } })
      await onChange()
    })

  const remove = () =>
    confirm(`Delete ${sat.OBJECT_NAME}? It is also removed from every watchlist.`) &&
    run(async () => {
      await api(`/satellites/${noradId}`, { method: 'DELETE' })
      onDeleted(noradId)
    })

  const shape = sat && orbitShape(sat)

  return (
    <aside ref={panelRef} className="card details" aria-label="Satellite details">
      <div className="details-head">
        <h2 ref={headingRef} tabIndex={-1}>
          {sat?.OBJECT_NAME ?? `NORAD ${noradId}`}
        </h2>
        <button className="icon" onClick={onClose} aria-label="Close details">
          ✕
        </button>
      </div>

      {error && <p className="error">{error}</p>}
      {!sat && !error && <p className="muted">Loading…</p>}
      {sat && (
        <>
          <p className="muted">
            NORAD <span className="mono">{noradId}</span> · orbit data from {formatTime(sat.EPOCH)},{' '}
            <span className="mono">{daysSince(sat.EPOCH).toFixed(1)}</span> days old
          </p>

          <dl className="facts">
            <dt>Orbit</dt>
            <dd className="mono">
              {shape.perigeeKm.toFixed(0)} × {shape.apogeeKm.toFixed(0)} km · {sat.INCLINATION.toFixed(1)}° · every{' '}
              {sat.period_minutes.toFixed(1)} min
            </dd>
            <dt>Now</dt>
            <dd>
              {positionError ? (
                <span className="error">{positionError}</span>
              ) : position ? (
                <span className="mono">
                  {formatLat(position.latitude)}, {formatLon(position.longitude)} · {position.altitude_km.toFixed(0)} km up
                </span>
              ) : (
                <span className="muted">Locating…</span>
              )}
            </dd>
          </dl>

          <div className="actions">
            <label className="check-label">
              <input
                type="checkbox"
                checked={isSelected}
                disabled={!isSelected && selected.size >= MAX_SELECTED}
                onChange={() => onToggle(noradId)}
              />
              Selected for passes
            </label>
            {observer && <button onClick={toggleWatch}>{watched ? '★ Watched' : '☆ Watch'}</button>}
            <button className="danger" onClick={remove}>
              Delete
            </button>
          </div>
          {actionError && <p className="error">{actionError}</p>}

          <h3>Next passes over {observer?.name ?? 'your location'} (24 h)</h3>
          {!observer && <p className="muted">Add a location in the Locations tab to see passes.</p>}
          {passesError && <p className="error">{passesError}</p>}
          {report && report.warnings.map((w) => <p key={w} className="warning">{w}</p>)}
          {report && report.passes.length === 0 && (
            <p className="muted">No passes higher than {report.min_elevation_deg}° in the next 24 hours.</p>
          )}
          {report && report.passes.length > 0 && (
            <ul className="pass-list">
              {report.passes.map((p) => (
                <li key={p.rise.time}>
                  <span className="mono">{formatPassTime(p.rise.time)}</span>
                  <span>
                    rises {p.rise.compass} → <b>{p.peak.elevation_deg}°</b> in the {p.peak.compass} → sets {p.set.compass} ·{' '}
                    {formatDuration(p.duration_seconds)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </aside>
  )
}
