// Calls the FastAPI backend through the Vite proxy (see vite.config.js).
export async function api(path, { method = 'GET', body } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new Error(errorText(data, res.status))
  return data
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
