import { useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router'
import { useAuth } from '../useAuth.js'

// Where to go after logging in: the ?next= page, but only within this site. Resolved the way the browser
// would, because tricks like "/\evil.com" or "/<tab>/evil.com" pass a simple "starts with /" check.
function safeNextPage(next, origin = window.location.origin) {
  if (!next) return '/satellites'
  const url = new URL(next, origin)
  return url.origin === origin ? url.pathname + url.search + url.hash : '/satellites'
}

function useNextPage() {
  const [params] = useSearchParams()
  return safeNextPage(params.get('next'))
}

// Shared by both forms: submit, show the API's error under the form, then go to the next page.
function useAuthForm(submit) {
  const navigate = useNavigate()
  const next = useNextPage()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await submit(Object.fromEntries(new FormData(event.currentTarget)))
      navigate(next, { replace: true })
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  return { error, busy, onSubmit, next }
}

export function LoginPage() {
  const { status, login } = useAuth()
  const form = useAuthForm((f) => login(f.login, f.password))
  if (status === 'user') return <Navigate to={form.next} replace />

  return (
    <section className="card auth-card">
      <h2>Log in</h2>
      <form className="stack" aria-describedby={form.error ? 'login-error' : undefined} onSubmit={form.onSubmit}>
        <label>
          Username or email
          <input name="login" autoComplete="username" required />
        </label>
        <label>
          Password
          <input name="password" type="password" autoComplete="current-password" required />
        </label>
        <button className="primary" disabled={form.busy}>
          {form.busy ? 'Logging in…' : 'Log in'}
        </button>
      </form>
      {form.error && (
        <p id="login-error" className="error" role="alert">
          {form.error}
        </p>
      )}
      <p>
        No account? <Link to={`/register${window.location.search}`}>Sign up</Link>
      </p>
    </section>
  )
}

export function RegisterPage() {
  const { status, register } = useAuth()
  const form = useAuthForm((f) => register(f.username, f.email, f.password))
  if (status === 'user') return <Navigate to={form.next} replace />

  return (
    <section className="card auth-card">
      <h2>Sign up</h2>
      <form className="stack" aria-describedby={form.error ? 'register-error' : 'register-rules'} onSubmit={form.onSubmit}>
        <label>
          Username
          <input name="username" autoComplete="username" required minLength={3} maxLength={32} />
        </label>
        <label>
          Email
          <input name="email" type="email" autoComplete="email" required maxLength={254} />
        </label>
        <label>
          Password
          <input name="password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} />
        </label>
        <p id="register-rules" className="muted">
          Username: 3–32 letters, digits, dots, dashes or underscores. Password: at least 8 characters.
        </p>
        <button className="primary" disabled={form.busy}>
          {form.busy ? 'Creating your account…' : 'Sign up'}
        </button>
      </form>
      {form.error && (
        <p id="register-error" className="error" role="alert">
          {form.error}
        </p>
      )}
      <p>
        Already have an account? <Link to={`/login${window.location.search}`}>Log in</Link>
      </p>
    </section>
  )
}
