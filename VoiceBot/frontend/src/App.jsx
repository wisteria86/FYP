import { useState, useEffect, useRef, useCallback } from 'react'
import './App.css'

// ─── Constants ────────────────────────────────────────────────────────────── //

const ENGINE_LABELS = {
  kokoro:  { label: 'Kokoro', flag: '🌸', lang: 'English' },
  vits_ja: { label: 'VITS',   flag: '🎌', lang: 'Japanese' },
  vits_ar: { label: 'VITS',   flag: '🌙', lang: 'Arabic' },
}

const QUICK_STARTS = [
  'Hello! Who are you and what can you help me with?',
  'Teach me a short phrase in the active language.',
  'Give me a challenging question to think about.',
]

// ─── Icons ────────────────────────────────────────────────────────────────── //

const Icons = {
  Bot: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2"/>
      <path d="M12 2a2 2 0 0 1 2 2v1H10V4a2 2 0 0 1 2-2z"/>
      <path d="M12 7v4"/>
      <circle cx="8.5" cy="16.5" r="1.5" fill="currentColor" stroke="none"/>
      <circle cx="15.5" cy="16.5" r="1.5" fill="currentColor" stroke="none"/>
    </svg>
  ),
  User: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="4"/>
      <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
    </svg>
  ),
  Send: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 2L11 13"/>
      <path d="M22 2L15 22l-4-9-9-4 20-7z"/>
    </svg>
  ),
  Mic: ({ active }) => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" fill={active ? 'currentColor' : 'none'}/>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
      <line x1="12" y1="19" x2="12" y2="23"/>
      <line x1="8" y1="23" x2="16" y2="23"/>
    </svg>
  ),
  Play: () => (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
      <polygon points="5,3 19,12 5,21"/>
    </svg>
  ),
  Pause: () => (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="4" width="4" height="16" rx="1"/>
      <rect x="14" y="4" width="4" height="16" rx="1"/>
    </svg>
  ),
  Chat: () => (
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  ),
  Warning: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
      <line x1="12" y1="9" x2="12" y2="13"/>
      <line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  ),
  Spinner: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="spin-icon">
      <circle cx="12" cy="12" r="10" strokeOpacity="0.2"/>
      <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round"/>
    </svg>
  ),
}

// ─── Message component ────────────────────────────────────────────────────── //

function Message({ msg, onPlay, playingId }) {
  const isUser = msg.role === 'user'
  const isPlaying = playingId === msg.id

  return (
    <div className={`msg-row ${isUser ? 'msg-row--user' : 'msg-row--bot'}`}>
      <div className={`avatar ${isUser ? 'avatar--user' : 'avatar--bot'}`}>
        {isUser ? <Icons.User /> : <Icons.Bot />}
      </div>

      <div className={`bubble ${isUser ? 'bubble--user' : 'bubble--bot'} ${msg.isError ? 'bubble--error' : ''}`}>
        <p className="bubble-text">{msg.text}</p>

        {!isUser && msg.audioB64 && (
          <button
            className={`play-btn ${isPlaying ? 'play-btn--active' : ''}`}
            onClick={() => onPlay(msg)}
            title={isPlaying ? 'Pause' : 'Play audio'}
          >
            {isPlaying ? <Icons.Pause /> : <Icons.Play />}
            <span>{isPlaying ? 'Playing…' : 'Listen'}</span>
          </button>
        )}
      </div>
    </div>
  )
}

// ─── Typing indicator ─────────────────────────────────────────────────────── //

function TypingIndicator() {
  return (
    <div className="msg-row msg-row--bot">
      <div className="avatar avatar--bot"><Icons.Bot /></div>
      <div className="bubble bubble--bot bubble--typing">
        <span /><span /><span />
      </div>
    </div>
  )
}

// ─── Status bar ───────────────────────────────────────────────────────────── //

