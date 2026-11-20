import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import Catalog from './Catalog.jsx'
import Locations from './Locations.jsx'
import Passes from './Passes.jsx'

const TABS = { passes: 'Passes', catalog: 'Satellites', locations: 'Locations' }

export default function App() {
  const [tab, setTab] = useState('passes')
  const [observers, setObservers] = useState([])
  const [observerId, setObserverId] = useState(null)
  const [error, setError] = useState('')

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

  const observer = observers.find((o) => o.id === observerId)

  return (
    <>
      <header>
        <h1>SatPass</h1>
        <label>
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
      <nav>
        {Object.entries(TABS).map(([key, label]) => (
          <button key={key} aria-current={tab === key ? 'page' : undefined} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </nav>
      <main>
        {error && <p className="error">{error}</p>}
        {tab === 'passes' && <Passes key={observerId} observer={observer} />}
        {tab === 'catalog' && <Catalog observer={observer} onChange={reloadObservers} />}
        {tab === 'locations' && <Locations observers={observers} onChange={reloadObservers} />}
      </main>
    </>
  )
}
