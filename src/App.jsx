import { useCallback, useEffect, useState } from 'react'
import { api, MAX_SELECTED } from './api.js'
import Catalog from './Catalog.jsx'
import Locations from './Locations.jsx'
import Passes from './Passes.jsx'
import SatelliteDetails from './SatelliteDetails.jsx'

const TABS = { passes: 'Passes', catalog: 'Satellites', locations: 'Locations' }

export default function App() {
  const [tab, setTab] = useState('catalog')
  const [observers, setObservers] = useState([])
  const [observerId, setObserverId] = useState(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(() => new Set()) // ticked NORAD IDs, shared by all tabs
  const [detailsId, setDetailsId] = useState(null)
  const [passesSource, setPassesSource] = useState('watchlist')
  const [autoPredict, setAutoPredict] = useState(false)
  const [catalogVersion, setCatalogVersion] = useState(0) // bumped when a satellite is deleted

  const reloadObservers = useCallback(
    () =>
      api('/observers').then(
        (list) => {
          setObservers(list)
          // Keep the selected location if it still exists, otherwise pick the first one.
          setObserverId((id) => (list.some((o) => o.id === id) ? id : (list[0]?.id ?? null)))
          setError('')
        },
        (e) => setError(e.message),
      ),
    [],
  )

  useEffect(() => {
    reloadObservers()
  }, [reloadObservers])

  const toggleSelected = useCallback((id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else if (next.size < MAX_SELECTED) next.add(id)
      return next
    })
  }, [])

  function predictSelected() {
    setPassesSource('selected')
    setAutoPredict(true) // the Passes tab runs the prediction as soon as it opens
    setTab('passes')
  }

  function satelliteDeleted(id) {
    setSelected((prev) => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
    setDetailsId(null)
    setCatalogVersion((v) => v + 1)
    reloadObservers() // it may have been on the watchlist
  }

  const observer = observers.find((o) => o.id === observerId)

  return (
    <>
      <header className="topbar">
        <h1>SatPass</h1>
        <nav aria-label="Sections">
          {Object.entries(TABS).map(([key, label]) => (
            <button key={key} className="tab" aria-current={tab === key ? 'page' : undefined} onClick={() => setTab(key)}>
              {label}
            </button>
          ))}
        </nav>
        <label className="location">
          Location
          <select value={observerId ?? ''} onChange={(e) => setObserverId(Number(e.target.value))}>
            {observers.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </label>
      </header>
      {error && <p className="error">{error}</p>}
      <div className={detailsId ? 'layout with-details' : 'layout'}>
        <main>
          {tab === 'passes' && (
            <Passes
              key={observerId}
              observer={observer}
              source={passesSource}
              onSourceChange={setPassesSource}
              selected={selected}
              onOpen={setDetailsId}
              autoPredict={autoPredict}
              onAutoPredicted={() => setAutoPredict(false)}
            />
          )}
          {/* Kept mounted (only hidden) so the search and page survive switching tabs. */}
          <div hidden={tab !== 'catalog'}>
            <Catalog
              observer={observer}
              selected={selected}
              onToggle={toggleSelected}
              onClear={() => setSelected(new Set())}
              onPredict={predictSelected}
              onOpen={setDetailsId}
              version={catalogVersion}
            />
          </div>
          {tab === 'locations' && <Locations observers={observers} onChange={reloadObservers} />}
        </main>
        {detailsId && (
          <SatelliteDetails
            key={detailsId}
            noradId={detailsId}
            observer={observer}
            selected={selected}
            onToggle={toggleSelected}
            onClose={() => setDetailsId(null)}
            onChange={reloadObservers}
            onDeleted={satelliteDeleted}
          />
        )}
      </div>
    </>
  )
}
