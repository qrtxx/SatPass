import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, formatDuration, formatPassTime, formatTime } from './api.js'

export default function Passes({ observer, observersLoaded, source, onSourceChange, selected, onOpen, autoPredict, onAutoPredicted }) {
  const [start, setStart] = useState('') // empty means "now"
  const [hours, setHours] = useState('24')
  const [minElevation, setMinElevation] = useState('')
  const [watchlist, setWatchlist] = useState([])
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(Boolean(autoPredict && observer))

  useEffect(() => {
    if (!observer) return
    api(`/observers/${observer.id}/watchlist`).then(setWatchlist, (e) => setError(e.message))
  }, [observer])

  const noneSelected = source === 'selected' && selected.size === 0

  function switchSource(next) {
    onSourceChange(next)
    setReport(null)
    setError('')
  }

  // Sends the request; the state changes happen when it answers.
  function requestPasses() {
    const params = new URLSearchParams({ hours })
    if (start) params.set('start', new Date(start).toISOString())
    if (minElevation !== '') params.set('min_elevation', minElevation)
    if (source === 'selected') selected.forEach((id) => params.append('norad_id', id))
    return api(`/observers/${observer.id}/passes?${params}`)
      .then(
        (r) => (setReport(r), setError('')),
        (e) => (setError(e.message), setReport(null)),
      )
      .finally(() => setLoading(false))
  }

  function predict(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    requestPasses()
  }

  // Arriving from the Satellites page's "Predict passes": run it once with the default window.
  useEffect(() => {
    if (!autoPredict || !observer) return
    onAutoPredicted()
    requestPasses()
  }, [autoPredict, observer]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!observer)
    return (
      <p className="empty card">
        {observersLoaded ? (
          <>
            Add a location in <Link to="/locations">My locations</Link> first.
          </>
        ) : (
          'Loading your locations…'
        )}
      </p>
    )

  return (
    <section className="card">
      <div className="segmented" role="group" aria-label="Which satellites">
        <button aria-pressed={source === 'watchlist'} onClick={() => switchSource('watchlist')}>
          Watchlist ({watchlist.length})
        </button>
        <button aria-pressed={source === 'selected'} onClick={() => switchSource('selected')}>
          Selected ({selected.size})
        </button>
      </div>

      <p className="muted">
        {source === 'watchlist'
          ? watchlist.length
            ? `Watched from ${observer.name}: ${watchlist.map((s) => s.OBJECT_NAME).join(', ')}`
            : `${observer.name} isn't watching any satellites yet. Open a satellite and press Watch, or use Selected.`
          : noneSelected
            ? 'No satellites selected: tick some on the Satellites page.'
            : `${selected.size} satellite${selected.size === 1 ? '' : 's'} ticked on the Satellites page, from ${observer.name}.`}
      </p>

      <form onSubmit={predict} className="row">
        <label>
          Start (empty = now)
          <input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          Hours ahead (1–72)
          <input type="number" value={hours} onChange={(e) => setHours(e.target.value)} required />
        </label>
        <label>
          Min. peak height °
          <input
            type="number"
            step="any"
            value={minElevation}
            placeholder={String(observer.min_elevation_deg)}
            onChange={(e) => setMinElevation(e.target.value)}
          />
        </label>
        <button className="primary" disabled={loading || noneSelected}>
          {loading ? 'Calculating…' : 'Predict passes'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}
      {report && (
        <>
          <p>
            <b>{report.passes.length}</b> passes between {formatTime(report.start)} and {formatTime(report.end)}, peaking at
            least {report.min_elevation_deg}° high. Times are local.
          </p>
          {report.warnings.map((w) => (
            <p key={w} className="warning">
              {w}
            </p>
          ))}
          {report.passes.length > 0 && (
            <div className="scroll">
              <table>
                <thead>
                  <tr>
                    <th>Satellite</th>
                    <th>Rises</th>
                    <th>Highest point</th>
                    <th>Sets</th>
                    <th>Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {report.passes.map((p) => (
                    <tr key={`${p.norad_id}-${p.rise.time}`}>
                      <td>
                        <button className="link" onClick={() => onOpen(p.norad_id)}>
                          {p.name}
                        </button>
                      </td>
                      <td>
                        <span className="mono">{formatPassTime(p.rise.time)}</span> {p.rise.compass}
                      </td>
                      <td>
                        <span className="mono">{formatPassTime(p.peak.time)}</span> <b>{p.peak.elevation_deg}°</b> {p.peak.compass}
                      </td>
                      <td>
                        <span className="mono">{formatPassTime(p.set.time)}</span> {p.set.compass}
                      </td>
                      <td className="mono">{formatDuration(p.duration_seconds)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  )
}
