import { useEffect, useState } from 'react'
import { api, apiPage, daysSince, formatCount, MAX_SELECTED } from './api.js'
import { useAuth } from './useAuth.js'

const PAGE = 50
// CelesTrak groups the API accepts; "active" is every working satellite (~17k).
const GROUPS = ['stations', 'visual', 'active', 'weather', 'science', 'gps-ops', 'galileo', 'starlink']

// query, page (0-based), onSearch and onPage come from the page, which keeps them in the URL.
export default function Catalog({ observer, selected, onToggle, onClear, onPredict, onOpen, version, query, page, onSearch, onPage }) {
  const [result, setResult] = useState(null) // { items, total }
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [group, setGroup] = useState('stations')
  const [importing, setImporting] = useState(false)
  const [reloads, setReloads] = useState(0)

  useEffect(() => {
    let current = true
    const params = new URLSearchParams({ limit: PAGE, offset: page * PAGE })
    if (query) params.set('search', query)
    apiPage(`/satellites?${params}`).then(
      (r) => current && (setResult(r), setError('')),
      (e) => current && setError(e.message),
    )
    return () => {
      current = false // ignore answers to an older search or page
    }
  }, [query, page, version, reloads])

  async function importGroup(event) {
    event.preventDefault()
    setImporting(true)
    setError('')
    setMessage('')
    try {
      const r = await api('/satellites/import', { method: 'POST', body: { group } })
      setMessage(
        `Updated '${r.group}' from CelesTrak: ${formatCount(r.added)} added, ${formatCount(r.updated)} updated, ` +
          `${formatCount(r.unchanged)} unchanged, ${formatCount(r.skipped)} skipped.`,
      )
      setReloads((n) => n + 1)
    } catch (e) {
      setError(e.message)
    } finally {
      setImporting(false)
    }
  }

  const watched = new Set(observer?.watchlist)
  const isAdmin = useAuth().user?.role === 'admin' // only admins may change the catalog
  const full = selected.size >= MAX_SELECTED
  const from = page * PAGE + 1
  const to = result ? Math.min((page + 1) * PAGE, result.total) : 0

  return (
    <section className="card">
      <div className="toolbar">
        {/* Keyed by the search, so Back/Forward refill the box with the search in the URL. */}
        <form
          key={query}
          className="row"
          role="search"
          onSubmit={(e) => {
            e.preventDefault()
            onSearch(new FormData(e.currentTarget).get('q').trim())
          }}
        >
          <label>
            Name or NORAD ID
            <input name="q" defaultValue={query} maxLength={60} placeholder="e.g. iss, starlink, 25544" />
          </label>
          <button>Search</button>
        </form>
{isAdmin && (
        <form className="row" onSubmit={importGroup}>
          <label>
            Satellite group
            <select value={group} onChange={(e) => setGroup(e.target.value)}>
              {GROUPS.map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </label>
          <button disabled={importing}>{importing ? 'Downloading… this can take a minute' : 'Update orbit data'}</button>
        </form>
        )}
      </div>

      <div className="selection-bar" aria-live="polite">
        <span>
          <b>{selected.size}</b> selected
          {full && <span className="muted"> · up to {MAX_SELECTED} satellites at a time</span>}
        </span>
        <button className="primary" disabled={selected.size === 0} onClick={onPredict}>
          Predict passes
        </button>
        <button disabled={selected.size === 0} onClick={onClear}>
          Clear
        </button>
      </div>

      {message && <p className="notice">{message}</p>}
      {error && <p className="error">{error}</p>}

      {result && result.total === 0 ? (
        <p className="empty">{query ? `No satellites match “${query}”.` : 'The catalog is empty. Update orbit data to load satellites.'}</p>
      ) : (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th className="check">
                  <span className="visually-hidden">Selected</span>
                </th>
                <th>Name</th>
                <th>NORAD ID</th>
                <th>Orbit data</th>
                <th>Period</th>
              </tr>
            </thead>
            <tbody>
              {result?.items.map((s) => {
                const id = s.NORAD_CAT_ID
                const isSelected = selected.has(id)
                return (
                  <tr key={id} className={isSelected ? 'selected' : undefined}>
                    <td className="check">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        disabled={!isSelected && full}
                        onChange={() => onToggle(id)}
                        aria-label={`Select ${s.OBJECT_NAME}`}
                      />
                    </td>
                    <td>
                      <button className="link" onClick={() => onOpen(id)}>
                        {s.OBJECT_NAME}
                      </button>
                      {watched.has(id) && (
                        <span className="badge" title="On this location's watchlist">
                          ★ watched
                        </span>
                      )}
                    </td>
                    <td className="mono">{id}</td>
                    <td className="mono">{daysSince(s.EPOCH).toFixed(1)} days old</td>
                    <td className="mono">{s.period_minutes.toFixed(1)} min</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {result && result.total > 0 && (
        <div className="pager">
          <button disabled={page === 0} onClick={() => onPage(page - 1)}>
            ‹ Previous
          </button>
          <span className="mono">
            {formatCount(from)}–{formatCount(to)} of {formatCount(result.total)}
          </span>
          <button disabled={to >= result.total} onClick={() => onPage(page + 1)}>
            Next ›
          </button>
        </div>
      )}
    </section>
  )
}
