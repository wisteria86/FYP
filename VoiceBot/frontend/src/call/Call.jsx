import { finalRecognitionForm, recognitionProvenance, reviewedRecognition } from '../recognitionDecision.mjs'
import { useCallback, useEffect, useRef, useState } from 'react'
import ConversationCoach from '../ConversationCoach'
import { PlaybackGeneration } from '../conversationPlayback.mjs'
import { startBargeIn } from '../bargeIn.mjs'
import { loadSessionAudio, saveSessionAudio, sessionAudioMode } from '../sessionAudio.mjs'
import { createInputLevel } from '../inputLevel.mjs'
import { CaptureClock } from '../captureClock.mjs'
import { IncrementalTranscriber } from '../incrementalTranscriber.mjs'
import { StreamingTranscriber } from '../streamingTranscriber.mjs'
import { listMicrophones, microphoneConstraints } from '../micDevices.mjs'
import { createCleanCapture } from '../noiseReduction.mjs'
import { turnDetection, captureLimitReason } from '../turnEnding.mjs'
import { startSilero } from '../sileroVad.mjs'
import { monitorMicrophone } from '../micMonitor.mjs'
import { SourceEvidence } from '../call/SourceEvidence'
import { API, Icon, api } from '../ui/core'
import { Portrait } from './Portrait'
import { Backdrop } from './Backdrop'
import { useFeedback } from '../ui/feedback'

