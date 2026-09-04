import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import './Monitor.css'

const API = '/api'
const api = async (path, options = {}) => {
  const response = await fetch(`${API}${path}`, options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || 'Something went wrong')
  return data
}

const Icon = ({ name }) => {
  const paths = {
    dashboard: <><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></>,
    practice: <><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3"/></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></>,
    docs: <><path d="M6 2h9l4 4v16H6z"/><path d="M14 2v5h5M9 12h7M9 16h7"/></>,
    monitor: <><path d="M3 3v18h18"/><path d="m6 16 4-5 3 3 5-8"/><path d="M17 6h1v1"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1z"/></>,
    send: <><path d="M22 2 11 13"/><path d="m22 2-7 20-4-9-9-4z"/></>,
    camera: <><path d="M14.5 4 16 7h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h3l1.5-3z"/><circle cx="12" cy="13" r="3"/></>,
  }
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

function Sidebar({ view, setView, health }) {
  const nav = [['dashboard', 'Overview'], ['practice', 'Practice'], ['history', 'History'], ['docs', 'Knowledge'], ['monitor', 'Monitor'], ['settings', 'Settings']]
  return <aside className="sidebar">
    <div className="brand"><span className="brand-mark">光</span><div><strong>Hikari</strong><small>Employee Trainer</small></div></div>
    <nav>{nav.map(([id, label]) => <button key={id} className={view === id ? 'active' : ''} onClick={() => setView(id)}><Icon name={id}/>{label}</button>)}</nav>
    <div className="engine-card"><span className={`live-dot ${health.status}`}/><div><strong>{health.status === 'ready' ? 'Voice ready' : 'Limited mode'}</strong><small>{health.engine||'TTS loading'} · {health.sample_rate?`${health.sample_rate/1000} kHz`:'—'}</small></div></div>
    <div className="profile"><span>DL</span><div><strong>Demo Learner</strong><small>Employee</small></div></div>
  </aside>
}

function ScoreRing({ score, size = 116 }) {
  const r = 45, c = 2 * Math.PI * r
  return <div className="score-ring" style={{ width: size, height: size }}>
    <svg viewBox="0 0 110 110"><circle className="ring-base" cx="55" cy="55" r={r}/><circle className="ring-value" cx="55" cy="55" r={r} strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)}/></svg>
    <div><strong>{Math.round(score)}</strong><small>/100</small></div>
  </div>
}

function Dashboard({ data, onStart, setView }) {
  if (!data) return <Loading/>
  return <main className="page">
    <header className="page-head"><div><p className="eyebrow">YOUR TRAINING SPACE</p><h1>Welcome back, {data.user.name.split(' ')[0]}</h1><p>Build confidence through short, realistic workplace conversations.</p></div><button className="primary" onClick={() => setView('practice')}>Start practice</button></header>
    <section className="overview-grid">
      <article className="overall-card"><div><p className="label">Overall proficiency</p><h2>{data.completed_sessions ? 'Building momentum' : 'Ready for baseline'}</h2><p>{data.completed_sessions ? `${data.completed_sessions} completed session${data.completed_sessions === 1 ? '' : 's'}` : 'Complete your first scenario to establish a score.'}</p></div><ScoreRing score={data.overall}/></article>
      <article className="recommend-card"><div className="card-kicker">RECOMMENDED NEXT</div><h2>{data.recommendation.skill}</h2><p>{data.recommendation.reason}</p><div className="rec-footer"><span>{data.recommendation.difficulty}</span><button onClick={() => onStart(data.recommendation.skill_id, data.recommendation.difficulty)}>Practise now →</button></div></article>
    </section>
    <section className="section"><div className="section-title"><div><p className="eyebrow">SKILL MAP</p><h2>Your capabilities</h2></div><button className="text-button" onClick={() => setView('practice')}>View all</button></div>
      <div className="skill-grid">{data.skills.slice(0, 6).map(skill => <article className="skill-card" key={skill.id}><div className="skill-top"><span className="skill-glyph">{skill.name.slice(0,1)}</span><span className="skill-score">{Math.round(skill.score)}</span></div><h3>{skill.name}</h3><p>{skill.description}</p><div className="progress"><i style={{width: `${skill.score}%`}}/></div><small>{skill.sessions ? `${skill.sessions} session${skill.sessions > 1 ? 's' : ''}` : 'Not practised yet'}</small></article>)}</div>
    </section>
    <section className="section split"><div><p className="eyebrow">THREE-SESSION PLAN</p><h2>Focused practice</h2><div className="plan-list">{data.plan.map((item, i) => <button key={item.day} onClick={() => onStart(item.skill_id, i ? 'intermediate' : 'beginner')}><span>{i + 1}</span><div><strong>{item.activity}</strong><small>Focus: {item.focus}</small></div><b>→</b></button>)}</div></div><div><p className="eyebrow">RECENT RESULTS</p><h2>Session history</h2>{data.recent_sessions.length ? <div className="result-list">{data.recent_sessions.slice(0,3).map(s => <div key={s.id}><span>{s.title.slice(0,1)}</span><div><strong>{s.title}</strong><small>{s.skill_id.replaceAll('-', ' ')}</small></div><b>{Math.round(s.overall)}</b></div>)}</div> : <div className="empty-panel">Your completed roleplays will appear here.</div>}</div></section>
  </main>
}

