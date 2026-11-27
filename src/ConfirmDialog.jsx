import { useEffect, useRef } from 'react'

// A modal confirmation on the browser's <dialog>: it traps focus, closes on Escape and dims the page.
// cancelFirst={false} swaps the buttons (used on a second confirmation, so a double click can't confirm twice).
export default function ConfirmDialog({
  title,
  children,
  confirmLabel,
  cancelLabel = 'Cancel',
  danger = false,
  cancelFirst = true,
  focusCancel = true,
  busy = false,
  onConfirm,
  onCancel,
}) {
  const ref = useRef(null)

  useEffect(() => {
    ref.current.showModal()
    // showModal() focuses the first button, which on a swapped dialog is the dangerous one, so set the focus
    // ourselves: the element marked data-autofocus (Cancel by default, or e.g. a password field).
    ref.current.querySelector('[data-autofocus]')?.focus()
  }, [])

  const cancel = (
    <button type="button" data-autofocus={focusCancel || undefined} onClick={onCancel}>
      {cancelLabel}
    </button>
  )
  const confirm = (
    <button type="submit" className={danger ? 'danger-solid' : 'primary'} disabled={busy}>
      {busy ? 'Working…' : confirmLabel}
    </button>
  )

  return (
    <dialog
      ref={ref}
      className="dialog"
      aria-labelledby="dialog-title"
      onCancel={(e) => {
        e.preventDefault() // Escape: let the page decide, so its state stays in step
        onCancel()
      }}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault()
          onConfirm(new FormData(e.currentTarget))
        }}
      >
        <h2 id="dialog-title">{title}</h2>
        {children}
        <div className="dialog-buttons">
          {cancelFirst ? (
            <>
              {cancel}
              {confirm}
            </>
          ) : (
            <>
              {confirm}
              {cancel}
            </>
          )}
        </div>
      </form>
    </dialog>
  )
}
