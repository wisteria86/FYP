// Shared feedback: toasts, a confirm dialog, an accessible modal and skeleton loaders.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { Icon } from './Icon'

const FeedbackContext = createContext(null)
const FOCUSABLE = 'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])'

// A dialog that keeps focus inside, closes on Escape and returns focus to where it came from.
export function Modal({ open, onClose, labelledBy, className = '', children, dismissable = true }) {
  const panel = useRef(null)
  useEffect(() => {
    if (!open) return
    const previous = document.activeElement
    const first = panel.current?.querySelector('[data-autofocus]') || panel.current?.querySelector(FOCUSABLE)
    first?.focus()
    const onKey = event => {
      if (event.key === 'Escape' && dismissable) { event.preventDefault(); onClose?.() }
      if (event.key !== 'Tab' || !panel.current) return
      const items = [...panel.current.querySelectorAll(FOCUSABLE)]
      if (!items.length) return
      const [head, tail] = [items[0], items[items.length - 1]]
      if (event.shiftKey && document.activeElement === head) { event.preventDefault(); tail.focus() }
      else if (!event.shiftKey && document.activeElement === tail) { event.preventDefault(); head.focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); previous?.focus?.() }
  }, [open, onClose, dismissable])
  if (!open) return null
  return <div className="hk-overlay" onMouseDown={event => { if (dismissable && event.target === event.currentTarget) onClose?.() }}>
    <div ref={panel} className={`hk-modal ${className}`.trim()} role="dialog" aria-modal="true" aria-labelledby={labelledBy}>{children}</div>
  </div>
}

let toastId = 0
export function FeedbackProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const [question, setQuestion] = useState(null)
  const dismiss = useCallback(id => setToasts(list => list.filter(item => item.id !== id)), [])
  const toast = useCallback((message, { tone = 'info', timeout } = {}) => {
    if (!message) return
    const id = ++toastId
    setToasts(list => [...list.filter(item => item.message !== message), { id, message, tone }].slice(-4))
    const wait = timeout ?? (tone === 'error' ? 9000 : 4500)
    if (wait) setTimeout(() => dismiss(id), wait)
    return id
  }, [dismiss])
  // confirm({title, message, confirmLabel, danger}) resolves true or false.
  const confirm = useCallback(options => new Promise(resolve => setQuestion({ ...options, resolve })), [])
  const answer = value => { question?.resolve(value); setQuestion(null) }
  const value = useMemo(() => ({ toast, confirm, dismiss }), [toast, confirm, dismiss])
  return <FeedbackContext.Provider value={value}>
    {children}
    <div className="hk-toasts" role="region" aria-label="Notifications">
      <div aria-live="polite" aria-relevant="additions">
        {toasts.map(item => <div key={item.id} className={`hk-toast ${item.tone}`} role={item.tone === 'error' ? 'alert' : 'status'}>
          <Icon name={item.tone === 'error' ? 'warning' : item.tone === 'success' ? 'checkCircle' : 'info'}/>
          <p>{item.message}</p>
          <button onClick={() => dismiss(item.id)} aria-label="Dismiss notification"><Icon name="close"/></button>
        </div>)}
      </div>
    </div>
    <Modal open={!!question} onClose={() => answer(false)} labelledBy="hk-confirm-title" className="hk-confirm">
      {question && <>
        <span className={`hk-confirm-mark ${question.danger ? 'danger' : ''}`}><Icon name={question.danger ? 'trash' : 'info'}/></span>
        <h2 id="hk-confirm-title">{question.title}</h2>
        {question.message && <p>{question.message}</p>}
        <footer>
          <button className="h-soft" onClick={() => answer(false)} data-autofocus>{question.cancelLabel || 'Cancel'}</button>
          <button className={question.danger ? 'hk-danger' : 'h-primary'} onClick={() => answer(true)}>{question.confirmLabel || 'Confirm'}</button>
        </footer>
      </>}
    </Modal>
  </FeedbackContext.Provider>
}

const fallback = {
  toast: message => { if (message) console.info(message) },
  confirm: async ({ title, message }) => window.confirm([title, message].filter(Boolean).join('\n\n')),
  dismiss: () => {},
}
export function useFeedback() { return useContext(FeedbackContext) || fallback }

// Placeholder blocks shown while content loads.
export function Skeleton({ lines = 3, card = false, className = '' }) {
  return <div className={`hk-skeleton ${card ? 'card' : ''} ${className}`.trim()} aria-hidden="true">
    {Array.from({ length: lines }, (_, index) => <i key={index} style={{ width: `${index === lines - 1 ? 55 : 100 - index * 8}%` }}/>)}
  </div>
}
export function PageSkeleton({ label = 'Loading' }) {
  return <main className="page hikari-page hk-page-skeleton" aria-busy="true" aria-label={label}>
    <Skeleton lines={2} className="head"/>
    <div className="hk-skeleton-grid">{[0, 1, 2, 3].map(index => <Skeleton key={index} card lines={3}/>)}</div>
    <Skeleton card lines={6}/>
  </main>
}

// A labelled on/off switch built on a real checkbox.
export function Toggle({ checked, onChange, label, description, disabled }) {
  return <label className="hk-toggle">
    <input type="checkbox" role="switch" checked={!!checked} disabled={disabled} onChange={event => onChange(event.target.checked)}/>
    <span className="hk-toggle-track" aria-hidden="true"><i/></span>
    <span className="hk-toggle-text"><b>{label}</b>{description && <small>{description}</small>}</span>
  </label>
}
