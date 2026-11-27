import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { api, formatCount, formatTime } from '../api.js'
import { useAuth } from '../useAuth.js'

// /admin: the numbers at a glance, then every user. Click a user for their page.
export function AdminPage() {
  const [stats, setStats] = useState(null)
  const [users, setUsers] = useState(null)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api('/admin/stats').then(setStats, (e) => setError(e.message))
  }, [])

  useEffect(() => {
    let current = true
    const params = search.trim() ? `?${new URLSearchParams({ search: search.trim() })}` : ''
    api(`/admin/users${params}`).then(
      (list) => current && setUsers(list),
      (e) => current && setError(e.message),
    )
    return () => {
      current = false
    }
  }, [search])

  return (
    <section className="card">
      <h2>Admin dashboard</h2>
      {error && <p className="error">{error}</p>}
      {stats && (
        <>
          <div className="stats">
            {[
              ['Users', stats.users],
              ['Admins', stats.admins],
              ['Satellites', stats.satellites],
              ['Places', stats.places],
            ].map(([label, value]) => (
              <div key={label} className="stat">
                <b className="mono">{formatCount(value)}</b>
                {label}
              </div>
            ))}
          </div>
          <h3>Orbit data imports</h3>
          {stats.imports.length === 0 ? (
            <p className="muted">No imports yet. Use Update orbit data on the Satellites page.</p>
          ) : (
            <div className="scroll">
              <table>
                <thead>
                  <tr>
                    <th>Group</th>
                    <th>Last import</th>
                    <th>Added</th>
                    <th>Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.imports.map((i) => (
                    <tr key={i.group_name}>
                      <td>{i.group_name}</td>
                      <td className="mono">{formatTime(i.fetched_at)}</td>
                      <td className="mono">{formatCount(i.added)}</td>
                      <td className="mono">{formatCount(i.updated)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <h3>Users</h3>
      <div className="row">
        <label>
          Search by username or email
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} maxLength={100} />
        </label>
      </div>
      {users && users.length === 0 && <p className="empty">No users match “{search.trim()}”.</p>}
      {users && users.length > 0 && (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Username</th>
                <th>Email</th>
                <th>Role</th>
                <th>Joined</th>
                <th>Locations</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <Link to={`/admin/users/${u.id}`}>{u.username}</Link>
                  </td>
                  <td>{u.email}</td>
                  <td>{u.role === 'admin' ? <span className="coming-soon">admin</span> : 'user'}</td>
                  <td className="mono">{formatTime(u.created_at)}</td>
                  <td className="mono">{u.location_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// /admin/users/:id: everything about one user. More sections can be added here later.
export function AdminUserPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user: me, reloadUser } = useAuth()
  const [user, setUser] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => api(`/admin/users/${id}`).then((u) => (setUser(u), setError('')), (e) => setError(e.message)), [id])

  useEffect(() => {
    load()
  }, [load])

  async function run(action) {
    setError('')
    try {
      await action()
    } catch (e) {
      setError(e.message)
    }
  }

  const changeRole = (role) =>
    run(async () => {
      await api(`/admin/users/${id}`, { method: 'PATCH', body: { role } })
      if (user.id === me.id) await reloadUser() // demoting yourself takes effect in the UI right away
      await load()
    })

  const deleteAccount = () =>
    confirm(`Delete ${user.username}'s account and all their locations? This can't be undone.`) &&
    run(async () => {
      await api(`/admin/users/${id}`, { method: 'DELETE' })
      navigate('/admin')
    })

  const deleteLocation = (o) =>
    confirm(`Delete ${user.username}'s location "${o.name}"?`) &&
    run(async () => {
      await api(`/observers/${o.id}`, { method: 'DELETE' })
      await load()
    })

  return (
    <section className="card">
      <p>
        <Link to="/admin">‹ All users</Link>
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {user && (
        <>
          <h2>
            {user.username} {user.role === 'admin' && <span className="coming-soon">admin</span>}
          </h2>
          <dl className="facts">
            <dt>Email</dt>
            <dd>{user.email}</dd>
            <dt>Joined</dt>
            <dd className="mono">{formatTime(user.created_at)}</dd>
            <dt>User id</dt>
            <dd className="mono">{user.id}</dd>
          </dl>
          <p className="actions">
            {user.role === 'admin' ? (
              <button onClick={() => changeRole('user')}>Make regular user</button>
            ) : (
              <button onClick={() => changeRole('admin')}>Make admin</button>
            )}
            <button className="danger" onClick={deleteAccount}>
              Delete account
            </button>
          </p>

          <h3>Locations ({user.locations.length})</h3>
          {user.locations.length === 0 ? (
            <p className="muted">No locations yet.</p>
          ) : (
            <div className="scroll">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Latitude</th>
                    <th>Longitude</th>
                    <th>Elevation</th>
                    <th>Watching</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {user.locations.map((o) => (
                    <tr key={o.id}>
                      <td>{o.name}</td>
                      <td className="mono">{o.latitude}</td>
                      <td className="mono">{o.longitude}</td>
                      <td className="mono">{o.elevation_m} m</td>
                      <td className="mono">{o.watchlist.length}</td>
                      <td className="actions">
                        <button className="danger" onClick={() => deleteLocation(o)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  )
}
