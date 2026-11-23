// Calls the FastAPI backend through the Vite proxy (see vite.config.js).

// Same limit as the API's passes endpoint (?norad_id= repeated at most 20 times).
export const MAX_SELECTED = 20

async function request(path, { method = 'GET', body } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 204) return { res, data: null }
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new Error(errorText(data, res.status))
  return { res, data }
}

export async function api(path, options) {
  return (await request(path, options)).data
}

// A page of a list plus the total number of matches (the API's X-Total-Count header).
export async function apiPage(path) {
  const { res, data } = await request(path)
  return { items: data, total: Number(res.headers.get('X-Total-Count') ?? data.length) }
}

function errorText(data, status) {
  const detail = data?.detail
  // Business rules: {"detail": "...", "code": "..."}
  if (typeof detail === 'string') return detail
  // Pydantic validation: {"detail": [{"loc": ["body", "latitude"], "msg": "..."}]}
  if (Array.isArray(detail)) return detail.map((e) => `${e.loc.at(-1)}: ${e.msg}`).join('; ')
  return `Request failed (${status}). Is the backend running on port 8000?`
}

export const formatTime = (iso) => new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'medium' })
// Short form for pass tables: "Nov 23, 13:06:53" (no year, 24-hour).
export const formatPassTime = (iso) =>
  new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
export const formatDuration = (s) => `${Math.floor(s / 60)} min ${s % 60} s`
export const daysSince = (iso) => (Date.now() - new Date(iso).getTime()) / 86_400_000
export const formatCount = (n) => n.toLocaleString()
