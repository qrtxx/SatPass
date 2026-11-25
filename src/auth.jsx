import { useCallback, useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router'
import { api, hasToken, onUnauthorized, setToken } from './api.js'
import { AuthContext, useAuth } from './useAuth.js'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState(hasToken() ? 'loading' : 'anonymous')

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
    setStatus('anonymous')
  }, [])

  useEffect(() => {
    onUnauthorized(logout) // an expired or rejected token logs you out
    return () => onUnauthorized(null)
  }, [logout])

  // A token from an earlier visit: find out who it belongs to.
  useEffect(() => {
    if (!hasToken()) return
    api('/auth/me').then(
      (me) => (setUser(me), setStatus('user')),
      () => setStatus('anonymous'), // a 401 has already logged out; any other error just shows the login link
    )
  }, [])

  async function login(loginName, password) {
    const { access_token } = await api('/auth/login', { method: 'POST', body: { login: loginName, password } })
    setToken(access_token)
    const me = await api('/auth/me')
    setUser(me)
    setStatus('user')
    return me
  }

  async function register(username, email, password) {
    await api('/auth/register', { method: 'POST', body: { username, email, password } })
    return login(username, password)
  }

  const value = { user, status, login, register, logout }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// Pages that need a login: anyone else is sent to /login and brought back here afterwards.
export function RequireAuth({ children }) {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <p className="card muted">Checking your login…</p>
  if (status !== 'user') {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  return children
}