function Practice({ skills, onStart }) {
  const [difficulty, setDifficulty] = useState('intermediate')
  return <main className="page"><header className="page-head compact"><div><p className="eyebrow">SCENARIO LIBRARY</p><h1>Choose what to practise</h1><p>Every roleplay adapts to your current proficiency and recent results.</p></div><div className="difficulty">{['beginner','intermediate','advanced'].map(x => <button className={difficulty === x ? 'active' : ''} onClick={() => setDifficulty(x)} key={x}>{x}</button>)}</div></header>
    <div className="catalog">{skills.map((skill, i) => <article key={skill.id}><div className="catalog-number">{String(i + 1).padStart(2,'0')}</div><div><h2>{skill.name}</h2><p>{skill.description}</p><div className="tags">{skill.subskills.map(x => <span key={x}>{x}</span>)}</div></div><div className="catalog-action"><strong>{Math.round(skill.score)}</strong><small>proficiency</small><button onClick={() => onStart(skill.id, difficulty)}>Start →</button></div></article>)}</div>
  </main>
}

function Roleplay({ session, setSession, onComplete }) {
  const [mode, setMode] = useState('voice')
  const [callActive, setCallActive] = useState(false)
  const [muted, setMuted] = useState(false)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [recording, setRecording] = useState(false)
  const [micState, setMicState] = useState('idle')
  const [micLevel, setMicLevel] = useState(0)
  const [micDevice, setMicDevice] = useState('No microphone selected')
  const [voiceState, setVoiceState] = useState('idle')
  const [micOptions, setMicOptions] = useState([])
  const [selectedMic, setSelectedMic] = useState(()=>localStorage.getItem('hikari-mic-id')||'')
  const [camera, setCamera] = useState(false)
  const [posture, setPosture] = useState(null)
  const recorder = useRef(null), chunks = useRef([]), started = useRef(0), video = useRef(null), media = useRef(null), chatEnd = useRef(null)
  const playbackContext = useRef(null), playbackTail = useRef(0)
  const callActiveRef = useRef(false), mutedRef = useRef(false), modeRef = useRef('voice'), beginListening = useRef(null), discardCapture = useRef(false)
  const micStream = useRef(null), micContext = useRef(null), micFrame = useRef(null), speechSeen = useRef(false), lastSpeech = useRef(0), peakLevel = useRef(0), lastLevelReport = useRef(0), noiseFloor = useRef(.003)
  useEffect(() => { chatEnd.current?.scrollIntoView({behavior:'smooth'}) }, [session.turns, busy])
  useEffect(() => () => { media.current?.getTracks().forEach(t => t.stop()); micStream.current?.getTracks().forEach(t => t.stop()); if(micFrame.current)cancelAnimationFrame(micFrame.current); micContext.current?.close(); playbackContext.current?.close() }, [])
  useEffect(() => {
    if (!camera || !('FaceDetector' in window)) return undefined
    const detector = new window.FaceDetector({fastMode:true})
    const analyse = async () => {
      if (!video.current?.videoWidth) return
      try {
        const faces = await detector.detect(video.current)
        if (!faces[0]) return
        const b=faces[0].boundingBox,w=video.current.videoWidth,h=video.current.videoHeight
        const centered=Math.max(0,100-Math.abs((b.x+b.width/2)-w/2)/w*220)
        const upright=Math.max(0,100-Math.abs((b.y+b.height/2)-h*.4)/h*180)
        const scale=Math.max(0,100-Math.abs(b.height/h-.35)*180)
        const sample={slouching:upright,head_position:centered,shoulder_alignment:(centered+scale)/2,body_orientation:centered}
        setPosture(sample)
        await api(`/sessions/${session.id}/posture`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(sample)})
      } catch { /* posture is optional; keep the call uninterrupted */ }
    }
    analyse()
    const timer=setInterval(analyse,5000)
    return ()=>clearInterval(timer)
  }, [camera, session.id])
  const ensureAudioReady = async () => {
    const AudioContext=window.AudioContext||window.webkitAudioContext
    if(!AudioContext)throw new Error('This browser does not support streamed audio playback.')
    if(!playbackContext.current)playbackContext.current=new AudioContext()
    if(playbackContext.current.state==='suspended')await playbackContext.current.resume()
    return playbackContext.current
  }
  const playChunk = async b64 => {
    const context=await ensureAudioReady()
    const bytes=Uint8Array.from(atob(b64),character=>character.charCodeAt(0))
    const buffer=await context.decodeAudioData(bytes.buffer.slice(0))
    const source=context.createBufferSource();source.buffer=buffer;source.connect(context.destination)
    const at=Math.max(context.currentTime+.025,playbackTail.current);source.start(at);playbackTail.current=at+buffer.duration
    return playbackTail.current
  }
  const waitForPlayback = async () => {
    const context=playbackContext.current
    if(!context)return
    const remaining=Math.max(0,playbackTail.current-context.currentTime)*1000
    if(remaining)await new Promise(resolve=>setTimeout(resolve,remaining+80))
  }
  const replay = async audioChunks => {
    try{playbackTail.current=0;setVoiceState('replaying');for(const chunk of audioChunks)await playChunk(chunk);await waitForPlayback();setVoiceState('ready')}
    catch(e){setVoiceState('blocked');setError(`Audio playback failed: ${e.message}. Allow sound for localhost, then use Play response.`)}
  }
  const streamVoice = async (reply,correlationId) => {
    setVoiceState('generating')
    const response=await fetch(`${API}/tts/stream`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:reply,correlation_id:correlationId})})
    if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.detail||'ChatTTS is unavailable.')}
    if(!response.body)throw new Error('Streaming audio is not supported by this browser.')
    const reader=response.body.getReader(),decoder=new TextDecoder();let pending='',received=0
    while(true){
      const {value,done}=await reader.read();pending+=decoder.decode(value||new Uint8Array(),{stream:!done})
      const lines=pending.split('\n');pending=lines.pop()||''
      for(const line of lines){
        if(!line.trim())continue
        const event=JSON.parse(line)
        if(event.type==='error')throw new Error(event.message)
        if(event.type==='audio'){
          received+=1
          setSession(s=>({...s,turns:s.turns.map(turn=>turn.correlationId===correlationId?{...turn,audioChunks:[...(turn.audioChunks||[]),event.audio_b64]}:turn)}))
          setVoiceState(received===1?'speaking':'streaming')
          await playChunk(event.audio_b64)
        }
      }
      if(done)break
    }
    if(!received)throw new Error('ChatTTS returned no playable audio.')
    await waitForPlayback()
    setVoiceState('ready')
    if(callActiveRef.current&&modeRef.current==='voice'&&!mutedRef.current){
      setTimeout(()=>{if(callActiveRef.current&&!mutedRef.current)beginListening.current?.()},350)
    }
  }
  const reportMic = payload => api('/monitor/microphone',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).catch(()=>{})
  const send = async (value = text, duration = 0) => {
    if (!value.trim() || busy) return
    ensureAudioReady().catch(()=>{})
    setBusy(true); setError(''); setText('')
    setSession(s => ({...s, turns:[...s.turns,{role:'user',text:value}]}))
    try {
      const result = await api(`/sessions/${session.id}/turn`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:value,duration_seconds:duration,synthesize_audio:false})})
      setSession(s => ({...s, turns:[...s.turns,{role:'assistant',text:result.text,sources:result.sources,correlationId:result.correlation_id,audioChunks:[]}]}))
      setBusy(false)
      streamVoice(result.text,result.correlation_id).catch(e=>{setVoiceState('failed');setError(`The text response is ready, but voice failed: ${e.message}`)})
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const toggleMic = async () => {
    if (recording) { recorder.current.stop(); return }
    try {
      await ensureAudioReady()
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone capture requires localhost or HTTPS.')
      const audioOptions={deviceId:selectedMic?{exact:selectedMic}:undefined,echoCancellation:true,noiseSuppression:true,autoGainControl:true}
      let stream
      try{stream=await navigator.mediaDevices.getUserMedia({audio:audioOptions})}catch(firstError){if(!selectedMic)throw firstError;localStorage.removeItem('hikari-mic-id');setSelectedMic('');stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}})}
      micStream.current=stream
      const track=stream.getAudioTracks()[0], settings=track.getSettings(), device=track.label||'Default microphone'
      const devices=(await navigator.mediaDevices.enumerateDevices()).filter(item=>item.kind==='audioinput')
      setMicOptions(devices);if(!selectedMic&&settings.deviceId){setSelectedMic(settings.deviceId);localStorage.setItem('hikari-mic-id',settings.deviceId)}
      setMicDevice(device); setMicState('listening'); setMicLevel(0); speechSeen.current=false; lastSpeech.current=0; peakLevel.current=0;lastLevelReport.current=0;noiseFloor.current=.003
      reportMic({event:'connected',device,state:'ready',sample_rate:settings.sampleRate,channel_count:settings.channelCount})
      const AudioContext=window.AudioContext||window.webkitAudioContext
      const context=new AudioContext(), analyser=context.createAnalyser(), source=context.createMediaStreamSource(stream)
      analyser.fftSize=1024; analyser.smoothingTimeConstant=.35; source.connect(analyser); micContext.current=context
      const samples=new Float32Array(analyser.fftSize)
      const r = new MediaRecorder(stream); chunks.current=[]; started.current=performance.now(); recorder.current=r
      r.ondataavailable = e => e.data.size && chunks.current.push(e.data)
      r.onstop = async () => {
        const captureMs=performance.now()-started.current
        if(micFrame.current)cancelAnimationFrame(micFrame.current); micFrame.current=null
        stream.getTracks().forEach(t=>t.stop()); micStream.current=null; await context.close().catch(()=>{}); micContext.current=null
        setRecording(false);setMicLevel(0)
        if(discardCapture.current){discardCapture.current=false;setMicState('idle');setBusy(false);return}
        setMicState('transcribing');setBusy(true)
        reportMic({event:'stopped',device,state:'transcribing',duration_ms:captureMs,peak_percent:peakLevel.current})
        try {
          const form=new FormData();form.append('file',new Blob(chunks.current,{type:r.mimeType}),'speech.webm')
          const out=await api('/transcribe',{method:'POST',body:form})
          if(!out.text)throw new Error('No speech detected. Check the live level and try speaking closer to the selected microphone.')
          setText(out.text);setMicState('transcribed');reportMic({event:'transcribed',device,state:'complete',duration_ms:out.latency_ms||0,peak_percent:peakLevel.current,transcript:out.text})
          await send(out.text,captureMs/1000)
        } catch(e){setMicState('error');setError(e.message);reportMic({event:'error',device,state:'error',duration_ms:captureMs,peak_percent:peakLevel.current,error:e.message});setBusy(false)}
      }
      const analyse=()=>{
        analyser.getFloatTimeDomainData(samples)
        const rms=Math.sqrt(samples.reduce((sum,value)=>sum+value*value,0)/samples.length)
        const level=Math.min(100,rms*500);peakLevel.current=Math.max(peakLevel.current,level);setMicLevel(level)
        const now=performance.now()
        const elapsed=now-started.current
        if(elapsed<500&&!speechSeen.current)noiseFloor.current=noiseFloor.current*.75+rms*.25
        const threshold=Math.max(.005,Math.min(.025,noiseFloor.current*2.4)),thresholdPercent=Math.min(100,threshold*500)
        if(now-lastLevelReport.current>500){lastLevelReport.current=now;reportMic({event:'level',device,state:speechSeen.current?'speech detected':'listening',duration_ms:elapsed,level_percent:level,peak_percent:peakLevel.current,threshold_percent:thresholdPercent})}
        if(elapsed>250&&rms>threshold){lastSpeech.current=now;if(!speechSeen.current){speechSeen.current=true;setMicState('speech detected');reportMic({event:'speech_detected',device,state:'recording',duration_ms:elapsed,level_percent:level,threshold_percent:thresholdPercent})}}
        if(speechSeen.current&&now-lastSpeech.current>1200&&now-started.current>900&&r.state==='recording')r.stop()
        else if(elapsed>20000&&r.state==='recording')r.stop()
        else micFrame.current=requestAnimationFrame(analyse)
      }
      r.start(250); setRecording(true);reportMic({event:'listening',device,state:'listening'});micFrame.current=requestAnimationFrame(analyse);return true
    } catch(e) { setMicState('error');setError(`Microphone unavailable: ${e.message}`);reportMic({event:'error',state:'error',error:e.message});return false }
  }
  beginListening.current=toggleMic
  const stopCall = () => {
    callActiveRef.current=false;setCallActive(false);mutedRef.current=false;setMuted(false);setVoiceState('idle');setMicState('idle')
    if(recorder.current?.state==='recording'){discardCapture.current=true;recorder.current.stop()}
    else{micStream.current?.getTracks().forEach(track=>track.stop());micStream.current=null}
    playbackContext.current?.close();playbackContext.current=null;playbackTail.current=0
  }
  const startCall = async () => {
    callActiveRef.current=true;modeRef.current='voice';mutedRef.current=false;setCallActive(true);setMuted(false);setError('')
    if(!await toggleMic()){callActiveRef.current=false;setCallActive(false)}
  }
  const changeMode = next => {
    if(next===mode)return
    if(callActiveRef.current)stopCall()
    modeRef.current=next;setMode(next);setError('')
  }
  const toggleMute = () => {
    const next=!muted;mutedRef.current=next;setMuted(next)
    if(next&&recorder.current?.state==='recording'){discardCapture.current=true;recorder.current.stop()}
    if(!next&&callActiveRef.current)setTimeout(()=>beginListening.current?.(),100)
  }
  const toggleCamera = async () => {
    if (camera) { media.current?.getTracks().forEach(t=>t.stop()); media.current=null; setCamera(false); return }
    try {
      const stream=await navigator.mediaDevices.getUserMedia({video:{width:640,height:480}}); media.current=stream; setCamera(true)
      setTimeout(()=>{ if(video.current) video.current.srcObject=stream },0)
    } catch(e){setError(`Camera unavailable: ${e.message}`)}
  }
  const latestReply=[...session.turns].reverse().find(turn=>turn.role==='assistant')
  const callStatus=!callActive?'Ready to start':muted?'Microphone muted':busy||micState==='transcribing'?'Understanding you…':voiceState==='generating'?'Preparing response…':voiceState==='speaking'||voiceState==='streaming'?`${session.counterpart} is speaking`:recording?(micState==='speech detected'?'Listening to you…':'Listening…'):'Connected'
  return <main className="roleplay-page"><header className="roleplay-head"><button className="back" onClick={() => {stopCall();setSession(null)}}>← Exit</button><div className="roleplay-title"><span className="live-pill">LIVE ROLEPLAY</span><strong>{session.title}</strong><div className="mode-switch" role="tablist" aria-label="Conversation mode"><button role="tab" aria-selected={mode==='voice'} className={mode==='voice'?'active':''} onClick={()=>changeMode('voice')}>Voice call</button><button role="tab" aria-selected={mode==='chat'} className={mode==='chat'?'active':''} onClick={()=>changeMode('chat')}>Chat</button></div></div><button className="finish" onClick={()=>{stopCall();onComplete()}} disabled={busy || !session.turns.some(t=>t.role==='user')}>Finish & assess</button></header>
    <div className="roleplay-layout"><aside className="brief"><p className="eyebrow">YOUR BRIEF</p><h2>{session.situation}</h2><p className="label">Success criteria</p><ul>{session.objectives.map(x=><li key={x}>✓ <span>{x}</span></li>)}</ul><div className="difficulty-badge">{session.difficulty} scenario</div><button className={`camera-toggle ${camera?'on':''}`} onClick={toggleCamera}><Icon name="camera"/>{camera?'Stop posture check':'Enable posture check'}</button>{camera && <div className="camera-box"><video ref={video} autoPlay muted playsInline/>{posture && <span>Alignment {Math.round(Object.values(posture).reduce((a,b)=>a+b,0)/4)}%</span>}</div>}<small className="privacy">Camera is optional. Frames stay in your browser; only four alignment scores are saved.</small></aside>
      <section className={`conversation ${mode==='voice'?'voice-mode':''}`}>{mode==='voice'?<div className="call-stage">{error&&<div className="error call-error">{error}</div>}<div className={`call-avatar ${callActive?'active':''} ${recording?'listening':''} ${voiceState==='speaking'||voiceState==='streaming'?'speaking':''}`} style={{'--mic-level':`${Math.max(8,micLevel)}%`}}><span>光</span><i/><i/></div><p className="call-person">{session.counterpart}</p><h2>{callStatus}</h2><p className="call-device">{callActive?micDevice:'Your microphone connects only after you start the call.'}</p>{latestReply&&callActive&&<div className="call-caption"><small>Live caption</small><p>{latestReply.text}</p></div>}{micOptions.length>0&&!callActive&&<label className="call-mic-picker"><span>Microphone</span><select value={selectedMic} onChange={e=>{setSelectedMic(e.target.value);localStorage.setItem('hikari-mic-id',e.target.value)}}>{micOptions.map((item,index)=><option value={item.deviceId} key={item.deviceId}>{item.label||`Microphone ${index+1}`}</option>)}</select></label>}<div className="call-controls">{callActive?<>{!recording&&!busy&&(micState==='error'||voiceState==='failed'||voiceState==='blocked')&&<button onClick={()=>beginListening.current?.()}>Listen again</button>}<button className={muted?'muted':''} onClick={toggleMute} aria-label={muted?'Unmute microphone':'Mute microphone'}>{muted?'Unmute':'Mute'}</button><button className="end-call" onClick={stopCall}>End call</button></>:<button className="start-call" onClick={startCall}>Start voice call</button>}</div></div>:<><div className="messages">{!session.turns.length && <div className="opening"><span>光</span><h2>Ready when you are</h2><p>Type a message or use the microphone for one voice message.</p></div>}{session.turns.map((turn,i)=><div className={`turn ${turn.role}`} key={i}><small>{turn.role==='user'?'You':session.counterpart}</small><p>{turn.text}</p>{turn.sources?.length>0&&<em>Grounded in {turn.sources.map(x=>x.name).join(', ')}</em>}{turn.role==='assistant'&&turn.audioChunks?.length>0&&<button className="replay-voice" onClick={()=>replay(turn.audioChunks)}>▶ Play response</button>}</div>)}{busy&&<div className="turn assistant typing"><i/><i/><i/></div>}<div ref={chatEnd}/></div>
        <div className="composer">{error&&<div className="error">{error}</div>}{recording&&<div className="mic-live"><span className="mic-device">{micDevice}</span><div className="mic-meter"><i style={{width:`${micLevel}%`}}/></div><b>{micState}</b><small>Stops automatically after 1.2s of silence</small></div>}{micOptions.length>0&&!recording&&<label className="mic-picker"><span>Input</span><select value={selectedMic} onChange={e=>{setSelectedMic(e.target.value);localStorage.setItem('hikari-mic-id',e.target.value)}}>{micOptions.map((item,index)=><option value={item.deviceId} key={item.deviceId}>{item.label||`Microphone ${index+1}`}</option>)}</select></label>}<textarea value={text} onChange={e=>setText(e.target.value)} placeholder="Speak or type your response…" onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}}/><div><button className={`mic ${recording?'recording':''}`} onClick={toggleMic} disabled={busy}>{recording?'■ Stop':'● Speak'}</button><span>{recording?'Speak now — your response will submit automatically':'Click Speak, then begin talking'}</span><button className="send" onClick={()=>send()} disabled={busy||!text.trim()}><Icon name="send"/></button></div></div>
        {voiceState!=='idle'&&<div className={`voice-status ${voiceState}`}><span/>{voiceState==='generating'?'Preparing voice…':voiceState==='speaking'||voiceState==='streaming'?'Speaking now…':voiceState==='failed'||voiceState==='blocked'?'Voice unavailable — use Play response after allowing sound':'Voice response ready'}</div>}
      </>}</section></div>
  </main>
}

