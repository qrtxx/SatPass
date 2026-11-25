import { useSearchParams } from 'react-router'

// The satellite details panel is opened by ?sat=<NORAD ID> on any page, so the link can be shared.
export function useDetails() {
  const [params, setParams] = useSearchParams()
  const sat = Number(params.get('sat'))
  const edit = (change) =>
    setParams((prev) => {
      const next = new URLSearchParams(prev) // keep the page's own parameters (search, page, …)
      change(next)
      return next
    })
  return {
    detailsId: Number.isInteger(sat) && sat > 0 ? sat : null,
    openDetails: (id) => edit((p) => p.set('sat', id)),
    closeDetails: () => edit((p) => p.delete('sat')),
  }
}
