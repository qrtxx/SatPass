import { useState } from 'react'
import { api } from './api.js'

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

  function reset() {
    setForm(EMPTY)
    setEditingId(null)
    setError('')
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
    <section>
      <h2>{editingId ? 'Edit location' : 'Add a location'}</h2>
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