function Assessment({ session, assessment, onDone }) {
  return <main className="assessment"><div className="assessment-hero"><p className="eyebrow">SESSION COMPLETE</p><h1>{session.title}</h1><ScoreRing score={assessment.overall} size={150}/><p>{assessment.feedback}</p></div><div className="assessment-grid"><section><p className="eyebrow">RUBRIC BREAKDOWN</p>{Object.entries(assessment.scores).map(([k,v])=><div className="metric" key={k}><span>{k.replaceAll('_',' ')}</span><div><i style={{width:`${v}%`}}/></div><strong>{Math.round(v)}</strong></div>)}</section><section><p className="eyebrow">COACHING NOTES</p><h3>What worked</h3>{assessment.strengths.map(x=><p className="note good" key={x}>✓ {x}</p>)}<h3>Improve next</h3>{assessment.improvements.map(x=><p className="note improve" key={x}>↗ {x}</p>)}</section></div><section className="evidence"><p className="eyebrow">EVIDENCE</p>{assessment.evidence.map(x=><p key={x}>{x}</p>)}</section><button className="primary done" onClick={onDone}>Back to overview</button></main>
}

function History({ rows }) { return <main className="page"><header className="page-head compact"><div><p className="eyebrow">YOUR RECORD</p><h1>Training history</h1><p>Review completed and in-progress practice sessions.</p></div></header><div className="history-table"><div className="table-head"><span>Scenario</span><span>Difficulty</span><span>Status</span><span>Score</span></div>{rows.length?rows.map(r=><div className="table-row" key={r.id}><span><strong>{r.title}</strong><small>{r.skill_id.replaceAll('-',' ')}</small></span><span>{r.difficulty}</span><span><i className={r.status}/>{r.status}</span><b>{r.overall?Math.round(r.overall):'—'}</b></div>):<div className="empty-panel">No sessions yet. Start a roleplay to build your history.</div>}</div></main> }

