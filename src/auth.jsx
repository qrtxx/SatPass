import { AuthContext, NO_USER } from './useAuth.js'

export function AuthProvider({ children }) {
  return <AuthContext.Provider value={NO_USER}>{children}</AuthContext.Provider>
}

// Wraps the pages that will need a login. A7: redirect to /login?next=<this page> when there is no user.
export function RequireAuth({ children }) {
  return children
}
