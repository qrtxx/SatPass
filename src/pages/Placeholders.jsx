import { Link } from 'react-router'

// A page that is planned but not built yet.
function Placeholder({ title, children, links = [] }) {
  return (
    <section className="card placeholder">
      <h2>
        {title} <span className="coming-soon">Coming soon</span>
      </h2>
      <p>{children}</p>
      {links.length > 0 && (
        <p className="actions">
          {links.map(([to, label]) => (
            <Link key={to} className="button" to={to}>
              {label}
            </Link>
          ))}
        </p>
      )}
    </section>
  )
}

export function TonightPage() {
  return (
    <Placeholder
      title="Tonight"
      links={[
        ['/passes', 'Predict passes now'],
        ['/satellites', 'Browse satellites'],
      ]}
    >
      Tonight's visible passes from your location: the satellites you can see with the naked eye, when and where to look.
    </Placeholder>
  )
}

export function GlobePage() {
  return (
    <Placeholder title="Globe" links={[['/satellites', 'Tick satellites']]}>
      A 3D globe with the live positions and orbits of the satellites you tick.
    </Placeholder>
  )
}

export function AccountPage() {
  return <Placeholder title="Account">Your account details and password.</Placeholder>
}

export function NotFoundPage() {
  return (
    <section className="card placeholder">
      <h2>Page not found</h2>
      <p>This page doesn't exist.</p>
      <p>
        <Link className="button" to="/satellites">
          Go to Satellites
        </Link>
      </p>
    </section>
  )
}