function Documents({ docs, reload }) {
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('')
  const upload=async e=>{const file=e.target.files[0];if(!file)return;setBusy(true);setMessage('');try{const form=new FormData();form.append('file',file);form.append('user_id','demo');await api('/documents',{method:'POST',body:form});setMessage(`${file.name} is ready for grounded roleplays.`);reload()}catch(err){setMessage(err.message)}finally{setBusy(false);e.target.value=''}}
  const remove=async id=>{await api(`/documents/${id}`,{method:'DELETE'});reload()}
  return <main className="page"><header className="page-head compact"><div><p className="eyebrow">ORGANIZATION KNOWLEDGE</p><h1>Ground training in real policy</h1><p>Upload authorised material. Hikari retrieves relevant passages during roleplay and identifies the source.</p></div><label className="primary upload">{busy?'Processing…':'Upload document'}<input type="file" accept=".pdf,.docx,.txt,.md" onChange={upload} disabled={busy}/></label></header>{message&&<div className="notice">{message}</div>}<div className="document-info"><div><strong>Supported</strong><span>PDF, DOCX, TXT, MD · maximum 10 MB</span></div><div><strong>Private by design</strong><span>Stored only in this local prototype database</span></div><div><strong>Traceable</strong><span>Source names appear beside grounded replies</span></div></div><div className="doc-list"><div className="table-head"><span>Document</span><span>Status</span><span>Chunks</span><span></span></div>{docs.length?docs.map(d=><div className="table-row" key={d.id}><span><strong>{d.name}</strong><small>{new Date(d.created_at).toLocaleDateString()}</small></span><span><i className="completed"/>ready</span><span>{d.chunks}</span><button className="delete" onClick={()=>remove(d.id)}>Remove</button></div>):<div className="empty-panel">No documents uploaded. General scenarios still work without them.</div>}</div></main>
}

