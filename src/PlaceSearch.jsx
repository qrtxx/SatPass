import { useEffect, useState } from 'react'
import { api } from './api.js'

const WAIT_MS = 250 // search once typing pauses, not on every key

// "Find a town or village": suggestions from our GeoNames copy; picking one hands the place to onPick.
export default function PlaceSearch({ onPick }) {
  const [text, setText] = useState('')
  const [results, setResults] = useState({ word: '', places: [] })
  const [error, setError] = useState('')
  const word = text.trim()

  useEffect(() => {
    if (word.length < 2) return
    // Results are stored with the word they answer and only shown while that word is still typed,
    // so a slow answer to an older word can't replace newer suggestions.
    const timer = setTimeout(() => {
      api(`/places?${new URLSearchParams({ search: word, limit: 8 })}`).then(
        (places) => (setResults({ word, places }), setError('')),
        (e) => setError(e.message),
      )
    }, WAIT_MS)
    return () => clearTimeout(timer)
  }, [word])

  const shown = word.length >= 2 && results.word === word ? results.places : []
  const noMatch = word.length >= 2 && results.word === word && shown.length === 0
  // Read out by screen readers when it changes (the list itself appears silently).
  const status = shown.length ? `${shown.length} place${shown.length === 1 ? '' : 's'} found` : noMatch ? 'No places found' : ''

  function pick(place) {
    onPick(place)
    setText('')
  }

  return (
    <div className="place-search">
      <label>
        Find a town or village
        <input
          type="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. Almaty, Talgar, Astana"
          autoComplete="off"
          aria-controls={shown.length ? 'place-results' : undefined}
          aria-describedby="place-status"
          onKeyDown={(e) => e.key === 'Escape' && setText('')}
        />
      </label>
      <p id="place-status" className="visually-hidden" aria-live="polite">
        {status}
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {shown.length > 0 && (
        <ul id="place-results" className="place-results">
          {shown.map((p) => (
            <li key={p.id}>
              <button type="button" className="link" onClick={() => pick(p)}>
                <b>{p.name}</b>
                {p.ascii_name !== p.name && ` (${p.ascii_name})`}
              </button>
              <span className="muted">
                {' '}
                · {[p.region, p.country_code].filter(Boolean).join(', ')}
                {p.elevation_m != null && ` · ${p.elevation_m} m`}
              </span>
            </li>
          ))}
        </ul>
      )}
      {noMatch && (
        <p className="muted">No places start with “{word}”. You can still enter the coordinates below.</p>
      )}
    </div>
  )
}
