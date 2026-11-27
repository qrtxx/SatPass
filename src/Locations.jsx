import { useState } from 'react'
import { api } from './api.js'
import PlaceSearch from './PlaceSearch.jsx'

const FIELDS = [
  ['name', 'Name'],
  ['latitude', 'Latitude'],
  ['longitude', 'Longitude'],
  ['elevation_m', 'Elevation (m)'],
  ['min_elevation_deg', 'Min. peak height °'],
]
const EMPTY = { name: '', latitude: '', longitude: '', elevation_m: '0', min_elevation_deg: '10' }

export default function Locations({ observers, onChange }) {
  const [form, setForm] = useState(EMPTY)
  const [editingId, setEditingId] = useState(null)
  const [error, setError] = useState('')
  const [hint, setHint] = useState('') // where the coordinates/elevation came from

  function reset() {
    setForm(EMPTY)
    setEditingId(null)
    setError('')
    setHint('')
  }

  function pickPlace(place) {
    setForm((f) => ({
      ...f,
      name: f.name || place.name,
      latitude: String(place.latitude),
      longitude: String(place.longitude),
      elevation_m: String(place.elevation_m ?? f.elevation_m),
    }))
    setHint(`Coordinates and elevation of ${place.name} from GeoNames. You can still adjust them.`)
  }

  // Elevation of an arbitrary point, estimated from the nearest town or village (GeoNames).
  function estimateElevation(latitude, longitude) {
    api(`/places/nearest?${new URLSearchParams({ latitude, longitude })}`).then(
      (p) => {
        setForm((f) => ({ ...f, name: f.name || `Near ${p.name}`, elevation_m: String(p.elevation_m ?? f.elevation_m) }))
        setHint(
          p.elevation_m == null
            ? `Nearest place: ${p.name} (${p.distance_km} km), elevation unknown; enter it yourself.`
            : `Elevation ≈ ${p.elevation_m} m, taken from ${p.name} (${p.distance_km} km away). Adjust it if you know better.`,
        )
      },
      (e) => setHint(`${e.message}; enter the elevation yourself.`),
    )
  }

  function useMyLocation() {
    if (!navigator.geolocation) return setHint("This browser can't share your location; search for a place instead.")
    setHint('Asking your browser for your location…')
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const latitude = coords.latitude.toFixed(4)
        const longitude = coords.longitude.toFixed(4)
        setForm((f) => ({ ...f, latitude, longitude }))
        estimateElevation(latitude, longitude)
      },
      (e) => setHint(`Couldn't get your location (${e.message}). Search for a place or type the coordinates.`),
      { timeout: 15000 },
    )
  }

  async function save(event) {
    event.preventDefault()
    // The API validates the values; empty number fields become null and get a readable error back.
    const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, k === 'name' ? v : v === '' ? null : Number(v)]))
    try {
      if (editingId) await api(`/observers/${editingId}`, { method: 'PATCH', body })
      else await api('/observers', { method: 'POST', body })
      reset()
      await onChange()
    } catch (e) {
      setError(e.message)
    }
  }

  async function remove(o) {
    if (!confirm(`Delete ${o.name} and its watchlist?`)) return
    try {
      await api(`/observers/${o.id}`, { method: 'DELETE' })
      if (editingId === o.id) reset()
      await onChange()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <section className="card">
      <h2>{editingId ? 'Edit location' : 'Add a location'}</h2>
      <PlaceSearch onPick={pickPlace} />
      <p className="actions">
        <button type="button" onClick={useMyLocation}>
          Use my current location
        </button>
        <button
          type="button"
          disabled={form.latitude === '' || form.longitude === ''}
          onClick={() => estimateElevation(form.latitude, form.longitude)}
        >
          Estimate elevation
        </button>
      </p>
      {hint && (
        <p className="muted" role="status">
          {hint}
        </p>
      )}
      <form onSubmit={save} className="row">
        {FIELDS.map(([key, label]) => (
          <label key={key}>
            {label}
            <input
              type={key === 'name' ? 'text' : 'number'}
              step={key === 'name' ? undefined : 'any'}
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
            />
          </label>
        ))}
        <button>{editingId ? 'Save changes' : 'Add location'}</button>
        {editingId && (
          <button type="button" onClick={reset}>
            Cancel
          </button>
        )}
      </form>
      {error && <p className="error">{error}</p>}
      <p className="muted small">
        Places from <a href="https://www.geonames.org/">GeoNames</a> (CC BY 4.0).
      </p>

      <div className="scroll">
        <table>
          <thead>
            <tr>
              {FIELDS.map(([key, label]) => (
                <th key={key}>{label}</th>
              ))}
              <th>Watching</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {observers.map((o) => (
              <tr key={o.id}>
                {FIELDS.map(([key]) => (
                  <td key={key}>{o[key]}</td>
                ))}
                <td>{o.watchlist.length}</td>
                <td className="actions">
                  <button
                    onClick={() => {
                      setEditingId(o.id)
                      setForm(Object.fromEntries(FIELDS.map(([key]) => [key, String(o[key])])))
                      setError('')
                    }}
                  >
                    Edit
                  </button>
                  <button onClick={() => remove(o)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