const fmt = (value, unit='ms') => value == null ? '—' : `${Math.round(value)}${unit}`
function Sparkline({ values, max=100 }) {
  if (!values.length) return <div className="spark-empty">Collecting samples…</div>
  const points=values.map((v,i)=>`${i/(Math.max(values.length-1,1))*100},${38-Math.min(v/max,1)*34}`).join(' ')
  return <svg className="spark" viewBox="0 0 100 40" preserveAspectRatio="none"><polyline points={points}/></svg>
}

function Monitor(){
  const [snapshot,setSnapshot]=useState(null),[samples,setSamples]=useState([]),[clientMs,setClientMs]=useState(null),[paused,setPaused]=useState(false),[error,setError]=useState('')
  const refresh=useCallback(async()=>{if(paused)return;const started=performance.now();try{const next=await api('/monitor/snapshot');setClientMs(performance.now()-started);setSnapshot(next);setSamples(old=>[...old.slice(-29),{cpu:next.system.cpu_percent,ram:next.system.ram_percent,gpu:next.system.gpu?.utilization_percent||0,at:next.timestamp}]);setError('')}catch(e){setError(e.message)}},[paused])
  useEffect(()=>{refresh();const timer=setInterval(refresh,2000);return()=>clearInterval(timer)},[refresh])
  const reset=async()=>{await api('/monitor/reset',{method:'POST'});setSamples([]);refresh()}
  if(!snapshot)return <Loading/>
  const s=snapshot.system,g=s.gpu,last=snapshot.pipeline.latest_roleplay
  const micEvents=snapshot.recent.filter(event=>event.category==='microphone')
  const latestMic=micEvents[0],deviceEvent=micEvents.find(event=>event.device),transcriptEvent=micEvents.find(event=>event.transcript)
  const micActive=latestMic&&['connected','listening','level','speech_detected'].includes(latestMic.name)&&(Date.now()-new Date(latestMic.timestamp).getTime()<5000)
  const status=(value,good,warn)=>value==null?'neutral':value<=good?'good':value<=warn?'warn':'bad'
  const cards=[
    ['Browser round trip',clientMs,'ms',250,700,'UI → API → UI'],
    ['HTTP p95',snapshot.http.p95_ms,'ms',500,1500,`${snapshot.http.requests} measured requests`],
    ['Process memory',s.process_rss_mb,' MB',3500,7000,'Backend working set'],
    ['System RAM',s.ram_percent,'%',75,90,`${s.ram_used_gb} of ${s.ram_total_gb} GB`],
    ['GPU load',g?.utilization_percent,'%',75,92,g?.name||'NVML unavailable'],
    ['VRAM',g?.memory_percent,'%',75,90,g?`${g.memory_used_mb} of ${g.memory_total_mb} MB`:'NVML unavailable'],
  ]
  return <main className="page monitor-page"><header className="page-head compact"><div><p className="eyebrow">TESTING CONSOLE</p><h1>Runtime monitor</h1><p>Live measurements from this local run, including bounded microphone diagnostics and recent transcription.</p></div><div className="monitor-actions"><button onClick={()=>setPaused(x=>!x)}>{paused?'Resume':'Pause'}</button><button onClick={reset}>Reset window</button></div></header>{error&&<div className="error">{error}</div>}
    <div className="monitor-status"><span className={`live-dot ${Object.values(snapshot.components).every(x=>x.ready)?'ready':''}`}/><strong>{Object.values(snapshot.components).every(x=>x.ready)?'All systems ready':'Running with unavailable components'}</strong><span>Uptime {Math.floor(snapshot.uptime_seconds/60)}m {Math.round(snapshot.uptime_seconds%60)}s</span><span>Refresh 2s</span></div>
    <section className="metric-cards">{cards.map(([label,value,unit,good,warn,detail])=><article key={label} className={status(value,good,warn)}><p>{label}</p><strong>{fmt(value,unit)}</strong><small>{detail}</small></article>)}</section>
    <section className="monitor-grid"><article className="monitor-panel"><div className="panel-title"><div><p className="eyebrow">RESOURCE TREND</p><h2>Last 60 seconds</h2></div><div className="legend"><span className="cpu">CPU</span><span className="ram">RAM</span><span className="gpu">GPU</span></div></div><div className="trend"><Sparkline values={samples.map(x=>x.cpu)}/><Sparkline values={samples.map(x=>x.ram)}/><Sparkline values={samples.map(x=>x.gpu)}/></div><div className="trend-values"><span>CPU <b>{fmt(s.cpu_percent,'%')}</b></span><span>RAM <b>{fmt(s.ram_percent,'%')}</b></span><span>GPU <b>{fmt(g?.utilization_percent,'%')}</b></span><span>GPU temp <b>{fmt(g?.temperature_c,'°C')}</b></span></div></article>
      <article className="monitor-panel"><p className="eyebrow">COMPONENTS</p><h2>Model readiness</h2><div className="component-list">{Object.entries(snapshot.components).map(([name,item])=><div key={name}><span className={`component-dot ${item.ready?'ready':'offline'}`}/><strong>{name.toUpperCase()}</strong><span>{item.ready?'Ready':item.error?'Failed':'Not loaded'}</span><b>{item.load_ms?fmt(item.load_ms):'—'}</b></div>)}</div></article></section>
    <section className="monitor-panel pipeline-panel"><div className="panel-title"><div><p className="eyebrow">LATEST VOICE TURN</p><h2>Latency breakdown</h2></div><span className="mode-pill">{last?.mode||'waiting'}</span></div>{last?<><div className="stage-grid">{[['Retrieval',last.retrieval_ms],['LLM first token',last.llm_ttft_ms],['Text visible',last.response_ready_ms],['First audio',last.first_audio_total_ms],['Voice complete',last.full_pipeline_ms]].map(([name,value])=><div key={name}><span>{name}</span><strong>{fmt(value)}</strong><i style={{width:`${Math.min((value||0)/Math.max(last.full_pipeline_ms||last.response_ready_ms,1)*100,100)}%`}}/></div>)}</div><div className="pipeline-foot"><span>ChatTTS first chunk <b>{fmt(last.tts_first_audio_ms)}</b> · full synthesis <b>{fmt(last.tts_ms)}</b> · real-time factor <b>{last.tts_realtime_factor??'—'}</b></span><span>Generated audio <b>{last.audio_seconds??'—'}s</b> in <b>{last.tts_chunks??'—'}</b> chunks</span></div></>:<div className="empty-panel">Complete a roleplay turn to populate stage timings.</div>}</section>
      <section className="monitor-panel mic-panel"><div className="panel-title"><div><p className="eyebrow">MICROPHONE</p><h2>Input diagnostics</h2></div><span className={`mic-status ${micActive?'active':''}`}>{micActive?'Live input':'Not recording'}</span></div><div className="mic-diagnostics"><div><small>Selected device</small><strong>{deviceEvent?.device||'No capture recorded'}</strong><span>{deviceEvent?.sample_rate?`${deviceEvent.sample_rate} Hz · ${deviceEvent.channel_count||1} channel${deviceEvent.channel_count===1?'':'s'}`:'Click Speak inside a roleplay to connect.'}</span></div><div><small>Current state</small><strong>{micActive?(latestMic?.state||latestMic?.name):latestMic?.name||'Idle'}</strong><span>{latestMic?.error||'Speech uses an adaptive noise threshold and stops after 1.2 seconds of silence.'}</span></div><div><small>Input level</small><strong>{fmt(latestMic?.level_percent,'%')}</strong><div className="diagnostic-meter"><i style={{width:`${latestMic?.level_percent||0}%`}}/></div><span>Peak {fmt(latestMic?.peak_percent,'%')} · trigger {fmt(latestMic?.threshold_percent,'%')}</span></div></div><div className="transcript-monitor"><small>Latest detected speech</small><p>{transcriptEvent?.transcript||'No transcription yet. Start a roleplay, click Speak, and talk normally.'}</p>{transcriptEvent&&<span>Whisper completed in {fmt(transcriptEvent.duration_ms)} at {new Date(transcriptEvent.timestamp).toLocaleTimeString()}</span>}</div><div className="mic-event-strip">{micEvents.slice(0,8).map((event,i)=><span key={`${event.timestamp}-${i}`} className={event.ok?'':'failed'}><b>{event.name.replaceAll('_',' ')}</b>{event.level_percent!=null&&` · ${Math.round(event.level_percent)}%`}</span>)}</div></section>
    <section className="monitor-panel"><div className="panel-title"><div><p className="eyebrow">RECENT EVENTS</p><h2>Request log</h2></div><span>{snapshot.http.errors} errors · {snapshot.http.error_rate_percent}% rate</span></div><div className="event-table"><div><b>Time</b><b>Category</b><b>Operation</b><b>Duration</b><b>Result</b></div>{snapshot.recent.map((event,i)=><div key={`${event.timestamp}-${i}`}><span>{new Date(event.timestamp).toLocaleTimeString()}</span><span>{event.category}</span><span>{event.name}</span><span>{fmt(event.duration_ms)}</span><span className={event.ok?'event-ok':'event-bad'}>{event.ok?'OK':'Error'}</span></div>)}</div></section>
    <p className="monitor-note">Guide: round trip includes local browser and proxy overhead; HTTP timing is server work; LLM first token measures responsiveness; TTS real-time factor compares synthesis time with generated audio duration. Microphone transcripts and device details stay in this local process, are limited to the recent-event window, and disappear on restart or reset. Treat thresholds as test aids, not production service-level guarantees.</p>
  </main>
}

