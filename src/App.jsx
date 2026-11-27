import { Route, Routes } from 'react-router'
import { AuthProvider, RequireAdmin, RequireAuth } from './auth.jsx'
import Layout from './Layout.jsx'
import { AdminPage, AdminUserPage } from './pages/AdminPages.jsx'
import { AccountPage, GlobePage, NotFoundPage, TonightPage } from './pages/Placeholders.jsx'
import { LoginPage, RegisterPage } from './pages/AuthPages.jsx'
import { LocationsPage, PassesPage, SatellitesPage } from './pages/MainPages.jsx'
import { AppStateProvider } from './state.jsx'

export default function App() {
  return (
    <AuthProvider>
      <AppStateProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<TonightPage />} />
            <Route path="satellites" element={<SatellitesPage />} />
            <Route
              path="passes"
              element={
                <RequireAuth>
                  <PassesPage />
                </RequireAuth>
              }
            />
            <Route path="globe" element={<GlobePage />} />
            <Route
              path="locations"
              element={
                <RequireAuth>
                  <LocationsPage />
                </RequireAuth>
              }
            />
            <Route path="login" element={<LoginPage />} />
            <Route path="register" element={<RegisterPage />} />
            <Route
              path="account"
              element={
                <RequireAuth>
                  <AccountPage />
                </RequireAuth>
              }
            />
            <Route
              path="admin"
              element={
                <RequireAdmin>
                  <AdminPage />
                </RequireAdmin>
              }
            />
            <Route
              path="admin/users/:id"
              element={
                <RequireAdmin>
                  <AdminUserPage />
                </RequireAdmin>
              }
            />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </AppStateProvider>
    </AuthProvider>
  )
}
