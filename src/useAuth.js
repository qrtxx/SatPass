import { createContext, useContext } from 'react'

// Placeholder until A7: nobody is logged in. A7 adds the user from /auth/me and login/register/logout.
export const NO_USER = { user: null }
export const AuthContext = createContext(NO_USER)

export const useAuth = () => useContext(AuthContext)
