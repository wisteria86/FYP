// Hikari's icon set: simple 24px line icons drawn for this app, all sharing one stroke style.
const PATHS = {
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
  sparkles: <><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z"/></>,
  mic: <><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M19 10v1a7 7 0 0 1-14 0v-1M12 18v4M8 22h8"/></>,
  micOff: <><path d="M15 9.3V5a3 3 0 0 0-5.7-1.3M9 9v2a3 3 0 0 0 5.1 2.1"/><path d="M19 10v1a7 7 0 0 1-.8 3.3M5 10v1a7 7 0 0 0 11.4 5.4M12 18v4M8 22h8M3 3l18 18"/></>,
  history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></>,
  chart: <><path d="M3 3v18h18"/><path d="m7 15 4-5 3 3 5-7"/></>,
  calendar: <><rect x="3" y="4" width="18" height="17" rx="2.5"/><path d="M8 2v4M16 2v4M3 10h18M8 14h3M8 17h6"/></>,
  book: <><path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v17H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M4 21.5A2.5 2.5 0 0 1 6.5 19H20v3H6.5M9 7h7"/></>,
  docs: <><path d="M6 2h9l4 4v16H6z"/><path d="M14 2v5h5M9 12h7M9 16h7"/></>,
  monitor: <><path d="M3 3v18h18"/><path d="m6 16 4-5 3 3 5-8"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1L7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.6V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1z"/></>,
  sliders: <><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/></>,
  send: <><path d="M22 2 11 13"/><path d="m22 2-7 20-4-9-9-4z"/></>,
  camera: <><path d="M14.5 4 16 7h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h3l1.5-3z"/><circle cx="12" cy="13" r="3"/></>,
  speaker: <><path d="M11 5 6 9H2v6h4l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14"/></>,
  stop: <><rect x="6" y="6" width="12" height="12" rx="2"/></>,
  record: <><circle cx="12" cy="12" r="5" fill="currentColor"/><circle cx="12" cy="12" r="9"/></>,
  pause: <><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></>,
  play: <><path d="M7 4.5v15a1 1 0 0 0 1.5.9l12-7.5a1 1 0 0 0 0-1.8l-12-7.5A1 1 0 0 0 7 4.5z"/></>,
  check: <><path d="M20 6 9 17l-5-5"/></>,
  checkCircle: <><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></>,
  circle: <><circle cx="12" cy="12" r="8"/></>,
  hand: <><path d="M18 11V6a2 2 0 0 0-4 0M14 10V4a2 2 0 0 0-4 0v2M10 10.5V6a2 2 0 0 0-4 0v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.9-6-2.4l-3.6-3.6a2 2 0 0 1 2.8-2.8L6 14"/></>,
  phoneOff: <><path d="M10.7 13.3a16 16 0 0 1-3-4.3l1.6-1.6a1.5 1.5 0 0 0 .3-1.7L8.2 2.9A1.5 1.5 0 0 0 6.5 2L3.4 2.9A1.5 1.5 0 0 0 2.3 4.5 19 19 0 0 0 6 13"/><path d="M8.8 17.2A19 19 0 0 0 19.5 21.7a1.5 1.5 0 0 0 1.6-1.1l.9-3.1a1.5 1.5 0 0 0-.9-1.7l-2.8-1.4a1.5 1.5 0 0 0-1.7.3l-1.6 1.6M22 2 2 22"/></>,
  captions: <><rect x="2" y="5" width="20" height="14" rx="3"/><path d="M10 10.5a2 2 0 1 0 0 3M17 10.5a2 2 0 1 0 0 3"/></>,
  chat: <><path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M8 9h8M8 13h5"/></>,
  close: <><path d="M18 6 6 18M6 6l12 12"/></>,
  arrowLeft: <><path d="M19 12H5M12 19l-7-7 7-7"/></>,
  arrowRight: <><path d="M5 12h14M12 5l7 7-7 7"/></>,
  arrowUpRight: <><path d="M7 17 17 7M8 7h9v9"/></>,
  trendUp: <><path d="m3 17 6-6 4 4 8-8"/><path d="M14 7h7v7"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  level: <><path d="M5 20v-5M12 20V9M19 20V4"/></>,
  search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
  logout: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></>,
  warning: <><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/></>,
  star: <><path d="m12 2.5 2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4l-5.9 3.1 1.2-6.5-4.8-4.6 6.6-.9z"/></>,
  chevronRight: <><path d="m9 18 6-6-6-6"/></>,
  chevronDown: <><path d="m6 9 6 6 6-6"/></>,
  plus: <><path d="M12 5v14M5 12h14"/></>,
  minus: <><path d="M5 12h14"/></>,
  trash: <><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6"/></>,
  download: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></>,
  upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/></>,
  undo: <><path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/></>,
  refresh: <><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16M3 12a9 9 0 0 1 15.5-6.2L21 8"/><path d="M21 3v5h-5M3 21v-5h5"/></>,
  flame: <><path d="M12 22c4 0 7-2.8 7-7 0-3.5-2.4-6.3-4-8-.3 2.2-1.4 3.6-3 4.5C12 8 11 5 8 2c.3 3.2-1.4 5.3-2.6 7.3A9 9 0 0 0 5 15c0 4.2 3 7 7 7z"/></>,
  target: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></>,
  trophy: <><path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3"/></>,
  user: <><circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/></>,
  users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/></>,
  briefcase: <><rect x="2" y="7" width="20" height="14" rx="2.5"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2M2 13h20"/></>,
  mail: <><rect x="2" y="4" width="20" height="16" rx="2.5"/><path d="m22 6-10 7L2 6"/></>,
  lock: <><rect x="4" y="11" width="16" height="10" rx="2.5"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></>,
  shield: <><path d="M12 22s8-3.6 8-10V5l-8-3-8 3v7c0 6.4 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></>,
  lightbulb: <><path d="M9 18h6M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.2 1 2V17h6v-.3c0-.8.4-1.5 1-2A7 7 0 0 0 12 2z"/></>,
  building: <><rect x="4" y="2" width="16" height="20" rx="1.5"/><path d="M9 22v-4h6v4M8 6h.01M12 6h.01M16 6h.01M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01"/></>,
  cpu: <><rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/></>,
  handshake: <><path d="m11 17 2 2a1.4 1.4 0 0 0 2-2"/><path d="m14 14 2.5 2.5a1.4 1.4 0 0 0 2-2L15 11l-1.8 1.8a1.5 1.5 0 0 1-2.2-2.1L13.6 8a2.8 2.8 0 0 1 3.4-.4l.6.4H21v7h-2M3 8h3l1 1"/><path d="M3 15h2l4 4a1.4 1.4 0 0 0 2-2"/><path d="M3 7v8"/></>,
  headphones: <><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1v-6h3zM3 19a2 2 0 0 0 2 2h1v-6H3z"/></>,
  presentation: <><path d="M2 3h20M4 3v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V3M12 16v5M8 21h8"/><path d="m8 11 3-3 2 2 3-3"/></>,
  swap: <><path d="M17 3l4 4-4 4M21 7H7M7 21l-4-4 4-4M3 17h14"/></>,
  quote: <><path d="M7 7h4v4c0 2.5-1.5 4.5-4 5M14 7h4v4c0 2.5-1.5 4.5-4 5"/></>,
  globe: <><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></>,
  bolt: <><path d="M13 2 4 14h7l-1 8 9-12h-7z"/></>,
  eye: <><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></>,
  ear: <><path d="M6 8.5a6 6 0 0 1 12 0c0 3.5-3 4.5-3 7.5a3.5 3.5 0 0 1-6.6 1.6"/><path d="M15 8.5a3 3 0 0 0-6 0"/></>,
}

export const ICON_NAMES = Object.keys(PATHS)

// Decorative by default; pass `label` when the icon is the only thing that says what a control does.
export function Icon({ name, label, className = '' }) {
  const paths = PATHS[name] || PATHS.circle
  return <svg className={`icon ${className}`.trim()} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden={label ? undefined : 'true'} role={label ? 'img' : undefined}
    aria-label={label} focusable="false">{paths}</svg>
}

// A fitting icon for each training topic.
const SKILL_ICONS = [
  [/negotiat|barter/, 'handshake'], [/interview/, 'briefcase'], [/email/, 'mail'], [/social-engineering|security/, 'lock'],
  [/ai-|ai_|literacy/, 'cpu'], [/company|knowledge/, 'building'], [/critical|thinking/, 'lightbulb'],
  [/conflict/, 'shield'], [/listening/, 'ear'], [/present|public-speaking|speaking-public/, 'presentation'],
  [/story/, 'quote'], [/customer/, 'users'], [/concise|communication/, 'chat'], [/english|speaking|language/, 'globe'],
]
export function skillIcon(id = '') {
  const key = String(id).toLowerCase()
  return (SKILL_ICONS.find(([pattern]) => pattern.test(key)) || [null, 'sparkles'])[1]
}
