import { useEffect, useState } from 'react'
import { api, formatTime } from './api.js'

const duration = (s) => `${Math.floor(s / 60)} min ${s % 60} s`

export default function Passes({ observer }) {
  const [start, setStart] = useState('') // empty means "now"
  const [hours, setHours] = useState('24')
  const [minElevation, setMinElevation] = useState('')
  const [watchlist, setWatchlist] = useState([])
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!observer) return
    api(`/observers/${observer.id}/watchlist`).then(setWatchlist, (e) => setError(e.message))
  }, [observer])

  if (!observer) return <p>Add a location in the Locations tab first.</p>

  async function predict(event) {
    event.preventDefault()
    const params = new URLSearchParams({ hours })
    if (start) params.set('start', new Date(start).toISOString())
    if (minElevation !== '') params.set('min_elevation', minElevation)
    setLoading(true)
    setError('')
    try {
      setReport(await api(`/observers/${observer.id}/passes?${params}`))
    } catch (e) {
      setError(e.message)
      setReport(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <p>
        Watching from <b>{observer.name}</b>:{' '}
        {watchlist.length ? watchlist.map((s) => s.OBJECT_NAME).join(', ') : 'nothing yet (add satellites in the Satellites tab)'}
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
        <button disabled={loading}>{loading ? 'Calculating…' : 'Predict passes'}</button>
      </form>
      <p className="muted">Orbit data is a snapshot from 4 Nov 2026. If passes are skipped as too old, pick a start near that date.</p>

      {error && <p className="error">{error}</p>}
      {report && (
        <>
          <p>
            {report.passes.length} passes between {formatTime(report.start)} and {formatTime(report.end)}, peaking at least{' '}
            {report.min_elevation_deg}° high. Times are local.
          </p>
          {report.warnings.length > 0 && (
            <ul className="warning">
              {report.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
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
                      <td>{p.name}</td>
                      <td>
                        {formatTime(p.rise.time)} in the {p.rise.compass}
                      </td>
                      <td>
                        {formatTime(p.peak.time)}, {p.peak.elevation_deg}° in the {p.peak.compass}
                      </td>
                      <td>
                        {formatTime(p.set.time)} in the {p.set.compass}
                      </td>
                      <td>{duration(p.duration_seconds)}</td>
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
