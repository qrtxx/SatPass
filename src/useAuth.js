import { createContext, useContext } from 'react'

// Filled by AuthProvider (auth.jsx): { user, status: 'loading' | 'anonymous' | 'user', login, register, logout }.
export const AuthContext = createContext(null)

export const useAuth = () => useContext(AuthContext)
