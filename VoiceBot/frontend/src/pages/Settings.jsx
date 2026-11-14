import { useCallback, useEffect, useRef, useState } from 'react'
import VoiceInputTest from '../VoiceInputTest'
import SessionAudioSettings from '../SessionAudioSettings'
import { API, Icon, Loading, api } from '../ui/core'

export function Settings({ onChanged, embedded=false, advanced=false }){
  const [state, setState] = useState(null)
  const [recognition,setRecognition]=useState(null)
  const [recognitionEngine,setRecognitionEngine]=useState('nemotron')
  const [recognitionDevice,setRecognitionDevice]=useState('auto')
  const [selectedVoice, setSelectedVoice] = useState('af_heart')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState({ text: '', type: '' })
  const [testText, setTestText] = useState('Hello! I am Hikari, your workplace training assistant.')
  const [testing, setTesting] = useState(false)
  const [auditionPhase,setAuditionPhase]=useState('idle')
  const [testLatency, setTestLatency] = useState(null)
  const [languagePrefs, setLanguagePrefs] = useState({preferred_language:'English',native_language:'Urdu',proficiency_level:'beginner',captions_enabled:true})
  const audioContextRef = useRef(null)
  const currentSourceRef = useRef(null)
  const auditionRequest=useRef(null),auditionSources=useRef(new Set())
  useEffect(()=>()=>{auditionRequest.current?.abort();auditionSources.current.forEach(source=>{try{source.stop()}catch{}});audioContextRef.current?.close().catch(()=>{})},[])

  const load = useCallback(async () => {
    try {
      const [next, preferences, speech] = await Promise.all([api('/tts/engines'), api('/auth/settings'),api('/stt/engines')])
      setState(next)
      setRecognition(speech);setRecognitionEngine(speech.selected);setRecognitionDevice(speech.device)
      setLanguagePrefs(preferences)
      if (next.current_voice) setSelectedVoice(next.current_voice)
    } catch (e) {
      setMessage({ text: e.message, type: 'error' })
    }
  }, [])

  useEffect(() => { load() }, [load])

  const saveLanguagePrefs = async () => {
    setBusy(true)
    try {
      const saved = await api('/auth/settings', {
        method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(languagePrefs)
      })
      setLanguagePrefs(saved)
      setMessage({text:'Language and caption preferences saved.',type:'success'})
      await onChanged()
    } catch (e) {
      setMessage({text:e.message,type:'error'})
    } finally { setBusy(false) }
  }

  const applyEngine = async (engineId, voiceId = selectedVoice) => {
    setBusy(true)
    setMessage({ text: `Switching to ${engineId}… Please wait.`, type: 'info' })
    try {
      const payload = { engine: engineId }
      if (engineId === 'kokoro' && voiceId) payload.voice = voiceId
      const next = await api('/tts/engine', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      setState(next)
      if (next.current_voice) setSelectedVoice(next.current_voice)
      const engineObj = next.engines.find(e => e.id === next.active)
      const engineName = engineObj?.name || next.active
      setMessage({
        text: `${engineName} is now active${next.active === 'kokoro' ? ` (Voice: ${voiceId})` : ''}.`,
        type: 'success'
      })
      await onChanged()
    } catch (e) {
      setMessage({ text: `Failed to switch voice engine: ${e.message}`, type: 'error' })
      await load()
    } finally {
      setBusy(false)
    }
  }

  const applyRecognition=async()=>{
    setBusy(true);setMessage({text:'Loading recognition model. Keep the microphone paused…',type:'info'})
    try{
      const next=await api('/stt/engine',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({engine:recognitionEngine,device:recognitionDevice})})
      setRecognition(next)
      setMessage({text:`Recognition active: ${next.runtime?.model||next.selected} on ${next.runtime?.device||'unknown'}.${next.runtime?.fallback_reason?` ${next.runtime.fallback_reason}`:''}`,type:'success'})
      await onChanged()
    }catch(error){setMessage({text:error.message,type:'error'})}
    finally{setBusy(false)}
  }

  const stopAudio = () => {
    auditionRequest.current?.abort()
    auditionSources.current.forEach(source=>{try{source.stop()}catch{}});auditionSources.current.clear()
    if (currentSourceRef.current) {
      try { currentSourceRef.current.stop() } catch {}
      currentSourceRef.current = null
    }
    setTesting(false)
    setAuditionPhase('idle')
  }

  const testVoice = async () => {
    if (testing) {
      stopAudio()
      return
    }
    if (!testText.trim()) return
    setTesting(true)
    setAuditionPhase('generating');setTestLatency(null)
    const controller=new AbortController();auditionRequest.current=controller
    setMessage({ text: '', type: '' })
    const startTime = performance.now()

    try {
      if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
        const AudioCtx = window.AudioContext || window.webkitAudioContext
        audioContextRef.current = new AudioCtx()
      }
      if (audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume()
      }

      const response = await fetch(`${API}/tts/stream`, {
        method: 'POST',
        signal:controller.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: testText, correlation_id: 'test-audition' })
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || 'Voice synthesis failed.')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let pending = ''
      const audioChunks = []
      let firstChunkTime = null
      let playbackEnd=audioContextRef.current.currentTime

      while (true) {
        const { value, done } = await reader.read()
        pending += decoder.decode(value || new Uint8Array(), { stream: !done })
        const lines = pending.split('\n')
        pending = lines.pop() || ''
        for (const line of lines) {
          if (!line.trim()) continue
          const event = JSON.parse(line)
          if(event.tts_timing)console.info('[Hikari TTS latency]',event.tts_timing)
          if (event.type === 'error') throw new Error(event.message)
          if (event.type === 'audio') {
            if (!firstChunkTime) firstChunkTime = Math.round(performance.now() - startTime)
            const binary = atob(event.audio_b64)
            const bytes = new Uint8Array(binary.length)
            for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
            audioChunks.push(bytes)
            const context=audioContextRef.current
            const decoded=await context.decodeAudioData(bytes.buffer.slice(0))
            if(controller.signal.aborted)return
            const source=context.createBufferSource();source.buffer=decoded;source.connect(context.destination)
            auditionSources.current.add(source);source.onended=()=>auditionSources.current.delete(source)
            source.start(Math.max(context.currentTime+.05,playbackEnd))
            playbackEnd=Math.max(context.currentTime+.05,playbackEnd)+decoded.duration
            setAuditionPhase('playing')
          }
        }
        if (done) break
      }

      if (!audioChunks.length) throw new Error('No audio returned from engine.')

      setTestLatency(firstChunkTime || Math.round(performance.now() - startTime))

      await new Promise(resolve=>setTimeout(resolve,Math.max(0,playbackEnd-audioContextRef.current.currentTime)*1000+50))
    } catch (e) {
      if(e.name!=='AbortError')setMessage({ text: `Audio audition error: ${e.message}`, type: 'error' })
    } finally {if(auditionRequest.current===controller){setTesting(false);setAuditionPhase('idle')}}
  }

  if (!state) {
    return (
      <section className={`page settings-page${embedded?' settings-embedded':''}`}>
        <header className="page-head compact">
          <div>
            <p className="eyebrow">PREFERENCES</p>
            <h1>Voice Settings</h1>
          </div>
        </header>
        {message.text ? <div className="error">{message.text}</div> : <Loading />}
      </section>
    )
  }

  const activeEngineObj = state.engines.find(e => e.id === state.active)
  const isKokoroActive = state.active === 'kokoro'

  return (
    <section className={`page settings-page${embedded?' settings-embedded':''}`}>
      <header className="page-head">
        <div>
          <p className="eyebrow">LANGUAGE AND CAPTIONS</p>
          <h2>Language and captions</h2>
          <p>Choose your training language, caption language and level.</p>
        </div>
        {advanced&&<div className="active-engine-badge">
          <span className="live-dot ready" />
          <div>
            <strong>{activeEngineObj?.name || state.active} Active</strong>
            <small>{state.sample_rate / 1000} kHz · {state.active === 'kokoro' ? `${selectedVoice}` : state.runtime ? `${String(state.runtime.backend||state.runtime.device||'local').toUpperCase()} · ${state.runtime.device_name||'Local device'}` : 'Native'}</small>
          </div>
        </div>}
      </header>

      {message.text && (
        <div className={`settings-alert ${message.type}`}>
          <span><Icon name={message.type === 'error' ? 'warning' : message.type === 'success' ? 'checkCircle' : 'info'}/></span>
          <p>{message.text}</p>
          <button type="button" aria-label="Dismiss notification" onClick={() => setMessage({ text: '', type: '' })}><Icon name="close"/></button>
        </div>
      )}

      <section className="settings-section language-preferences">
        <div className="section-title"><div><p className="eyebrow">LANGUAGE LEARNING</p><h2>Dialogue & caption languages</h2><p>Beginner English stays spoken in English while captions are translated into your native language.</p></div></div>
        <div className="voice-picker-row">
          <label>Training language<select value={languagePrefs.preferred_language} onChange={e=>setLanguagePrefs({...languagePrefs,preferred_language:e.target.value})}>{['English','Japanese','Arabic','Chinese','Korean'].map(item=><option key={item}>{item}</option>)}</select></label>
          <label>Native caption language<select value={languagePrefs.native_language} onChange={e=>setLanguagePrefs({...languagePrefs,native_language:e.target.value})}>{['Urdu','English','Japanese','Arabic','Chinese','Korean'].map(item=><option key={item}>{item}</option>)}</select></label>
          <label>English proficiency<select value={languagePrefs.proficiency_level} onChange={e=>setLanguagePrefs({...languagePrefs,proficiency_level:e.target.value})}><option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select></label>
          <label>Translated captions<input type="checkbox" checked={languagePrefs.captions_enabled} onChange={e=>setLanguagePrefs({...languagePrefs,captions_enabled:e.target.checked})}/></label>
          <button className="primary-outline-btn" onClick={saveLanguagePrefs} disabled={busy}>Save language preferences</button>
        </div>
      </section>

      {advanced&&<details className="settings-advanced">
        <summary><span><b>Advanced: speech engines and diagnostics</b><small>For administrators and testers. Changes here affect every learner on this computer.</small></span></summary>
      <section className="settings-section">
        <div className="section-title"><div><p className="eyebrow">SPEECH RECOGNITION</p><h2>Microphone recognition engine</h2><p>Pause the microphone before switching. This changes recognition, not the AI voice.</p></div></div>
        <div className="voice-picker-row">
          <label>Recognition model<select value={recognitionEngine} disabled={busy} onChange={event=>setRecognitionEngine(event.target.value)}>{recognition?.engines.map(engine=><option key={engine.id} value={engine.id} disabled={!engine.installed}>{engine.name}{engine.installed?'':' — not installed'}</option>)}</select></label>
          <label>Execution device<select value={recognitionDevice} disabled={busy} onChange={event=>setRecognitionDevice(event.target.value)}><option value="auto">Automatic (GPU when available)</option><option value="cpu">CPU only</option><option value="cuda" disabled={!recognition?.cuda?.available}>{recognitionEngine==='nemotron'?'Nemotron CUDA — GPU only':'CUDA — GPU only'}{recognition?.cuda?.available?'':' — unavailable'}</option></select></label>
          <button className="primary-outline-btn" disabled={busy||!recognition?.engines.find(engine=>engine.id===recognitionEngine)?.installed||(recognitionDevice==='cuda'&&!recognition?.cuda?.available)} onClick={applyRecognition}>Apply recognition mode</button>
        </div>
        <p>{recognition?.engines.find(engine=>engine.id===recognitionEngine)?.description}</p>
        <p>{recognition?.cuda?.available?`CUDA available: ${recognition.cuda.device_name}. GPU-only mode must load on CUDA; it will not silently switch to CPU.`:recognition?.cuda?.reason} CUDA accelerates recognition; the same model and decoder do not inherently become more accurate. Model loading is verified when you apply the mode.</p>
        <p>For English on CPU, try Nemotron with “CPU only”: it keeps live recognition and uses the same model weights. Whisper Small is the lower-cost multilingual option; Medium favors capacity over speed.</p>
        <small>Running: {recognition?.runtime?.model||'Not loaded'} · {recognition?.runtime?.device||'—'} · {recognition?.runtime?.compute_type||'—'}. CPU speed depends on the machine; equal GPU speed is not guaranteed.</small>
      </section>

      <SessionAudioSettings request={api}/>
      <VoiceInputTest request={api} runtime={recognition?.runtime}/>

      {/* TTS Engine Cards */}
      <section className="settings-section">
        <div className="section-title">
          <div>
            <p className="eyebrow">TTS ENGINES</p>
            <h2>Choose Speech Engine</h2>
          </div>
          {!isKokoroActive && (
            <button
              className="primary-outline-btn"
              onClick={() => applyEngine('kokoro', selectedVoice)}
              disabled={busy}
            >
              <Icon name="sparkles" /> Set Kokoro as Default
            </button>
          )}
        </div>

        {state.active==='chattts'&&state.runtime&&<div className={`settings-alert ${state.runtime.backend==='cuda'?'success':'error'}`}><span><Icon name={state.runtime.backend==='cuda'?'checkCircle':'warning'}/></span><p><strong>ChatTTS acceleration:</strong> {state.runtime.device} · {state.runtime.device_name}. Model modules: {Object.entries(state.runtime.module_devices||{}).map(([name,device])=>`${name} ${device}`).join(', ')}.</p></div>}

        <div className="engine-cards-grid">
          {state.engines.map(engine => {
            const isActive = engine.id === state.active
            const isDefault = engine.default || engine.id === 'kokoro'

            return (
              <article
                key={engine.id}
                className={`engine-card-option ${isActive ? 'active' : ''} ${isDefault ? 'default-card' : ''}`}
              >
                <div className="engine-card-head">
                  <div>
                    <div className="badges-row">
                      {isDefault && <span className="badge badge-default"><Icon name="star"/> Default & Recommended</span>}
                      {isActive && <span className="badge badge-active">Active</span>}
                      {engine.latency_label && <span className="badge badge-latency">{engine.latency_label}</span>}
                    </div>
                    <h3>{engine.name}</h3>
                  </div>
                  <span className={`radio-indicator ${isActive ? 'checked' : ''}`}>
                    {isActive && <i />}
                  </span>
                </div>

                <p className="engine-desc">{engine.description}</p>

                {engine.features && (
                  <ul className="engine-feature-list">
                    {engine.features.map((feat, i) => (
                      <li key={i}><Icon name="check"/> {feat}</li>
                    ))}
                  </ul>
                )}

                <div className="engine-card-foot">
                  <span className="lang-tag">{engine.language}</span>
                  <button
                    className={`engine-action-btn ${isActive ? 'btn-active' : 'btn-switch'}`}
                    disabled={busy || isActive || (!engine.installed && !engine.download_on_select)}
                    onClick={(e) => {
                      e.stopPropagation()
                      applyEngine(engine.id, selectedVoice)
                    }}
                  >
                    {isActive ? 'Active' : busy ? 'Loading…' : !engine.installed ? (engine.download_on_select ? 'Download & Switch' : 'Not installed') : 'Switch Engine'}
                  </button>
                </div>
              </article>
            )
          })}
        </div>
      </section>

      {/* Kokoro Voice Persona Selection (active when Kokoro is chosen) */}
      {isKokoroActive && (
        <section className="settings-section">
          <div className="section-title">
            <div>
              <p className="eyebrow">VOICE PERSONA</p>
              <h2>Kokoro Voice Selection</h2>
            </div>
            <span className="voice-active-indicator">Current: <strong>{selectedVoice}</strong></span>
          </div>

          <div className="voice-selection-box">
            <div className="voice-picker-row">
              <label htmlFor="voice-select">
                <strong>Speaker Voice Profile</strong>
                <small>Select from high-definition natural voices (American, British, Japanese).</small>
              </label>
              <select
                id="voice-select"
                value={selectedVoice}
                onChange={(e) => {
                  const newVoice = e.target.value
                  setSelectedVoice(newVoice)
                  applyEngine('kokoro', newVoice)
                }}
                disabled={busy}
              >
                {state.voices?.map(v => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="voice-chips-grid">
              {state.voices?.map(v => (
                <button
                  key={v.id}
                  className={`voice-chip ${selectedVoice === v.id ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedVoice(v.id)
                    applyEngine('kokoro', v.id)
                  }}
                  disabled={busy}
                >
                  <div>
                    <strong>{v.name.split(' ')[0]}</strong>
                    <small>{v.gender} · {v.accent}</small>
                  </div>
                  {selectedVoice === v.id && <span className="chip-check"><Icon name="check"/></span>}
                </button>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Real-time Voice Audition Lab */}
      <section className="settings-section audition-section">
        <div className="section-title">
          <div>
            <p className="eyebrow">INTERACTIVE AUDITION</p>
            <h2>Test Voice Playback</h2>
          </div>
          {testLatency && (
            <span className="latency-indicator">
              First audio received in <strong>{testLatency} ms</strong>
            </span>
          )}
        </div>

        <div className="audition-panel">
          <div className="audition-input-group">
            <label htmlFor="audition-text">Sample Phrase</label>
            <input
              id="audition-text"
              type="text"
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
              placeholder="Enter phrase to synthesize and test audio output…"
              disabled={testing}
            />
            <div className="sample-phrases">
              <span>Try quick phrases:</span>
              <button
                type="button"
                onClick={() => setTestText('Hello! I am Hikari, your workplace training assistant.')}
              >
                Greeting
              </button>
              <button
                type="button"
                onClick={() => setTestText('Thank you for contacting us today. How may I assist with your inquiry?')}
              >
                Customer Service
              </button>
              <button
                type="button"
                onClick={() => setTestText('Great job on your phrasing! That was clear, courteous, and reassuring.')}
              >
                Coaching Feedback
              </button>
            </div>
          </div>

          <div className="audition-actions">
            <button
              className={`primary test-play-btn ${testing ? 'playing' : ''}`}
              onClick={testVoice}
              disabled={busy||!testText.trim()}
            >
              <Icon name={testing ? 'stop' : 'speaker'} />
              {testing ? auditionPhase==='generating'?'Generating… Click to stop':'Playing… Click to stop' : 'Test Voice Audio'}
            </button>
            {testing && (
              <div className="audio-wave">
                <i /><i /><i /><i /><i />
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Engine Architecture Benchmarks */}
      <section className="settings-section">
        <div className="section-title">
          <div>
            <p className="eyebrow">SYSTEM ARCHITECTURE</p>
            <h2>Engine Benchmarks & Resource Profile</h2>
          </div>
        </div>

        <div className="benchmarks-grid">
          <div className="benchmark-card highlighted">
            <span className="bm-pill">DEFAULT</span>
            <h4>Kokoro ONNX</h4>
            <div className="bm-metric">
              <small>Time to First Audio</small>
              <strong>&lt; 150 ms</strong>
            </div>
            <div className="bm-metric">
              <small>System Memory</small>
              <strong>~400 MB</strong>
            </div>
            <div className="bm-metric">
              <small>Optimal Usage</small>
              <span>Instant roleplay conversations on CPU</span>
            </div>
          </div>

          <div className="benchmark-card">
            <span className="bm-pill neutral">ADVANCED</span>
            <h4>ChatTTS</h4>
            <div className="bm-metric">
              <small>Time to First Audio</small>
              <strong>~2,500 ms</strong>
            </div>
            <div className="bm-metric">
              <small>System Memory</small>
              <strong>~4 GB</strong>
            </div>
            <div className="bm-metric">
              <small>Optimal Usage</small>
              <span>Conversational prosody & laughter tokens</span>
            </div>
          </div>

          <div className="benchmark-card">
            <span className="bm-pill neutral">SPECIALIZED</span>
            <h4>VITS Piper</h4>
            <div className="bm-metric">
              <small>Time to First Audio</small>
              <strong>~300 ms</strong>
            </div>
            <div className="bm-metric">
              <small>System Memory</small>
              <strong>~200 MB</strong>
            </div>
            <div className="bm-metric">
              <small>Optimal Usage</small>
              <span>Native Japanese & Arabic language training</span>
            </div>
          </div>
        </div>
      </section>
      </details>}
    </section>
  )
}

export function SettingsModal({ isOpen, onClose, onChanged, advanced=false }){
  const dialog=useRef(null)
  const closeRef=useRef(onClose);closeRef.current=onClose
  useEffect(()=>{
    if(!isOpen)return
    const previous=document.activeElement,overflow=document.body.style.overflow
    document.body.style.overflow='hidden';dialog.current?.querySelector('button')?.focus()
    const keydown=event=>{
      if(event.key==='Escape'){event.preventDefault();closeRef.current()}
      if(event.key==='Tab'){
        const controls=[...dialog.current.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled)')]
        const first=controls[0],last=controls[controls.length-1]
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
      }
    }
    document.addEventListener('keydown',keydown)
    return()=>{document.body.style.overflow=overflow;document.removeEventListener('keydown',keydown);previous?.focus()}
  },[isOpen])
  if (!isOpen) return null
  return (
    <div className="settings-modal-backdrop" onClick={onClose}>
      <div ref={dialog} className="settings-modal-dialog" role="dialog" aria-modal="true" aria-labelledby="speech-settings-title" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <p className="eyebrow">PREFERENCES</p>
            <h2 id="speech-settings-title">Speech & Voice Settings</h2>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close Settings"><Icon name="close"/></button>
        </div>
        <div className="modal-scroll-area">
          <Settings onChanged={onChanged} advanced={advanced}/>
        </div>
      </div>
    </div>
  )
}
