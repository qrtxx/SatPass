// Calls the FastAPI backend through the Vite proxy (see vite.config.js).

// Same limit as the API's passes endpoint (?norad_id= repeated at most 20 times).
export const MAX_SELECTED = 20

// --- Login token -----------------------------------------------------------------
// Kept in localStorage so a reload stays logged in. shortcut: readable by any script on the page (an XSS
// risk); an httpOnly cookie would avoid that but needs CSRF protection and a backend change.
const TOKEN_KEY = 'satpass.token'
let token = readToken()
let unauthorizedHandler = null

function readToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null // storage blocked (e.g. private mode): log in again after a reload
  }
}

export function setToken(value) {
  token = value
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // storage blocked: the token still works until the page is reloaded
  }
}

export const hasToken = () => Boolean(token)

// Called when a request that carried a token gets 401 (expired, or the user was deleted): log out.
export function onUnauthorized(handler) {
  unauthorizedHandler = handler
}

async function request(path, { method = 'GET', body } = {}) {
  const headers = {}
  if (body) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`/api${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined })
  if (res.status === 204) return { res, data: null }
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 401 && token) unauthorizedHandler?.()
    const error = new Error(errorText(data, res.status))
    error.status = res.status
    error.code = data?.code
    throw error
  }
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