function Settings({ onChanged }){
  const [state,setState]=useState(null),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState('')
  const load=useCallback(async()=>{try{const next=await api('/tts/engines');setState(next);setSelected(next.active);setMessage('')}catch(e){setMessage(e.message)}},[])
  useEffect(()=>{load()},[load])
  const apply=async()=>{if(!selected||selected===state?.active)return;setBusy(true);setMessage('Loading voice model… Keep this page open.');try{const next=await api('/tts/engine',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({engine:selected})});setState(next);setMessage(`${next.engines.find(item=>item.id===next.active)?.name||next.active} is now active.`);await onChanged()}catch(e){setSelected(state.active);setMessage(e.message)}finally{setBusy(false)}}
  if(!state)return <main className="page settings-page"><header className="page-head compact"><div><p className="eyebrow">PREFERENCES</p><h1>Voice settings</h1></div></header>{message?<div className="error">{message}</div>:<Loading/>}</main>
  return <main className="page settings-page"><header className="page-head compact"><div><p className="eyebrow">PREFERENCES</p><h1>Voice settings</h1><p>Choose the speech engine used for voice calls and spoken chat replies.</p></div></header><section className="settings-panel"><div className="settings-row"><div><h2>Text-to-speech engine</h2><p>ChatTTS remains the default. Other engines load only when selected to keep memory usage controlled.</p></div><div className="engine-select"><select value={selected} onChange={e=>{setSelected(e.target.value);setMessage('')}} disabled={busy} aria-label="Text-to-speech engine">{state.engines.map(engine=><option key={engine.id} value={engine.id}>{engine.name} — {engine.language}{engine.installed?'':' (first-use setup)'}</option>)}</select><button className="primary" onClick={apply} disabled={busy||selected===state.active}>{busy?'Loading…':'Apply voice'}</button></div></div>{message&&<div className={message.includes('active')?'notice':'settings-message'}>{message}</div>}<div className="engine-options">{state.engines.map(engine=><article key={engine.id} className={engine.id===state.active?'active':''}><div><strong>{engine.name}</strong>{engine.id===state.active&&<span>Active</span>}</div><p>{engine.description}</p><small>{engine.language} · {engine.installed?'Model ready':'Model downloads on first selection'}</small></article>)}</div><p className="settings-note">Change engines between calls. Japanese and Arabic engines are language-specific; the Arabic engine also requires the eSpeak NG desktop runtime.</p></section></main>
}

