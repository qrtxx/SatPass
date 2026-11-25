import { Link } from 'react-router'

// The forms are complete but switched off until accounts exist (A7).
const NOTE = 'Accounts arrive in the next update. Until then everything works without logging in.'

export function LoginPage() {
  return (
    <section className="card auth-card">
      <h2>Log in</h2>
      <p id="login-note" className="notice">{NOTE}</p>
      <form className="stack" aria-describedby="login-note" onSubmit={(e) => e.preventDefault()}>
        <label>
          Username or email
          <input name="login" autoComplete="username" />
        </label>
        <label>
          Password
          <input name="password" type="password" autoComplete="current-password" />
        </label>
        <button className="primary" disabled>
          Log in
        </button>
      </form>
      <p>
        No account? <Link to="/register">Sign up</Link>
      </p>
    </section>
  )
}

export function RegisterPage() {
  return (
    <section className="card auth-card">
      <h2>Sign up</h2>
      <p id="register-note" className="notice">{NOTE}</p>
      <form className="stack" aria-describedby="register-note" onSubmit={(e) => e.preventDefault()}>
        <label>
          Username
          <input name="username" autoComplete="username" />
        </label>
        <label>
          Email
          <input name="email" type="email" autoComplete="email" />
        </label>
        <label>
          Password
          <input name="password" type="password" autoComplete="new-password" />
        </label>
        <button className="primary" disabled>
          Sign up
        </button>
      </form>
      <p>
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </section>
  )
}
