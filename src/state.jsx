import { useCallback, useEffect, useState } from 'react'
import { api, MAX_SELECTED } from './api.js'
import { AppStateContext } from './useAppState.js'
import { useAuth } from './useAuth.js'

// State shared by every page: locations, the chosen location, ticked satellites, and the Passes page's mode.
export function AppStateProvider({ children }) {
  const { user } = useAuth()
  const userId = user?.id ?? null
  const [observers, setObservers] = useState([])
  const [observerId, setObserverId] = useState(null)
  const [observersLoaded, setObserversLoaded] = useState(false) // so pages can tell "loading" from "no locations"
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(() => new Set())
  const [passesSource, setPassesSource] = useState('watchlist')
  const [autoPredict, setAutoPredict] = useState(false)
  const [catalogVersion, setCatalogVersion] = useState(0) // bumped when a satellite is deleted
  const [catalogSearch, setCatalogSearch] = useState('') // last "?q=…&page=…", so the navbar link returns to it

  const reloadObservers = useCallback(
    () =>
      api('/observers').then(
        (list) => {
          setObservers(list)
          // Keep the chosen location if it still exists, otherwise pick the first one.
          setObserverId((id) => (list.some((o) => o.id === id) ? id : (list[0]?.id ?? null)))
          setError('')
        },
        (e) => setError(e.message),
      )
      .finally(() => setObserversLoaded(true)),
    [],
  )

  // When the logged-in user changes: forget the previous user's locations, and on logout their ticks too.
  // (Adjusting state during render, React's recommended alternative to an effect for this.)
  const [shownUserId, setShownUserId] = useState(userId)
  if (userId !== shownUserId) {
    setShownUserId(userId)
    setObservers([])
    setObserverId(null)
    setObserversLoaded(false)
    setError('')
    if (userId === null) setSelected(new Set())
  }

  // Locations are private, so they're only loaded for a logged-in user.
  useEffect(() => {
    if (userId !== null) reloadObservers()
  }, [userId, reloadObservers])

  const toggleSelected = useCallback((id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else if (next.size < MAX_SELECTED) next.add(id)
      return next
    })
  }, [])

  function satelliteDeleted(id) {
    setSelected((prev) => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
    setCatalogVersion((v) => v + 1)
    reloadObservers() // it may have been on the watchlist
  }

  const value = {
    observers,
    observer: observers.find((o) => o.id === observerId),
    observerId,
    setObserverId,
    observersLoaded,
    reloadObservers,
    error,
    selected,
    toggleSelected,
    clearSelected: () => setSelected(new Set()),
    passesSource,
    setPassesSource,
    autoPredict,
    setAutoPredict,
    catalogVersion,
    satelliteDeleted,
    catalogSearch,
    setCatalogSearch,
  }
  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>
}