function Loading(){return <div className="loading"><span>光</span><p>Preparing your training space…</p></div>}

export default function App(){
  const [view,setView]=useState('dashboard'),[dashboard,setDashboard]=useState(null),[skills,setSkills]=useState([]),[history,setHistory]=useState([]),[docs,setDocs]=useState([]),[health,setHealth]=useState({status:'loading'}),[session,setSession]=useState(null),[assessment,setAssessment]=useState(null),[error,setError]=useState('')
  const load=useCallback(async()=>{try{const [d,s,h,dc,he]=await Promise.all([api('/dashboard'),api('/skills'),api('/sessions'),api('/documents'),api('/health')]);setDashboard(d);setSkills(s);setHistory(h);setDocs(dc);setHealth(he);setError('')}catch(e){setError(e.message)}},[])
  useEffect(()=>{load()},[load])
  const start=async(skillId,difficulty='intermediate')=>{try{setError('');const s=await api('/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:'demo',skill_id:skillId,difficulty})});setSession(s);setAssessment(null)}catch(e){setError(e.message)}}
  const complete=async()=>{try{const a=await api(`/sessions/${session.id}/complete`,{method:'POST'});setAssessment(a);await load()}catch(e){setError(e.message)}}
  if(session&&assessment)return <Assessment session={session} assessment={assessment} onDone={()=>{setSession(null);setAssessment(null);setView('dashboard')}}/>
  if(session)return <Roleplay session={session} setSession={setSession} onComplete={complete}/>
  return <div className="app-shell"><Sidebar view={view} setView={setView} health={health}/><div className="content">{error&&<div className="global-error">Backend unavailable: {error}. Start the API server and refresh.</div>}{view==='dashboard'&&<Dashboard data={dashboard} onStart={start} setView={setView}/>} {view==='practice'&&<Practice skills={skills} onStart={start}/>} {view==='history'&&<History rows={history}/>} {view==='docs'&&<Documents docs={docs} reload={load}/>} {view==='monitor'&&<Monitor/>} {view==='settings'&&<Settings onChanged={load}/>}</div></div>
}