function StatusBar({ health }) {
  const engineInfo = ENGINE_LABELS[health.engine] || { label: health.engine, flag: '🤖', lang: '' }
  const dot =
    health.status === 'ready'   ? '#10b981' :
    health.status === 'loading' ? '#f59e0b' : '#ef4444'

  return (
    <div className="status-bar">
      <div className="status-engine">
        <span>{engineInfo.flag}</span>
        <span className="status-engine__name">{engineInfo.label}</span>
        {engineInfo.lang && <span className="status-engine__lang">{engineInfo.lang}</span>}
      </div>
      <div className="status-indicator">
        <span className="status-dot" style={{ background: dot }} />
        <span className="status-label">{health.status}</span>
      </div>
    </div>
  )
}

// ─── Empty state ──────────────────────────────────────────────────────────── //

function EmptyState({ onQuickStart }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Icons.Chat /></div>
      <h2 className="empty-title">Start a conversation</h2>
      <p className="empty-sub">
        Type a message below or use the mic button. VoiceBot will respond with
        synthesised speech you can play back.
      </p>
      <div className="quick-starts">
        {QUICK_STARTS.map(q => (
          <button key={q} className="qs-btn" onClick={() => onQuickStart(q)}>
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────── //

export default function App() {
  const [messages, setMessages]     = useState([])
  const [input, setInput]           = useState('')
  const [isLoading, setIsLoading]   = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [health, setHealth]         = useState({ status: 'loading', engine: 'kokoro', sample_rate: 0 })
  const [playingId, setPlayingId]   = useState(null)

  const chatEndRef     = useRef(null)
  const audioRef       = useRef(null)        // current HTMLAudioElement
  const recognitionRef = useRef(null)
  const textareaRef    = useRef(null)

  // ── Poll /api/health ───────────────────────────────────────────────────── //
  useEffect(() => {
    const poll = async () => {
      try {
        const res  = await fetch('/api/health')
        const data = await res.json()
        setHealth(data)
      } catch {
        setHealth(prev => ({ ...prev, status: 'offline' }))
      }
    }
    poll()
    const id = setInterval(poll, 4000)
    return () => clearInterval(id)
  }, [])

  // ── Auto-scroll ────────────────────────────────────────────────────────── //
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // ── Auto-resize textarea ───────────────────────────────────────────────── //
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 140) + 'px'
  }, [input])

  // ── Web Speech API ─────────────────────────────────────────────────────── //
  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return

    const rec = new SR()
    rec.continuous = false
    rec.interimResults = true

    rec.onresult = e => {
      const transcript = Array.from(e.results).map(r => r[0].transcript).join('')
      setInput(transcript)
      if (e.results[e.results.length - 1].isFinal) setIsListening(false)
    }
    rec.onend   = () => setIsListening(false)
    rec.onerror = () => setIsListening(false)

    recognitionRef.current = rec
  }, [])

  const toggleListening = () => {
    const rec = recognitionRef.current
    if (!rec) return
    if (isListening) {
      rec.stop()
      setIsListening(false)
    } else {
      try { rec.start(); setIsListening(true) } catch { /* already running */ }
    }
  }

  // ── Audio playback ─────────────────────────────────────────────────────── //
  const playAudio = useCallback((msg) => {
    // Stop whatever is playing
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }

    // Toggle off if same message
    if (playingId === msg.id) {
      setPlayingId(null)
      return
    }

    if (!msg.audioB64) return

    // Decode base64 WAV → Blob → object URL
    const raw  = atob(msg.audioB64)
    const buf  = new Uint8Array(raw.length)
    for (let i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i)

    const url  = URL.createObjectURL(new Blob([buf], { type: 'audio/wav' }))
    const audio = new Audio(url)

    audio.onended = () => {
      setPlayingId(null)
      audioRef.current = null
      URL.revokeObjectURL(url)
    }
    audio.onerror = () => {
      setPlayingId(null)
      audioRef.current = null
      URL.revokeObjectURL(url)
    }

    audio.play().catch(() => {})
    audioRef.current = audio
    setPlayingId(msg.id)
  }, [playingId])

  // ── Send message ───────────────────────────────────────────────────────── //
  const sendMessage = useCallback(async (text) => {
    text = text.trim()
    if (!text || isLoading) return

    // Add user bubble
    const userMsg = { id: Date.now(), role: 'user', text }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      const data = await res.json()

      const botMsg = {
        id: Date.now() + 1,
        role: 'bot',
        text: data.text,
        audioB64: data.audio_b64 ?? null,
      }
      setMessages(prev => [...prev, botMsg])

      // Auto-play the response audio
      if (botMsg.audioB64) {
        // Small delay so state has flushed
        setTimeout(() => playAudio(botMsg), 80)
      }

    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'bot',
        text: `Something went wrong: ${err.message}`,
        isError: true,
      }])
    } finally {
      setIsLoading(false)
    }
  }, [isLoading, playAudio])

  const handleKeyDown = e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  const canSend = input.trim().length > 0 && !isLoading && health.status === 'ready'

  // ─────────────────────────────────────────────────────────────────────────── //
  return (
    <div className="app">
      {/* Ambient glow blobs */}
      <div className="blob blob-1" />
      <div className="blob blob-2" />
      <div className="blob blob-3" />

      <div className="shell">
        {/* ── Header ──────────────────────────────────────────────────────── */}
        <header className="header">
          <div className="header-brand">
            {/* Logo mark */}
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none" className="logo-svg">
              <defs>
                <linearGradient id="lg1" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="#7c3aed"/>
                  <stop offset="100%" stopColor="#3b82f6"/>
                </linearGradient>
              </defs>
              <circle cx="16" cy="16" r="15" fill="url(#lg1)"/>
              <ellipse cx="16" cy="15" rx="7" ry="5.5" fill="white" fillOpacity="0.92"/>
              <circle cx="13.5" cy="15" r="1.4" fill="#7c3aed"/>
              <circle cx="18.5" cy="15" r="1.4" fill="#7c3aed"/>
              <path d="M13 19.5 Q16 21 19 19.5" stroke="white" strokeWidth="1.2" strokeLinecap="round" fill="none"/>
            </svg>
            <span className="header-wordmark">VoiceBot</span>
          </div>

          <StatusBar health={health} />
        </header>

        {/* ── Chat ────────────────────────────────────────────────────────── */}
        <main className="chat">
          {messages.length === 0 && !isLoading
            ? <EmptyState onQuickStart={sendMessage} />
            : (
              <>
                {messages.map(msg => (
                  <Message
                    key={msg.id}
                    msg={msg}
                    onPlay={playAudio}
                    playingId={playingId}
                  />
                ))}
                {isLoading && <TypingIndicator />}
              </>
            )
          }
          <div ref={chatEndRef} />
        </main>

        {/* ── Input ───────────────────────────────────────────────────────── */}
        <footer className="footer">
          <div className={`input-bar ${isLoading ? 'input-bar--loading' : ''}`}>
            {/* Mic */}
            <button
              className={`icon-btn mic-btn ${isListening ? 'mic-btn--on' : ''}`}
              onClick={toggleListening}
              title={isListening ? 'Stop listening' : 'Voice input'}
              disabled={isLoading}
            >
              <Icons.Mic active={isListening} />
              {isListening && <span className="mic-ring" />}
            </button>

            {/* Text field */}
            <textarea
              ref={textareaRef}
              className="input-field"
              placeholder={health.status === 'ready'
                ? 'Message VoiceBot…'
                : health.status === 'loading'
                  ? 'Loading models, please wait…'
                  : 'Server offline — start api/server.py'}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={isLoading || health.status !== 'ready'}
            />

            {/* Send */}
            <button
              className={`icon-btn send-btn ${canSend ? 'send-btn--ready' : ''}`}
              onClick={() => sendMessage(input)}
              disabled={!canSend}
              title="Send (Enter)"
            >
              {isLoading ? <Icons.Spinner /> : <Icons.Send />}
            </button>
          </div>

          <p className="footer-hint">
            <kbd>Enter</kbd> to send &nbsp;·&nbsp; <kbd>Shift+Enter</kbd> for newline
            &nbsp;·&nbsp; click <strong>Listen</strong> on any bot message to hear it
          </p>
        </footer>
      </div>
    </div>
  )
}