export function Roleplay({ session, setSession, onComplete, onCancel, health, onOpenSettings, userSettings }) {
  const [runtime,setRuntime]=useState(session.runtime||null),[addressed,setAddressed]=useState('')
  const playbackGeneration=useRef(new PlaybackGeneration()),bargeCallbacks=useRef({}),bargeMonitor=useRef(null)
  const [mode, setMode] = useState('voice')
  const [callActive, setCallActive] = useState(false)
  const [muted, setMuted] = useState(false)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [recording, setRecording] = useState(false)
  const [capturePaused,setCapturePaused]=useState(false)
  const [voiceDraft,setVoiceDraft]=useState(null)
  const [recognitionReview,setRecognitionReview]=useState(null)
  const voiceDraftRef=useRef(null),reviewSending=useRef(false)
  const [micState, setMicState] = useState('idle')
  const [micLevel, setMicLevel] = useState(0)
  const [micDevice, setMicDevice] = useState('No microphone selected')
  const [voiceState, setVoiceState] = useState('idle')
  const [activeSpeaker, setActiveSpeaker] = useState(null)
  const [sessionProgress, setSessionProgress] = useState(null)
  const [audioPanelOpen,setAudioPanelOpen]=useState(false)
  const audioPanelRef=useRef(null),audioButtonRef=useRef(null)
  const [micOptions, setMicOptions] = useState([])
  const [sessionAudio,setSessionAudio]=useState(()=>loadSessionAudio(localStorage))
  const automaticTurnEnd=sessionAudio.inputMode==='auto'
  const audioMode=sessionAudioMode(sessionAudio)
  const micLevelGraph=useRef(null)
  const micDenoiser=useRef(null)
  const micVad=useRef(null)
  const [micListError,setMicListError]=useState('')
  const [micRefreshing,setMicRefreshing]=useState(false)
  const [selectedMic, setSelectedMic] = useState(()=>loadSessionAudio(localStorage).deviceId)
  const [camera, setCamera] = useState(false)
  const [captions, setCaptions] = useState(userSettings?.captions_enabled??true)
  const [elapsed, setElapsed] = useState(0)
  const [posture, setPosture] = useState(null)
  const [postureReason,setPostureReason]=useState('Enable your camera and keep your head, shoulders and hips visible.')
  const recorder = useRef(null), chunks = useRef([]), started = useRef(0), video = useRef(null), media = useRef(null), chatEnd = useRef(null)
  const playbackContext = useRef(null), playbackTail = useRef(0)
  const playbackSources = useRef(new Set())
  const voiceRequest = useRef(null)
  const sending = useRef(false)
  const incrementalCapture = useRef(null)
  const streamingCapture = useRef(null)
  const micStarting = useRef(false)
  const lastCapture = useRef(null)
  const latencyTrial = useRef(null)
  const callActiveRef = useRef(false), mutedRef = useRef(false), modeRef = useRef('voice'), beginListening = useRef(null), discardCapture = useRef(false)
  const micStream = useRef(null), micContext = useRef(null), micFrame = useRef(null), speechSeen = useRef(false), lastSpeech = useRef(0), peakLevel = useRef(0), lastLevelReport = useRef(0), noiseFloor = useRef(.003)
  useEffect(() => { chatEnd.current?.scrollIntoView({behavior:'smooth'}) }, [session.turns, busy])
  useEffect(()=>{const update=()=>setElapsed(Math.max(0,Math.floor((Date.now()-Date.parse(session.created_at))/1000)));update();const timer=setInterval(update,1000);return()=>clearInterval(timer)},[session.created_at])
  useEffect(() => () => { if(voiceDraftRef.current)URL.revokeObjectURL(voiceDraftRef.current.url);streamingCapture.current?.cancel();incrementalCapture.current?.cancel();media.current?.getTracks().forEach(t => t.stop()); micStream.current?.getTracks().forEach(t => t.stop()); micFrame.current?.(); micVad.current?.stop();micDenoiser.current?.destroy();micLevelGraph.current?.destroy();micContext.current?.close(); playbackContext.current?.close() }, [])
  useEffect(()=>{
    if(!audioPanelOpen)return
    const previous=document.activeElement
    const panel=audioPanelRef.current
    panel?.querySelector('button')?.focus()
    const handleKey=event=>{
      if(event.key==='Escape'){event.preventDefault();setAudioPanelOpen(false)}
      if(event.key==='Tab'){
        const controls=[...panel.querySelectorAll('button:not(:disabled),select:not(:disabled),input:not(:disabled)')]
        const first=controls[0],last=controls.at(-1)
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
      }
    }
    document.addEventListener('keydown',handleKey)
    return()=>{document.removeEventListener('keydown',handleKey);if(previous?.isConnected)previous.focus()}
  },[audioPanelOpen])
  useEffect(()=>{
    const refresh=()=>{if(!callActive){const value=loadSessionAudio(localStorage);setSessionAudio(value);setSelectedMic(value.deviceId)}}
    refresh();window.addEventListener('hikari-session-audio-changed',refresh)
    return()=>window.removeEventListener('hikari-session-audio-changed',refresh)
  },[callActive])
  const refreshMicrophones=useCallback(async(requestAccess=false)=>{
    setMicRefreshing(true)
    try{
      const devices=await listMicrophones(navigator.mediaDevices,requestAccess)
      setMicOptions(devices);setMicListError('')
    }catch(error){setMicListError(error.message)}finally{setMicRefreshing(false)}
  },[])
  useEffect(()=>{
    const refresh=()=>{refreshMicrophones(false)}
    refresh()
    navigator.mediaDevices?.addEventListener?.('devicechange',refresh)
    window.addEventListener('focus',refresh)
    return()=>{navigator.mediaDevices?.removeEventListener?.('devicechange',refresh);window.removeEventListener('focus',refresh)}
  },[refreshMicrophones])
  useEffect(() => {
    if (!camera||!session.posture_enabled) return undefined
    const worker=new Worker(new URL('../pose.worker.js',import.meta.url),{type:'module'})
    let inFlight=false,disposed=false
    worker.onmessage=async({data})=>{
      inFlight=false
      if(disposed)return
      if(data.error){setError(`Posture analysis unavailable: ${data.error}. Voice training can continue.`);return}
      if(!data.landmarks?.length){setPosture(null);setPostureReason('No body detected. Keep your head, shoulders and hips visible.');return}
      try{
        const out=await api(`/sessions/${session.id}/posture-landmarks`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({landmarks:data.landmarks})})
        if(!disposed){setPosture(out.available?out.scores:null);setPostureReason(out.reason||'Visible-body presentation indicators, not medical advice.')}
      }catch(error){if(!disposed)setError(`Posture analysis unavailable: ${error.message}. Voice training can continue.`)}
    }
    const analyse = async () => {
      if (!video.current?.videoWidth||inFlight||disposed) return
      try {
        inFlight=true
        const bitmap=await createImageBitmap(video.current)
        if(disposed){bitmap.close();return}
        worker.postMessage({bitmap,timestamp:performance.now()},[bitmap])
      } catch {inFlight=false}
    }
    analyse()
    const timer=setInterval(analyse,5000)
    return ()=>{disposed=true;clearInterval(timer);worker.terminate()}
  }, [camera, session.id,session.posture_enabled])
  const refreshRuntime=async()=>{
    const next=await api(`/sessions/${session.id}`)
    setRuntime(next.runtime||null);setSessionProgress(next.runtime?.progress||null)
    if(!sending.current)setSession(next)
    return next.runtime
  }
  const runtimeAction=async(action,data={})=>{
    if(['correct','skip'].includes(action)){stopCall();sending.current=false;setBusy(false)}
    const result=await api(`/sessions/${session.id}/actions`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,data,request_id:crypto.randomUUID()})})
    setRuntime(result.runtime);setSessionProgress(result.runtime?.progress||null)
    if(action==='correct')await refreshRuntime()
    return result
  }
  const {toast}=useFeedback()
  // "Take that back": undo the learner's last turn and the reply to it, then say it differently.
  const canTakeBack=!!runtime&&session.turns.some(turn=>turn.role==='user')&&!busy&&!runtime?.generation&&!recording
  const takeBack=async()=>{
    try{
      if(['speaking','streaming'].includes(voiceState))await interrupt(false)
      const result=await api(`/sessions/${session.id}/rewind`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
      setRuntime(result.runtime);setSessionProgress(result.runtime?.progress||null);setSession(result.session);setError('')
      toast('Taken back. Say it another way.',{tone:'success'})
    }catch(error){setError(error.message)}
  }
  const interrupt=async(resume=true)=>{
    playbackGeneration.current.cancel()
    voiceRequest.current?.abort()
    for(const source of playbackSources.current){try{source.stop()}catch{}}
    playbackSources.current.clear();playbackTail.current=0
    setVoiceState('ready');setActiveSpeaker(null)
    if(runtime)await runtimeAction('interrupt')
    sending.current=false;setBusy(false)
    if(resume&&callActiveRef.current&&!mutedRef.current)beginListening.current?.()
  }
  bargeCallbacks.current={isPlaying:()=>callActiveRef.current&&!mutedRef.current&&['speaking','streaming'].includes(voiceState),
    onInterrupt:()=>interrupt(false),onUtterance:async(blob,duration)=>{
      try{setMicState('transcribing');const form=new FormData();form.append('file',blob,'interruption.webm');form.append('language','English');form.append('duration_ms',String(duration*1000));const out=await api('/transcribe',{method:'POST',body:form});if(out.text&&!out.needs_retry)await send(out.text,duration,{source:'speech',unreliable:false});else setError('Please repeat or type your interruption; recognition was uncertain.')}catch(e){setError(e.message)}
    }}
  useEffect(()=>{
    if(!session.runtime)return
    const events=new EventSource(`${API}/sessions/${session.id}/events`)
    events.onmessage=event=>{const item=JSON.parse(event.data);if(['evaluation','coach','pause','resume','correct','offer','accept','withdraw','consistency_repair','provider_status'].includes(item.kind))refreshRuntime().catch(()=>{})}
    return()=>events.close()
  },[session.id])
  useEffect(()=>{
    if(!callActive||!session.runtime)return
    let disposed=false
    startBargeIn({constraints:microphoneConstraints(selectedMic,{noiseSuppression:true}),isPlaying:()=>bargeCallbacks.current.isPlaying(),onInterrupt:()=>bargeCallbacks.current.onInterrupt(),onUtterance:(...args)=>bargeCallbacks.current.onUtterance(...args),onUnavailable:message=>setError(message)})
      .then(monitor=>{if(disposed)monitor.stop();else bargeMonitor.current=monitor}).catch(()=>setError('Automatic interruption is unavailable. Use the Interrupt button.'))
    return()=>{disposed=true;bargeMonitor.current?.stop();bargeMonitor.current=null}
  },[callActive,session.id])
  const voiceAnalyser=useRef(null),sceneRef=useRef(null)
  const voiceOutput=context=>{
    if(!voiceAnalyser.current||voiceAnalyser.current.context!==context){
      const analyser=context.createAnalyser();analyser.fftSize=512;analyser.smoothingTimeConstant=.55;analyser.connect(context.destination);voiceAnalyser.current=analyser
    }
    return voiceAnalyser.current
  }
  // While a character speaks, write the voice loudness to --voice-level (no re-render per frame).
  useEffect(()=>{
    const root=sceneRef.current,analyser=voiceAnalyser.current
    if(!root)return
    if(!analyser||!['speaking','streaming'].includes(voiceState)){root.classList.remove('voice-driven');root.style.setProperty('--voice-level','0');return}
    root.classList.add('voice-driven')
    const samples=new Uint8Array(analyser.fftSize);let frame
    const tick=()=>{analyser.getByteTimeDomainData(samples);let sum=0;for(const value of samples){const centred=(value-128)/128;sum+=centred*centred}
      root.style.setProperty('--voice-level',Math.min(1,Math.sqrt(sum/samples.length)*4.2).toFixed(3));frame=requestAnimationFrame(tick)}
    frame=requestAnimationFrame(tick)
    return()=>{cancelAnimationFrame(frame);root.style.setProperty('--voice-level','0')}
  },[voiceState])
  const ensureAudioReady = async () => {
    const AudioContext=window.AudioContext||window.webkitAudioContext
    if(!AudioContext)throw new Error('This browser does not support streamed audio playback.')
    if(!playbackContext.current)playbackContext.current=new AudioContext()
    if(playbackContext.current.state==='suspended')await playbackContext.current.resume()
    return playbackContext.current
  }
  const playChunk = async b64 => {
    const generation=playbackGeneration.current.capture()
    const receivedAt=performance.now()
    const context=await ensureAudioReady()
    const readyAt=performance.now()
    const bytes=Uint8Array.from(atob(b64),character=>character.charCodeAt(0))
    const decodeStarted=performance.now()
    const buffer=await context.decodeAudioData(bytes.buffer.slice(0))
    if(!playbackGeneration.current.current(generation))return
    const decodedAt=performance.now()
    const source=context.createBufferSource();source.buffer=buffer;source.connect(voiceOutput(context))
    playbackSources.current.add(source)
    source.onended=()=>playbackSources.current.delete(source)
    const lead=.025
    const at=Math.max(context.currentTime+lead,playbackTail.current);source.start(at);playbackTail.current=at+buffer.duration
    if(latencyTrial.current&&!latencyTrial.current.reported){
      const trial=latencyTrial.current
      trial.reported=true
      const outputLatency=(context.outputLatency||context.baseLatency||0)*1000
      const audibleAt=performance.now()+(at-context.currentTime)*1000+outputLatency
      console.info('[Hikari playback latency]',{response_to_audio_received_ms:Math.round(receivedAt-trial.responseStart),context_ready_ms:Math.round(readyAt-receivedAt),base64_ms:Math.round(decodeStarted-readyAt),decode_ms:Math.round(decodedAt-decodeStarted),schedule_wait_ms:Math.round((at-context.currentTime)*1000),output_latency_ms:Math.round(outputLatency)})
      console.info('[Hikari latency]',{endpointing_ms:Math.round(trial.stopped-trial.speechEnd),transcription_ms:Math.round(trial.transcriptionMs),response_to_playback_ms:Math.round(audibleAt-trial.responseStart),total_ms:Math.round(audibleAt-trial.speechEnd),transcription_path:trial.transcriptionPath})
      reportMic({event:'playback_started',state:'session',transcription_path:trial.transcriptionPath,duration_ms:audibleAt-trial.speechEnd,engine:trial.engine,endpointing_ms:trial.stopped-trial.speechEnd,transcription_wall_ms:trial.transcriptionMs,response_to_playback_ms:audibleAt-trial.responseStart,audio_output_latency_ms:outputLatency})
    }
    return playbackTail.current
  }
  const waitForPlayback = async () => {
    const context=playbackContext.current
    if(!context)return
    const remaining=Math.max(0,playbackTail.current-context.currentTime)*1000
    if(remaining)await new Promise(resolve=>setTimeout(resolve,remaining+80))
  }
  const replay = async audioChunks => {
    const generation=playbackGeneration.current.capture()
    try{playbackTail.current=0;setVoiceState('replaying');for(const chunk of audioChunks){if(!playbackGeneration.current.current(generation))return;await playChunk(chunk)}await waitForPlayback();if(playbackGeneration.current.current(generation))setVoiceState('ready')}
    catch(e){setVoiceState('blocked');setError(`Audio playback failed: ${e.message}. Allow sound for localhost, then use Play response.`)}
  }
  const streamVoice = async (reply,correlationId,resumeListening=true,speakerName=null) => {
    const generation=playbackGeneration.current.capture()
    const controller=new AbortController();voiceRequest.current=controller
    playbackTail.current=0
    setActiveSpeaker(speakerName||session.counterpart)
    setVoiceState('generating')
    const response=await fetch(`${API}/tts/stream`,{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({text:reply,correlation_id:correlationId})})
    if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.detail||'Voice engine is unavailable.')}
    if(!response.body)throw new Error('Streaming audio is not supported by this browser.')
    const reader=response.body.getReader(),decoder=new TextDecoder();let pending='',received=0
    while(true){
      const {value,done}=await reader.read();pending+=decoder.decode(value||new Uint8Array(),{stream:!done})
      const lines=pending.split('\n');pending=lines.pop()||''
      for(const line of lines){
        if(!line.trim())continue
        if(!playbackGeneration.current.current(generation))return
        const event=JSON.parse(line)
        if(event.tts_timing)console.info('[Hikari TTS latency]',event.tts_timing)
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
    if(!received)throw new Error('Voice engine returned no playable audio.')
    await waitForPlayback()
    if(!playbackGeneration.current.current(generation))return
    setVoiceState('ready')
    if(resumeListening)setActiveSpeaker(null)
    if(automaticTurnEnd&&resumeListening&&callActiveRef.current&&modeRef.current==='voice'&&!mutedRef.current){
      setTimeout(()=>{if(callActiveRef.current&&!mutedRef.current)beginListening.current?.()},180)
    }
  }
  const reportMic = payload => api('/monitor/microphone',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).catch(()=>{})
  const send = async (value = text, duration = 0, recognition = {}, retryLastTurn = false) => {
    if (!value.trim() || sending.current || runtime?.paused) return
    if(recognitionReview&&!recognition.source&&!retryLastTurn)recognition=reviewedRecognition(recognitionReview)
    setRecognitionReview(null)
    sending.current=true
    const generation=playbackGeneration.current.capture()
    const requestId=crypto.randomUUID()
    voiceRequest.current=new AbortController()
    ensureAudioReady().catch(()=>{})
    setBusy(true); setError(''); setText('')
    if(!retryLastTurn)setSession(s => ({...s, turns:[...s.turns,{role:'user',text:value,created_at:new Date().toISOString()}]}))
    try {
      let result, streamed=false
      const receivedAudio={}
      if(modeRef.current==='voice'){
        const response=await fetch(`${API}/sessions/${session.id}/voice-stream`,{method:'POST',signal:voiceRequest.current.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({text:value,duration_seconds:duration,synthesize_audio:false,request_id:requestId,addressed_participant_ids:addressed?[addressed]:[],recognition,retry_last_turn:retryLastTurn})})
        if(!response.ok)throw new Error('Voice response could not start.')
        const reader=response.body.getReader(), decoder=new TextDecoder();let pending=''
        playbackTail.current=0;setVoiceState('generating')
        while(true){
          const {value:bytes,done}=await reader.read();pending+=decoder.decode(bytes||new Uint8Array(),{stream:!done})
          const lines=pending.split('\n');pending=lines.pop()||''
          for(const line of lines){
            if(!line.trim())continue
            if(!playbackGeneration.current.current(generation))return
            const event=JSON.parse(line)
        if(event.tts_timing)console.info('[Hikari TTS latency]',event.tts_timing)
            if(event.type==='error')throw new Error(event.message)
            if(event.type==='speech_error'){setError(event.message);streamed=true}
            if(event.type==='speech_text')setSession(s=>{
              const existing=s.turns.find(turn=>turn.provisional&&(event.utterance_id?turn.utterance_id===event.utterance_id:turn.speaker_name===event.speaker))
              return {...s,turns:existing?s.turns.map(turn=>turn===existing?{...turn,text:`${turn.text} ${event.text}`}:turn):[...s.turns,{role:'assistant',speaker_name:event.speaker,participant_id:event.participant_id,utterance_id:event.utterance_id,text:event.text,provisional:true,created_at:new Date().toISOString()}]}
            })
            if(event.timing)console.info('[Hikari backend latency]',event.timing)
            if(event.kokoro_timing)console.info('[Hikari Kokoro latency]',event.kokoro_timing)
            if(event.type==='audio'){(receivedAudio[event.utterance_id||event.speaker]??=[]).push(event.audio_b64);setActiveSpeaker(event.speaker);setVoiceState('speaking');await playChunk(event.audio_b64);streamed=true}
            if(event.type==='segment_end'){const delay=Math.max(0,(playbackTail.current-(playbackContext.current?.currentTime||0))*1000)+80;playbackGeneration.current.after(delay,()=>api(`/sessions/${session.id}/playback`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({utterance_id:event.utterance_id,segment:event.segment})}).catch(()=>{}))}
            if(event.type==='result')result=event.result
          }
          if(done)break
        }
        if(!result)throw new Error('The voice response ended unexpectedly.')
      }else result=await api(`/sessions/${session.id}/turn`, {method:'POST',signal:voiceRequest.current.signal, headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:value,duration_seconds:duration,synthesize_audio:false,request_id:requestId,addressed_participant_ids:addressed?[addressed]:[],recognition,retry_last_turn:retryLastTurn})})
      if(!playbackGeneration.current.current(generation))return
      if(result.runtime)setRuntime(result.runtime)
      setSessionProgress(result.session_progress||null)
    const responses=(result.responses||[{text:result.text,correlation_id:result.correlation_id,speaker:session.counterpart}]).filter(reply=>reply.text?.trim())
      if(!responses.length){setVoiceState('ready');setActiveSpeaker(null)}
      setSession(s => ({...s, turns:[...s.turns.filter(turn=>!turn.provisional),...responses.map(reply=>({role:'assistant',text:reply.text,speaker_name:reply.speaker,participant_id:reply.participant_id,utterance_id:reply.utterance_id,caption_text:reply.caption_text,sources:result.sources,correlationId:reply.correlation_id,audioChunks:receivedAudio[reply.utterance_id||reply.speaker]||[],created_at:reply.created_at||new Date().toISOString()}))]}))
      for(let index=0;modeRef.current==='voice'&&!streamed&&index<responses.length;index+=1){
        const reply=responses[index]
        await streamVoice(reply.text,reply.correlation_id,index===responses.length-1,reply.speaker)
      }
      if(streamed){
        await waitForPlayback();if(!playbackGeneration.current.current(generation))return;setVoiceState('ready');setActiveSpeaker(null)
        if(automaticTurnEnd&&result.session_progress?.outcome!=='success'&&callActiveRef.current&&!mutedRef.current)setTimeout(()=>{if(callActiveRef.current&&!mutedRef.current&&modeRef.current==='voice')beginListening.current?.()},180)
      }
      if(!session.runtime&&result.session_progress?.outcome==='success'){
        stopCall()
        await onComplete()
      }
    } catch (e) {
      if(e.name==='AbortError')return
      setVoiceState('failed');setError(`${e.message} The conversation is still active.`)
      if(automaticTurnEnd&&callActiveRef.current&&modeRef.current==='voice'&&!mutedRef.current)setTimeout(()=>{if(callActiveRef.current&&!mutedRef.current&&modeRef.current==='voice')beginListening.current?.()},500)
    } finally { if(playbackGeneration.current.current(generation)){sending.current=false;setBusy(false);if(session.runtime)refreshRuntime().catch(()=>{})} }
  }
  const toggleMic = async () => {
    if(micStarting.current||['recording','paused'].includes(recorder.current?.state)||voiceDraftRef.current)return true
    if(!callActiveRef.current||mutedRef.current||modeRef.current!=='voice')return false
    micStarting.current=true
    setRecognitionReview(null)
    try {
      await ensureAudioReady()
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone capture requires localhost or HTTPS.')
      const audioOptions=microphoneConstraints(selectedMic,{noiseSuppression:audioMode.browser})
      let stream=micStream.current
      if(!stream?.getAudioTracks().some(track=>track.readyState==='live')){
        try{stream=await navigator.mediaDevices.getUserMedia({audio:audioOptions})}catch(firstError){if(!selectedMic)throw firstError;localStorage.removeItem('hikari-mic-id');setSelectedMic('');setSessionAudio(saveSessionAudio(localStorage,{...sessionAudio,deviceId:''}));stream=await navigator.mediaDevices.getUserMedia({audio:microphoneConstraints('',{noiseSuppression:audioMode.browser})})}
      }
      micStream.current=stream
      const track=stream.getAudioTracks()[0], settings=track.getSettings(), device=track.label||'Default microphone'
      console.info('[Hikari microphone settings]',{device,...settings})
      const devices=(await navigator.mediaDevices.enumerateDevices()).filter(item=>item.kind==='audioinput')
      setMicOptions(devices);if(!selectedMic&&settings.deviceId){setSelectedMic(settings.deviceId);localStorage.setItem('hikari-mic-id',settings.deviceId)}
      setMicDevice(device); setMicState('listening'); setMicLevel(0); speechSeen.current=false; lastSpeech.current=0; peakLevel.current=0;lastLevelReport.current=0;noiseFloor.current=.0003
      reportMic({event:'connected',device,state:'ready',sample_rate:settings.sampleRate,channel_count:settings.channelCount})
      const AudioContext=window.AudioContext||window.webkitAudioContext
      const context=new AudioContext({sampleRate:48000})
      micContext.current=context
      if(context.state==='suspended')await context.resume()
      const levelGraph=sessionAudio.gainEnabled?createInputLevel(context,stream,sessionAudio.gainDb):null
      micLevelGraph.current=levelGraph
      const leveledStream=levelGraph?.stream||stream
      const capture=audioMode.rnnoise?await createCleanCapture(context,leveledStream):null
      micDenoiser.current=capture
      const source=capture?.source||context.createMediaStreamSource(leveledStream)
      const recordingStream=capture?.stream||leveledStream
      console.info('[Hikari session audio]',{mode:audioMode.id,gain_db:sessionAudio.gainEnabled?sessionAudio.gainDb:0,live_recognition:sessionAudio.liveRecognition})
      console.info('[Hikari noise reduction]',{enabled:!!capture,engine:capture?'RNNoise':audioMode.browser?'browser':'none',sample_rate:context.sampleRate})
      if(!callActiveRef.current||mutedRef.current||modeRef.current!=='voice'){
        capture?.destroy();levelGraph?.destroy();micLevelGraph.current=null;micDenoiser.current=null;stream.getTracks().forEach(track=>track.stop());await context.close();micStream.current=null;micContext.current=null;return false
      }
      const preferredMime=['audio/webm;codecs=opus','audio/webm'].find(type=>MediaRecorder.isTypeSupported?.(type))
      const r = preferredMime?new MediaRecorder(recordingStream,{mimeType:preferredMime}):new MediaRecorder(recordingStream); chunks.current=[]; started.current=performance.now(); recorder.current=r
      const decodeCapture=(blob,signal)=>{
        const form=new FormData();form.append('file',blob,'speech.webm');form.append('language',session.training_language||'English');form.append('context',`${session.title}. ${session.situation}`);form.append('duration_ms',String(performance.now()-started.current));form.append('partial','true');form.append('decoding_method',sessionAudio.decodingMethod)
        return api('/transcribe',{method:'POST',body:form,signal:AbortSignal.any&&AbortSignal.timeout?AbortSignal.any([signal,AbortSignal.timeout(12000)]):signal})
      }
      const incremental=new IncrementalTranscriber(decodeCapture,partial=>{setText(partial);setMicState('transcribing live')})
      incrementalCapture.current=incremental
      let live=null
      if(sessionAudio.liveRecognition&&health?.stt_runtime?.streaming&&(session.training_language||'English')==='English'){
        live=new StreamingTranscriber(session.id,partial=>{setText(partial);setMicState('transcribing live')},sessionAudio.decodingMethod)
        streamingCapture.current=live
        if(!await live.start(context,source)){live=null;streamingCapture.current=null}
      }
      if(!callActiveRef.current||mutedRef.current){live?.cancel();incremental.cancel();source.disconnect();capture?.destroy();levelGraph?.destroy();micLevelGraph.current=null;micDenoiser.current=null;await context.close();return false}
      let lastSnapshot=0
      r.ondataavailable = e => {
        if(!e.data.size)return
        chunks.current.push(e.data)
        const now=performance.now(),paused=now-lastSpeech.current>300
        if(automaticTurnEnd&&!live?.ready&&r.state==='recording'&&speechSeen.current&&(now-lastSnapshot>1500||(paused&&now-lastSnapshot>350))){
          if(incremental.push(new Blob(chunks.current,{type:r.mimeType||'audio/webm'}),now))lastSnapshot=now
        }
      }
      r.onstop = async () => {
        const stoppedAt=performance.now()
        console.info('[Hikari capture endpoint]',{reason:r.hikariStopReason||stopReason,capture_ms:Math.round(stoppedAt-started.current),silence_ms:Math.round(stoppedAt-lastSpeech.current)})
        latencyTrial.current=speechSeen.current?{speechEnd:lastSpeech.current,stopped:stoppedAt,reported:false}:null
        const captureMs=r.captureClock.elapsed(performance.now())
        lastCapture.current=new Blob(chunks.current,{type:r.mimeType||'audio/webm'})
        micFrame.current?.(); micFrame.current=null
        micVad.current?.stop();micVad.current=null
        setRecording(false);setCapturePaused(false)
        if((speechSeen.current||!automaticTurnEnd)&&!discardCapture.current)setBusy(true)
        const transcriptionStarted=performance.now()
        let cleanupStarted=false
        const cleanupCapture=()=>{
          if(cleanupStarted)return
          cleanupStarted=true
          source.disconnect()
          capture?.destroy();levelGraph?.destroy()
          if(micLevelGraph.current===levelGraph)micLevelGraph.current=null
          if(!automaticTurnEnd){stream.getTracks().forEach(track=>track.stop());if(micStream.current===stream)micStream.current=null}
          if(micDenoiser.current===capture)micDenoiser.current=null
          if(micContext.current===context)micContext.current=null
          const cleanupAt=performance.now()
          context.close().then(()=>console.info('[Hikari capture cleanup]',{close_ms:Math.round(performance.now()-cleanupAt)})).catch(()=>{})
        }
        if(!automaticTurnEnd&&!discardCapture.current&&callActiveRef.current&&!mutedRef.current){
          const liveResult=live?await live.finish(cleanupCapture):null
          incremental.cancel();cleanupCapture()
          if(!callActiveRef.current||mutedRef.current||discardCapture.current){setBusy(false);return}
          if(voiceDraftRef.current)URL.revokeObjectURL(voiceDraftRef.current.url)
          const draft={blob:lastCapture.current,url:URL.createObjectURL(lastCapture.current),durationMs:captureMs,liveResult}
          voiceDraftRef.current=draft;setVoiceDraft(draft);setMicLevel(0);setMicState('review');setVoiceState('ready');setBusy(false)
          latencyTrial.current=null
          await sendReviewedVoice()
          return
        }
        let liveResult=null
        if(live){
          // Flush captured PCM before closing its context; overlap cleanup with
          // backend finalization rather than delaying the response request.
          if(speechSeen.current&&!discardCapture.current)liveResult=await live.finish(cleanupCapture)
          else live.cancel()
          if(streamingCapture.current===live)streamingCapture.current=null
        }
        cleanupCapture()
        if(live?.timing)console.info('[Hikari transcription stages]',live.timing)
        console.info('[Hikari recognition outcome]',{live_final_received:!!liveResult,input_audio:liveResult?.input_audio??null,captured_audio_ms:liveResult?.captured_audio_ms??null,text_chars:liveResult?.text?.trim().length??0,needs_retry:liveResult?.needs_retry??null,capture_ms:Math.round(captureMs),recorded_bytes:chunks.current.reduce((total,chunk)=>total+chunk.size,0)})
        if(!callActiveRef.current||mutedRef.current){stream.getTracks().forEach(t=>t.stop());micStream.current=null}
        setRecording(false);setMicLevel(0)
        if(discardCapture.current){incremental.cancel();discardCapture.current=false;setMicState('idle');setBusy(false);return}
        const resumeCapture=()=>setTimeout(()=>{
          if(callActiveRef.current&&!mutedRef.current&&modeRef.current==='voice')beginListening.current?.()
        },350)
        // Quiet capture rotation must not transcribe silence or strand a connected call.
        if(!speechSeen.current){
          incremental.cancel();setMicState('listening')
          const warning=track.muted||peakLevel.current<.05
            ? `No microphone audio is arriving from ${device}. Check the selected device and its hardware mute switch.`
            : `Audio is arriving from ${device}, but speech was too quiet to detect. Check its input volume or choose another microphone.`
          setError(warning);reportMic({event:'error',device,state:'no speech',peak_percent:peakLevel.current,error:warning});resumeCapture();return
        }
        setMicState('transcribing');setBusy(true)
        reportMic({event:'stopped',device,state:'transcribing',duration_ms:captureMs,peak_percent:peakLevel.current})
        try {
          const form=new FormData();form.append('file',new Blob(chunks.current,{type:r.mimeType||'audio/webm'}),'speech.webm');form.append('language',session.training_language||'English');form.append('context',`${session.title}. ${session.situation}`);form.append('duration_ms',String(captureMs));form.append('decoding_method',sessionAudio.decodingMethod)
          const previous=liveResult?.text?liveResult:await incremental.finish(lastSpeech.current)
          const reusable=finalRecognitionForm(form,sessionAudio,session.id,previous)
          if(incremental.controller.signal.aborted){setBusy(false);return}
          const signal=AbortSignal.any&&AbortSignal.timeout?AbortSignal.any([incremental.controller.signal,AbortSignal.timeout(45000)]):incremental.controller.signal
          const out=reusable||await api('/transcribe',{method:'POST',body:form,signal})
          if(incremental.controller.signal.aborted){setBusy(false);return}
          if(latencyTrial.current)latencyTrial.current.transcriptionMs=performance.now()-transcriptionStarted
          console.info('[Hikari transcript decision]',{text_chars:out.text?.trim().length??0,needs_retry:!!out.needs_retry,engine:out.engine||'unknown',input_audio:out.input_audio??null})
          if(!out.text?.trim())throw new Error('Nemotron returned an empty transcript. No message was sent. Check the selected microphone, then choose Retry microphone.')
          if(out.needs_retry){
            setRecognitionReview(out)
            setText(out.text);setMicState('retry');setBusy(false);setError(out.retry_reason||'Check the transcript, edit any mistakes, then send it or record again.');reportMic({event:'error',device,state:'retry',duration_ms:out.latency_ms||0,peak_percent:peakLevel.current,transcript:out.text,error:out.retry_reason});return
          }
          setText(out.text);setMicState('transcribed');reportMic({event:'transcribed',device,state:'complete',duration_ms:out.latency_ms||0,peak_percent:peakLevel.current,transcript:out.text})
          if(latencyTrial.current){
            console.info('[Hikari transcription latency]',{backend_finalize_or_decode_ms:out.latency_ms,transcription_path:out.final_pass==='whisper'?'verified':liveResult?.text?'live':reusable?'incremental':'recorded'})
            latencyTrial.current.engine=health?.engine||'unknown'
            latencyTrial.current.transcriptionPath=out.final_pass==='whisper'?'verified':liveResult?.text?'live':reusable?'incremental':'recorded'
            latencyTrial.current.responseStart=performance.now()
          }
          await send(out.text,captureMs/1000,recognitionProvenance(out))
        } catch(e){
          if(incremental.controller.signal.aborted){setBusy(false);return}
          setMicState('error');setError(e.message);reportMic({event:'error',device,state:'error',duration_ms:captureMs,peak_percent:peakLevel.current,error:e.message});setBusy(false);console.error('[Hikari recognition failed]',e)
        }
      }
      let stopReason='unknown'
      const markSpeech=()=>{
        if(r.state!=='recording')return
        if(!speechSeen.current){
          speechSeen.current=true;setError('');setMicState('speech detected')
          reportMic({event:'speech_detected',device,state:'recording',duration_ms:performance.now()-started.current})
        }
      }
      // VAD only decides turn boundaries. MediaRecorder and live recognition
      // retain the continuous capture, including audio before speech detection.
      const vad=automaticTurnEnd?await startSilero(context,recordingStream,{
        onProbability:probability=>{if(r.state==='recording'&&probability>=turnDetection.positiveThreshold)lastSpeech.current=performance.now()},
        onSpeech:markSpeech,
        onEnd:()=>{if(automaticTurnEnd&&r.state==='recording'&&speechSeen.current){stopReason='silero_silence';r.stop()}},
      }):{error:null,stop:async()=>{}}
      micVad.current=vad
      if(!callActiveRef.current||mutedRef.current||modeRef.current!=='voice'){
        await vad.stop();micVad.current=null;live?.cancel();incremental.cancel()
        source.disconnect();capture?.destroy();micDenoiser.current=null
        await context.close();micContext.current=null;return false
      }
      const analyse=rms=>{
        if(r.state!=='recording')return
        const level=Math.min(100,rms*500);peakLevel.current=Math.max(peakLevel.current,level);setMicLevel(level)
        const now=performance.now(),elapsed=r.captureClock.elapsed(now)
        if(now-lastLevelReport.current>500){lastLevelReport.current=now;reportMic({event:'level',device,state:speechSeen.current?'speech detected':'listening',duration_ms:elapsed,level_percent:level,peak_percent:peakLevel.current})}
        if(vad.error){stopReason='vad_error';discardCapture.current=true;setError(`Speech detection failed: ${vad.error}. Rejoin the call.`);r.stop();return}
        const limitReason=captureLimitReason(elapsed,speechSeen.current,automaticTurnEnd)
        if(limitReason){stopReason=limitReason;r.stop()}
      }
      started.current=performance.now();r.captureClock=new CaptureClock(started.current)
      setCapturePaused(false)
      r.start(100); setRecording(true);reportMic({event:'listening',device,state:'listening'})
      micFrame.current=monitorMicrophone(context,source,analyse,error=>{
        setError(error.message);reportMic({event:'error',device,state:'error',error:error.message})
        if(r.state==='recording')r.stop()
      });return true
    } catch(e) {
      micFrame.current?.();micFrame.current=null
      micVad.current?.stop();micVad.current=null
      streamingCapture.current?.cancel();incrementalCapture.current?.cancel()
      micDenoiser.current?.destroy();micDenoiser.current=null
      micLevelGraph.current?.destroy();micLevelGraph.current=null
      micStream.current?.getTracks().forEach(track=>track.stop());micStream.current=null
      if(micContext.current)await micContext.current.close().catch(()=>{});micContext.current=null
      setMicState('error');setError(`Microphone unavailable: ${e.message}`);reportMic({event:'error',state:'error',error:e.message});return false
    } finally {micStarting.current=false}
  }
  beginListening.current=toggleMic
  // Resume microphone capture after waitForPlayback completes. A volume-only
  // interruption detector cannot distinguish the learner from speaker echo,
  // and can abort the bot's own audio immediately on laptops.
  const stopCall = () => {
    playbackGeneration.current.cancel();bargeMonitor.current?.stop();bargeMonitor.current=null
    if(voiceDraftRef.current)URL.revokeObjectURL(voiceDraftRef.current.url)
    voiceDraftRef.current=null;setVoiceDraft(null);setCapturePaused(false)
    streamingCapture.current?.cancel();streamingCapture.current=null
    incrementalCapture.current?.cancel();incrementalCapture.current=null
    voiceRequest.current?.abort();voiceRequest.current=null
    callActiveRef.current=false;setCallActive(false);mutedRef.current=false;setMuted(false);setVoiceState('idle');setMicState('idle')
    if(['recording','paused'].includes(recorder.current?.state)){discardCapture.current=true;recorder.current.stop()}
    else{micStream.current?.getTracks().forEach(track=>track.stop());micStream.current=null}
    micVad.current?.stop();micVad.current=null
    micDenoiser.current?.destroy();micDenoiser.current=null
    micLevelGraph.current?.destroy();micLevelGraph.current=null
    playbackContext.current?.close().catch(()=>{});playbackContext.current=null;playbackTail.current=0
  }
  const startCall = async () => {
    if (health?.components?.stt === false) {
      setError('Speech recognition is offline. Restart Hikari without --skip-models, then refresh this page.')
      return
    }
    if(runtime?.paused){setError('Resume the lesson before joining the call.');return}
    callActiveRef.current = true; modeRef.current = 'voice'; mutedRef.current = false; setCallActive(true); setMuted(false); setError('')
    try {
      await ensureAudioReady()
      if(!micStream.current?.active){
        try{micStream.current=await navigator.mediaDevices.getUserMedia({audio:microphoneConstraints(selectedMic,{noiseSuppression:audioMode.browser})})}
        catch(error){
          if(!selectedMic||!['NotFoundError','OverconstrainedError'].includes(error.name))throw error
          localStorage.removeItem('hikari-mic-id');setSelectedMic('');setSessionAudio(saveSessionAudio(localStorage,{...sessionAudio,deviceId:''}))
          micStream.current=await navigator.mediaDevices.getUserMedia({audio:microphoneConstraints('',{noiseSuppression:audioMode.browser})})
        }
      }
      const track=micStream.current.getAudioTracks()[0]
      console.info('[Hikari microphone settings]',{device:track.label,...track.getSettings()})
      await refreshMicrophones(false)
    } catch(e) {
      setError(e.message);callActiveRef.current=false;setCallActive(false);return
    }
    const openingTurn = session.turns?.[0]
    const hasUserSpoken = session.turns?.some(t => t.role === 'user')
    if (openingTurn && openingTurn.role === 'assistant' && !hasUserSpoken) {
      streamVoice(openingTurn.text, openingTurn.correlationId || 'opening-turn', true, openingTurn.speaker_name)
        .catch(e => {
          if(e.name==='AbortError')return
          setVoiceState('failed')
          setError(`Voice playback failed: ${e.message}. You can still proceed by speaking.`)
          if(automaticTurnEnd)setTimeout(() => {if(callActiveRef.current&&!mutedRef.current&&modeRef.current==='voice')beginListening.current?.()}, 600)
        })
    } else {
      if (automaticTurnEnd&&!await toggleMic()) { callActiveRef.current = false; setCallActive(false) }
    }
  }
  const changeMode = next => {
    if(next===mode)return
    if(callActiveRef.current)stopCall()
    modeRef.current=next;setMode(next);setError('')
  }
  const toggleMute = () => {
    const next=!muted;mutedRef.current=next;setMuted(next)
    if(next&&['recording','paused'].includes(recorder.current?.state)){discardCapture.current=true;recorder.current.stop()}
    if(next){streamingCapture.current?.cancel();incrementalCapture.current?.cancel();micStream.current?.getTracks().forEach(track=>track.stop());micStream.current=null}
    if(automaticTurnEnd&&!next&&callActiveRef.current&&!busy&&voiceState==='ready')setTimeout(()=>beginListening.current?.(),100)
  }
  const toggleCamera = async () => {
    if (camera) { media.current?.getTracks().forEach(t=>t.stop()); media.current=null; setCamera(false); return }
    try {
      const stream=await navigator.mediaDevices.getUserMedia({video:{width:640,height:480}}); media.current=stream; setCamera(true)
      setTimeout(()=>{ if(video.current) video.current.srcObject=stream },0)
    } catch(e){setError(`Camera unavailable: ${e.message}`)}
  }
  const downloadCapture=()=>{
    if(!lastCapture.current)return
    const url=URL.createObjectURL(lastCapture.current)
    const link=document.createElement('a')
    link.href=url;link.download='hikari-microphone.webm';link.click()
    setTimeout(()=>URL.revokeObjectURL(url),1000)
  }
  const sendReviewedVoice=async()=>{
    const draft=voiceDraftRef.current
    if(!draft||reviewSending.current||!callActiveRef.current||mutedRef.current)return
    reviewSending.current=true;setBusy(true);setError('');setMicState('transcribing')
    const controller=new AbortController();voiceRequest.current=controller
    const timer=setTimeout(()=>controller.abort(),45000)
    try{
      const form=new FormData();form.append('file',draft.blob,'speech.webm');form.append('decoding_method',sessionAudio.decodingMethod)
      form.append('language',session.training_language||'English');form.append('duration_ms',String(draft.durationMs))
      form.append('context',`${session.title}. ${session.situation}`)
      const reusable=finalRecognitionForm(form,sessionAudio,session.id,draft.liveResult)
      const out=reusable||await api('/transcribe',{method:'POST',body:form,signal:controller.signal})
      if(!callActiveRef.current||voiceDraftRef.current!==draft||controller.signal.aborted)return
      if(!out.text?.trim()){URL.revokeObjectURL(draft.url);voiceDraftRef.current=null;setVoiceDraft(null);throw new Error('No words recognized. Press Record voice to try another turn.')}
      URL.revokeObjectURL(draft.url);voiceDraftRef.current=null;setVoiceDraft(null)
      if(out.needs_retry){setRecognitionReview(out);setText(out.text);setMicState('retry');setError(out.retry_reason||'Check the transcript, edit any mistakes, then send it or record again.');return}
      setMicState('transcribed');await send(out.text,draft.durationMs/1000,recognitionProvenance(out))
    }catch(error){if(error.name!=='AbortError'){setMicState('error');setError(error.message)}else if(callActiveRef.current){setMicState('error');setError('Recognition was interrupted or timed out. Your recording is still available.')}}
    finally{clearTimeout(timer);reviewSending.current=false;setBusy(false)}
  }
  const toggleVoiceRecording=()=>{
    const current=recorder.current
    if(current?.state==='recording'){
      current.hikariStopReason='manual_send';current.stop()
    }else if(voiceDraftRef.current){
      sendReviewedVoice()
    }else{
      beginListening.current?.()
    }
  }
  const latestReply=[...session.turns].reverse().find(turn=>turn.role==='assistant')
  const callStatus=!callActive?'Ready to start':voiceDraft?'Preparing your voice message…':capturePaused?'Recording paused':!recording&&['error','retry'].includes(micState)?'Recognition needs attention':voiceState==='speaking'||voiceState==='streaming'?`${activeSpeaker||session.counterpart} is speaking`:muted?'Microphone muted':micState==='transcribing'?'Understanding you…':voiceState==='generating'||busy?'Preparing response…':recording?(micState==='speech detected'?'Listening to you…':'Listening…'):'Connected'
  const participants=session.participants||[{participant_type:'learner',display_name:'You'},{participant_type:'ai',display_name:session.counterpart}]
  const aiParticipants=participants.filter(person=>person.participant_type==='ai')
  const multipleAI=aiParticipants.length>1
  const formatTime=value=>`${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`
  const finishSession=async(endAttempt=false)=>{try{await onComplete(endAttempt===true);stopCall()}catch(error){setError(error.message)}}
  const leaveSession=async()=>{try{stopCall();await onCancel()}catch(error){setError(error.message)}}
  const speakingNow=['speaking','streaming'].includes(voiceState)
  const definitionPeople=runtime?.definition?.participants||[]
  const reactionOf=person=>{const id=(definitionPeople.find(item=>item.name===person.display_name)||{}).id;return(id&&runtime?.reactions?.[id])||'neutral'}
  const stateOf=(person,index)=>speakingNow&&(person.display_name===activeSpeaker||(!activeSpeaker&&index===0))?'speaking':busy?'thinking':recording?'listening':'idle'
  const participantTile=(person,index,isLearner=false)=><div key={person.id||`${person.display_name}-${index}`} className={`participant-tile ${!isLearner&&person.display_name===activeSpeaker&&(voiceState==='speaking'||voiceState==='streaming')?'active-speaker':''}`}>
    {isLearner&&camera?<video ref={video} autoPlay muted playsInline/>:isLearner?<div className="participant-avatar learner-avatar"><Icon name="user"/></div>:<div className="participant-avatar"><Portrait name={person.display_name} role={person.scenario_role||session.counterpart} state={stateOf(person,index)} reaction={reactionOf(person)} size={150}/></div>}
    <strong>{person.display_name}{!isLearner?` (${person.scenario_role||session.counterpart})`:''}</strong>
    <span className="tile-mic">{isLearner&&!muted&&recording?<Icon name="mic" label="Microphone on"/>:<Icon name="micOff" label="Microphone off"/>}</span>
  </div>
  return <main className={`session-window ${runtime?'has-runtime':''}`}>


    <header className="session-header"><div><h1>{session.title}</h1><p>{session.description||session.situation}</p></div><div className="session-header-actions"><div className="session-clock"><span/> <strong>{formatTime(elapsed)}</strong><small>{callActive?'In Session':'Ready'}</small></div><i/>{!runtime?.scene&&<button className="h-small" onClick={()=>finishSession()} disabled={busy||sessionProgress?.outcome!=='success'}>Finish lesson</button>}</div></header>
    <ConversationCoach runtime={runtime} turns={session.turns} addressed={addressed} onAddress={setAddressed} onAction={runtimeAction} busy={busy} onRetry={()=>send(runtime.latest_input,0,{},true)} onDebrief={()=>finishSession()} onEndAttempt={()=>finishSession(true)} onPause={async()=>{if(runtime.paused){await runtimeAction('resume')}else{await interrupt(false);stopCall();await runtimeAction('pause')}}} onDelete={async()=>{stopCall();await api(`/sessions/${session.id}/conversation-data`,{method:'DELETE'});await onCancel(true)}}/>
    <div className="session-body">
      <section className="session-call-area">
        {error&&<div className="session-error" role="alert">{error}{lastCapture.current&&['error','retry'].includes(micState)&&<button onClick={downloadCapture}>Save microphone recording</button>}{callActive&&!recording&&!busy&&['error','retry'].includes(micState)&&<button onClick={()=>{setError('');beginListening.current?.()}} disabled={muted}>Retry microphone</button>}</div>}
        {recognitionReview&&mode==='voice'&&<section className="recognition-review" aria-label="Review recognized words"><strong>Check your words before sending</strong>{recognitionReview.original_text&&recognitionReview.original_text!==recognitionReview.text&&<details><summary>Live recognizer heard</summary><p>{recognitionReview.original_text}</p></details>}<div className="composer"><textarea aria-label="Recognized words" value={text} onChange={event=>setText(event.target.value)}/><button className="send" aria-label="Send checked transcript" disabled={busy||!text.trim()} onClick={()=>send()}><Icon name="send"/></button></div></section>}
        {sessionProgress&&<div className={`session-progress ${sessionProgress.outcome}`}><strong>{sessionProgress.outcome==='success'?'Objectives achieved':'Keep learning'}</strong><span>{sessionProgress.criteria?.filter(item=>item.met).length || 0}/{sessionProgress.criteria?.length || 0} objectives{sessionProgress.missing?.length?` · Next: ${sessionProgress.missing[0]}`:''}{sessionProgress.evaluation_mode?` · ${sessionProgress.evaluation_mode}`:''}</span></div>}
        {mode==='voice'?<div ref={sceneRef} className={`participant-stage ${multipleAI?'participant-grid':'single-participant'}`}><Backdrop archetype={runtime?.definition?.archetype}/>
          {multipleAI?<>{aiParticipants.map((person,index)=>participantTile(person,index))}{participantTile(participants.find(person=>person.participant_type==='learner')||{display_name:'You'},aiParticipants.length,true)}</>:<>
            <div className={`hero-participant ${voiceState==='speaking'||voiceState==='streaming'?'speaking':''}`}><div className="hero-rings"><Portrait name={aiParticipants[0]?.display_name||session.counterpart} role={aiParticipants[0]?.scenario_role||session.counterpart} state={stateOf(aiParticipants[0]||{display_name:session.counterpart},0)} reaction={reactionOf(aiParticipants[0]||{display_name:session.counterpart})} size={196}/></div><b>{callStatus}</b><small>{aiParticipants[0]?.display_name||session.counterpart}</small></div>
            <div className="self-pip">{camera?<video ref={video} autoPlay muted playsInline/>:<div className="pip-avatar"><Icon name="user"/></div>}<strong>You</strong><span>{muted?<Icon name="micOff" label="Muted"/>:<Icon name="mic" label="Microphone on"/>}</span></div>
            <div className="ai-role-label"><Icon name="sparkles"/> AI roleplay</div>
          </>}
          <button ref={audioButtonRef} className="session-audio-tab" aria-label="Open audio settings" aria-haspopup="dialog" aria-expanded={audioPanelOpen} aria-controls="session-audio-panel" onClick={()=>setAudioPanelOpen(true)}><Icon name="settings"/><span>Audio</span></button>
          {audioPanelOpen&&<div className="session-audio-backdrop" onClick={()=>setAudioPanelOpen(false)}>
            <section ref={audioPanelRef} id="session-audio-panel" className="session-audio-panel" role="dialog" aria-modal="true" aria-labelledby="session-audio-title" onClick={event=>event.stopPropagation()}>
              <header><div><p>CALL PREFERENCES</p><h2 id="session-audio-title">Audio settings</h2></div><button className="audio-panel-close" aria-label="Close audio settings" onClick={()=>setAudioPanelOpen(false)}><Icon name="close"/></button></header>
              <div className="audio-panel-content">
                <label className="audio-device-label" htmlFor="session-microphone">Microphone</label>
                <p className="audio-panel-description">{automaticTurnEnd?'Automatic input listens between replies and sends after a pause. You can also press Stop & send.':'Use the bottom Record voice button to start. Press it again to stop and send.'} Recordings are limited to 80 seconds.</p>
                <p className="audio-panel-description">Choose the input you want to use for this conversation.</p>
                <select id="session-microphone" value={selectedMic} disabled={callActive||micRefreshing} onChange={event=>{setSelectedMic(event.target.value);setSessionAudio(saveSessionAudio(localStorage,{...sessionAudio,deviceId:event.target.value}))}}>
                  <option value="">System default microphone</option>
                  {selectedMic&&!micOptions.some(item=>item.deviceId===selectedMic)&&<option value={selectedMic}>Previously selected microphone</option>}
                  {micOptions.map((item,index)=><option value={item.deviceId} key={item.deviceId}>{item.label||`Microphone ${index+1}`}</option>)}
                </select>
                <button className="audio-refresh" disabled={micRefreshing} onClick={()=>refreshMicrophones(!callActive)}>{micRefreshing?'Finding microphones…':'Enable / refresh microphones'}</button>
                <p className="audio-panel-note">Input: {automaticTurnEnd?'Automatic':'Manual'} · Session processing: {audioMode.name} · Gain {sessionAudio.gainEnabled?`${sessionAudio.gainDb} dB`:'off'} · Live recognition {sessionAudio.liveRecognition?'on':'off'}. Change processing preferences on the Settings page before joining your next session.</p>
                {callActive&&<p className="audio-panel-note">Input settings are locked during a call. Switch to chat before changing them.</p>}
                {!callActive&&micOptions.length===0&&<p className="audio-panel-note">Enable microphone access to see your devices.</p>}
                {micListError&&<p className="audio-panel-error" role="alert">{micListError}</p>}
              </div>
              <footer><button onClick={()=>setAudioPanelOpen(false)}>Done</button></footer>
            </section>
          </div>}
          {!callActive&&<div className="join-overlay"><h2>Ready to begin?</h2><p>{health?.components?.stt===false?'Speech recognition is offline. Start Hikari normally before joining.':automaticTurnEnd?'Your microphone starts automatically. Pause after speaking to send your turn.':'Use Record voice below, then press Stop & send when you are finished.'}</p><button onClick={startCall} disabled={health?.components?.stt===false}>{health?.components?.stt===false?'Speech Recognition Offline':'Join Voice Session'}</button></div>}
          {captions&&latestReply&&<div className="live-caption"><strong>{latestReply.speaker_name||aiParticipants[0]?.display_name||session.counterpart}</strong><p>{latestReply.caption_text||latestReply.text}</p>{latestReply.caption_text&&<small>{userSettings?.native_language} captions · spoken English</small>}</div>}
        </div>:<div className="session-chat"><div className="messages">{session.turns.map((turn,index)=><div className={`turn ${turn.role}`} key={index}><small>{turn.role==='user'?'You':turn.speaker_name||session.counterpart}</small><p>{turn.text}</p><SourceEvidence sources={turn.sources}/>{captions&&turn.caption_text&&<small className="translated-caption">{turn.caption_text}</small>}</div>)}{busy&&<div className="turn assistant typing"><i/><i/><i/></div>}<div ref={chatEnd}/></div><div className="composer"><textarea value={text} onChange={event=>setText(event.target.value)} placeholder="Type your response…" onKeyDown={event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send()}}}/><button className="send" onClick={()=>send()} disabled={busy||!text.trim()}><Icon name="send"/></button></div></div>}
        {session.posture_enabled&&<section className="posture-live"><strong>Posture indicators</strong><span>{camera?postureReason:"Camera is off; posture is not assessed."}</span>{posture&&Object.entries(posture).filter(([,v])=>typeof v==="number").map(([k,v])=><small key={k}>{k.replaceAll("_"," ")}: {Math.round(v)} · </small>)}</section>}<div className="meeting-controls">{session.runtime&&mode==='voice'&&<button disabled={!callActive} onClick={()=>interrupt()}><span><Icon name="hand"/></span>Interrupt</button>}{session.runtime&&<button className="take-back" disabled={!canTakeBack} onClick={takeBack} title="Undo your last turn and the reply to it"><span><Icon name="undo"/></span>Take back</button>}{mode==='voice'&&<button className={`voice-record-button ${recording?'selected is-recording':''}`} disabled={!callActive||muted||busy||micStarting.current||['speaking','streaming','generating'].includes(voiceState)} aria-pressed={recording} onClick={toggleVoiceRecording}><span><Icon name={recording?'stop':'record'}/></span>{recording?'Stop & send':voiceDraft?'Retry send':'Record voice'}</button>}<button onClick={onOpenSettings}><span><Icon name="sliders"/></span>Settings</button><button className={muted?'selected':''} onClick={toggleMute}><span><Icon name={muted?'micOff':'mic'}/></span>{muted?'Unmute':'Mute'}</button><button className={camera?'selected':''} onClick={toggleCamera}><span><Icon name="camera"/></span>Camera</button><button className="hangup" onClick={leaveSession}><span><Icon name="phoneOff"/></span>End Session</button><button className={captions?'selected':''} onClick={()=>setCaptions(value=>!value)}><span><Icon name="captions"/></span>Captions</button><button onClick={()=>changeMode(mode==='voice'?'chat':'voice')}><span><Icon name={mode==='voice'?'chat':'mic'}/></span>{mode==='voice'?'More':'Voice Call'}</button></div>
      </section>
      <aside className="session-transcript"><h2>Conversation</h2><div>{session.turns.map((turn,index)=><article className={turn.role} key={index}><div className="transcript-avatar">{turn.role==='user'?<Icon name="user"/>:<Portrait name={turn.speaker_name||session.counterpart} decorative size={34}/>}</div><section><header><strong>{turn.role==='user'?'You':turn.speaker_name||session.counterpart}</strong><span>· {formatTime(Math.max(0,Math.floor((turn.elapsed_seconds??((Date.parse(turn.created_at)-Date.parse(session.created_at))/1000))||0)))}</span></header><p>{turn.text}</p><SourceEvidence sources={turn.sources}/>{captions&&turn.caption_text&&<small className="translated-caption">{turn.caption_text}</small>}</section></article>)}{busy&&<article><div className="transcript-avatar"><Portrait name={activeSpeaker||aiParticipants[0]?.display_name||session.counterpart} state="thinking" decorative size={34}/></div><section className="transcript-typing"><i/><i/><i/></section></article>}</div></aside>
    </div>
  </main>
}
