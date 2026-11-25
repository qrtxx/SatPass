import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import Catalog from '../Catalog.jsx'
import Locations from '../Locations.jsx'
import Passes from '../Passes.jsx'
import { useAppState } from '../useAppState.js'
import { useDetails } from '../useDetails.js'

export function SatellitesPage() {
  const app = useAppState()
  const { openDetails } = useDetails()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()

  // The search and page live in the URL (?q=starlink&page=3), so they survive leaving the page and can be shared.
  const query = params.get('q') ?? ''
  const pageNumber = Number(params.get('page') ?? 1)
  const page = Number.isInteger(pageNumber) && pageNumber >= 1 ? pageNumber - 1 : 0

  // Remember the search and page for the navbar's Satellites link.
  const remembered = new URLSearchParams({ ...(query && { q: query }), ...(page > 0 && { page: page + 1 }) }).toString()
  const { setCatalogSearch } = app
  useEffect(() => {
    setCatalogSearch(remembered ? `?${remembered}` : '')
  }, [remembered, setCatalogSearch])
  const update = (changes) =>
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      for (const [key, value] of Object.entries(changes)) {
        if (value) next.set(key, value)
        else next.delete(key)
      }
      return next
    })

  function predictSelected() {
    app.setPassesSource('selected')
    app.setAutoPredict(true) // the Passes page runs the prediction as soon as it opens
    navigate({ pathname: '/passes', search: params.has('sat') ? `?sat=${params.get('sat')}` : '' }) // keep open details
  }

  return (
    <Catalog
      observer={app.observer}
      selected={app.selected}
      onToggle={app.toggleSelected}
      onClear={app.clearSelected}
      onPredict={predictSelected}
      onOpen={openDetails}
      version={app.catalogVersion}
      query={query}
      page={page}
      onSearch={(q) => update({ q, page: null })}
      onPage={(index) => update({ page: index > 0 ? index + 1 : null })}
    />
  )
}

export function PassesPage() {
  const app = useAppState()
  const { openDetails } = useDetails()
  return (
    <Passes
      key={app.observerId}
      observer={app.observer}
      observersLoaded={app.observersLoaded}
      source={app.passesSource}
      onSourceChange={app.setPassesSource}
      selected={app.selected}
      onOpen={openDetails}
      autoPredict={app.autoPredict}
      onAutoPredicted={() => app.setAutoPredict(false)}
    />
  )
}

export function LocationsPage() {
  const app = useAppState()
  return <Locations observers={app.observers} onChange={app.reloadObservers} />
}
