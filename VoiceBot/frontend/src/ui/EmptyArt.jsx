// Small drawings for empty states, in the same soft style as the call scenes.
const ART = {
  // A lantern waiting to be lit: nothing practised yet.
  lantern: <>
    <circle cx="60" cy="54" r="34" fill="#fde6dc"/>
    <path d="M60 14v8" stroke="#b88a78" strokeWidth="3" strokeLinecap="round"/>
    <rect x="48" y="22" width="24" height="6" rx="3" fill="#a8133a"/>
    <path d="M44 30h32l-4 40H48z" fill="#fff8f0" stroke="#d9b3a8" strokeWidth="2"/>
    <path d="M60 40c5 6 5 12 0 18-5-6-5-12 0-18z" fill="#f2a59f" opacity=".7"/>
    <rect x="46" y="70" width="28" height="6" rx="3" fill="#a8133a"/>
  </>,
  // Two speech bubbles: no conversations yet.
  chat: <>
    <circle cx="60" cy="54" r="34" fill="#fde6dc"/>
    <path d="M30 34h40a8 8 0 0 1 8 8v16a8 8 0 0 1-8 8H48l-10 8v-8h-8a8 8 0 0 1-8-8V42a8 8 0 0 1 8-8z" fill="#fff8f0" stroke="#d9b3a8" strokeWidth="2"/>
    <path d="M58 52h34a7 7 0 0 1 7 7v13a7 7 0 0 1-7 7h-4v7l-9-7H58a7 7 0 0 1-7-7V59a7 7 0 0 1 7-7z" fill="#a8133a"/>
    <circle cx="66" cy="65" r="2.4" fill="#fff"/><circle cx="75" cy="65" r="2.4" fill="#fff"/><circle cx="84" cy="65" r="2.4" fill="#fff"/>
  </>,
}

export function EmptyArt({ kind = 'lantern', title, children }) {
  return <div className="hk-empty-art">
    <svg viewBox="0 0 120 100" aria-hidden="true">{ART[kind] || ART.lantern}</svg>
    {title && <strong>{title}</strong>}
    {children && <p>{children}</p>}
  </div>
}
