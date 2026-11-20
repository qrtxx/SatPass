import { useEffect, useState } from 'react'
import { api, formatTime } from './api.js'

export default function Catalog({ observer, onChange }) {
  const [search, setSearch] = useState('')
  const [satellites, setSatellites] = useState([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const load = (query) => api(`/satellites${query ? `?${new URLSearchParams({ search: query })}` : ''}`).then(setSatellites)

  useEffect(() => {
    load('').catch((e) => setError(e.message))
  }, [])

  // Runs one request and shows its error, if any, above the table.
  async function act(request) {
    setError('')
    setMessage('')
    try {
      await request()
    } catch (e) {
      setError(e.message)
    }
  }

  const watched = new Set(observer?.watchlist)
  const watchlistUrl = observer && `/observers/${observer.id}/watchlist`

  const watch = (id) =>
    act(async () => {
      await api(watchlistUrl, { method: 'POST', body: { norad_id: id } })
      await onChange()
    })

  const unwatch = (id) =>
    act(async () => {
      await api(`${watchlistUrl}/${id}`, { method: 'DELETE' })
      await onChange()
    })

  const showPosition = (s) =>
    act(async () => {
      const p = await api(`/satellites/${s.NORAD_CAT_ID}/position`)
      setMessage(
        `${s.OBJECT_NAME} is now above ${p.latitude.toFixed(2)}°, ${p.longitude.toFixed(2)}°, ` +
          `${p.altitude_km.toFixed(0)} km up (orbit data ${p.orbit_age_days.toFixed(1)} days old).`,
      )
    })

  const remove = (s) =>
    confirm(`Delete ${s.OBJECT_NAME}? It is also removed from every watchlist.`) &&
    act(async () => {
      await api(`/satellites/${s.NORAD_CAT_ID}`, { method: 'DELETE' })
      await load(search)
      await onChange()
    })

  return (
    <section>
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault()
          act(() => load(search))
        }}
      >
        <label>
          Name or NORAD ID
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="e.g. iss, hst, 25544" />
        </label>
        <button>Search</button>
      </form>
      {message && <p>{message}</p>}
      {error && <p className="error">{error}</p>}
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>NORAD ID</th>
              <th>Orbit data from</th>
              <th>Orbit</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {satellites.map((s) => {
              const id = s.NORAD_CAT_ID
              return (
                <tr key={id}>
                  <td>{s.OBJECT_NAME}</td>
                  <td>{id}</td>
                  <td>{formatTime(s.EPOCH)}</td>
                  <td>{s.period_minutes.toFixed(0)} min</td>
                  <td className="actions">
                    {watched.has(id) ? (
                      <button onClick={() => unwatch(id)}>Unwatch</button>
                    ) : (
                      <button disabled={!observer} onClick={() => watch(id)}>
                        Watch
                      </button>
                    )}
                    <button onClick={() => showPosition(s)}>Where now?</button>
                    <button onClick={() => remove(s)}>Delete</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {satellites.length === 0 && <p>No satellites found.</p>}
    </section>
  )
}
