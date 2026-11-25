import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router'
import { useAuth } from './useAuth.js'
import SatelliteDetails from './SatelliteDetails.jsx'
import { useAppState } from './useAppState.js'
import { useDetails } from './useDetails.js'

const LINKS = [
  ['/', 'Tonight'],
  ['/satellites', 'Satellites'],
  ['/passes', 'Passes'],
  ['/globe', 'Globe'],
  ['/locations', 'My locations'],
]

export default function Layout() {
  const app = useAppState()
  const { user } = useAuth()
  const { detailsId, closeDetails } = useDetails()
  const [menuOpen, setMenuOpen] = useState(false)
  // Keep an open details panel open when moving between pages.
  const keepDetails = (to) => (detailsId ? `${to}${to.includes('?') ? '&' : '?'}sat=${detailsId}` : to)

  return (
    <>
      <header className="topbar">
        <h1>
          <Link to="/" className="brand">
            SatPass
          </Link>
        </h1>
        <button className="menu-button" aria-expanded={menuOpen} aria-controls="main-nav" onClick={() => setMenuOpen((o) => !o)}>
          Menu
        </button>
        <nav id="main-nav" className={menuOpen ? 'nav open' : 'nav'} aria-label="Main">
          {LINKS.map(([to, label]) => (
            <NavLink
              key={to}
              to={keepDetails(to === '/satellites' ? to + app.catalogSearch : to)}
              end={to === '/'}
              className="tab"
              onClick={() => setMenuOpen(false)}
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="topbar-right">
          <label className="location">
            Location
            <select value={app.observerId ?? ''} onChange={(e) => app.setObserverId(Number(e.target.value))}>
              {app.observers.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </label>
          {user ? (
            <details className="user-menu">
              <summary>{user.username} ▾</summary>
              <Link to="/account">Account</Link>
              <button>Log out</button>
            </details>
          ) : (
            <>
              <Link className="button" to="/login">
                Log in
              </Link>
              <Link className="button primary" to="/register">
                Sign up
              </Link>
            </>
          )}
        </div>
      </header>
      {app.error && <p className="error">{app.error}</p>}
      <div className={detailsId ? 'layout with-details' : 'layout'}>
        <main>
          <Outlet />
        </main>
        {detailsId && (
          <SatelliteDetails
            key={detailsId}
            noradId={detailsId}
            observer={app.observer}
            selected={app.selected}
            onToggle={app.toggleSelected}
            onClose={closeDetails}
            onChange={app.reloadObservers}
            onDeleted={(id) => {
              app.satelliteDeleted(id)
              closeDetails()
            }}
          />
        )}
      </div>
    </>
  )
}
