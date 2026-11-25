import { createContext, useContext } from 'react'

// Filled by AppStateProvider (state.jsx).
export const AppStateContext = createContext(null)

export const useAppState = () => useContext(AppStateContext)
