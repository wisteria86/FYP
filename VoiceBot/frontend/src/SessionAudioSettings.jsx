import {useEffect,useState} from 'react'
import {listMicrophones} from './micDevices.mjs'
import {loadSessionAudio,saveSessionAudio,sessionAudioModes} from './sessionAudio.mjs'

export default function SessionAudioSettings({request}){
 const [value,setValue]=useState(()=>loadSessionAudio(localStorage)),[devices,setDevices]=useState([])
 const [busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('')
 useEffect(()=>{const refresh=()=>setValue(loadSessionAudio(localStorage));window.addEventListener('hikari-session-audio-changed',refresh);return()=>window.removeEventListener('hikari-session-audio-changed',refresh)},[])
 const update=(key,next)=>{setValue(current=>({...current,[key]:next}));setMessage('')}
 const refresh=async()=>{
  setBusy(true);setError('')
  try{setDevices(await listMicrophones(navigator.mediaDevices,true))}catch(error){setError(error.message)}finally{setBusy(false)}
 }
 const save=async()=>{
  setBusy(true)
  try{if(value.decodingMethod==='modified_beam_search')await request(`/stt/session-decoder?decoding_method=${encodeURIComponent(value.decodingMethod)}`,{method:'POST'});const next=saveSessionAudio(localStorage,value);setValue(next);setError('');setMessage('Saved. Applies when you next join a voice session in this browser.')}catch(error){setError([404,405].includes(error.status)?'Decoder settings are unavailable on this backend. Restart Hikari with the updated backend, then refresh this page.':error.message)}finally{setBusy(false)}
 }
 return <section className="settings-section session-audio-settings"><div className="section-title"><div><p className="eyebrow">SESSION VOICE INPUT</p><h2>Audio settings for sessions</h2><p>Choose what real sessions use. Test controls below stay separate until you save them here.</p></div></div>
 <label>Nemotron decoding<select value={value.decodingMethod} disabled={busy} onChange={event=>update('decodingMethod',event.target.value)}><option value="greedy_search">Greedy search — fastest</option><option value="modified_beam_search">Modified beam search — compare alternatives</option></select></label><p className="voice-check-note">Applies to live and recorded English recognition. Beam search uses four paths and requires a compatible Sherpa runtime. Saving validates support; unavailable choices are not applied.</p>
 <label>Session input<select value={value.inputMode} onChange={event=>update('inputMode',event.target.value)}><option value="manual">Manual — press to record, press to send</option><option value="auto">Automatic — detect speech and send after a pause</option></select></label><p className="voice-check-note">Manual gives you control of each turn. Automatic uses Silero speech detection and resumes listening after replies.</p>
 <div className="voice-picker-row"><label>Microphone<select value={value.deviceId} disabled={busy} onChange={event=>update('deviceId',event.target.value)}><option value="">System default microphone</option>{value.deviceId&&!devices.some(item=>item.deviceId===value.deviceId)&&<option value={value.deviceId}>Saved microphone</option>}{devices.map((item,index)=><option key={item.deviceId} value={item.deviceId}>{item.label||`Microphone ${index+1}`}</option>)}</select></label><button className="primary-outline-btn" disabled={busy} onClick={refresh}>{busy?'Finding microphones…':'Enable / refresh microphones'}</button><label>Noise processing<select value={value.mode} onChange={event=>update('mode',event.target.value)}>{sessionAudioModes.map(mode=><option key={mode.id} value={mode.id}>{mode.name}</option>)}</select></label></div>
 <div className="voice-level-control"><label className="voice-check-toggle"><input type="checkbox" checked={value.gainEnabled} onChange={event=>update('gainEnabled',event.target.checked)}/> Control input level</label>{value.gainEnabled&&<label>Software gain: {value.gainDb>0?'+':''}{value.gainDb} dB<input aria-label="Session software gain" type="range" min="-24" max="6" step="1" value={value.gainDb} onChange={event=>update('gainDb',Number(event.target.value))}/></label>}<p className="voice-check-note">Applied before extra noise reduction and recognition. Cannot repair microphone clipping. Echo cancellation stays on; automatic gain control stays off.</p></div>
 <label className="voice-check-toggle"><input type="checkbox" checked={value.liveRecognition} onChange={event=>update('liveRecognition',event.target.checked)}/> Recognize live while recording</label><p className="voice-check-note">English Nemotron can transcribe while you speak. Your button still controls when the conversation receives your turn. If unavailable, the saved recording is transcribed after you stop.</p>
 <button className="primary-outline-btn" disabled={busy} onClick={save}>Save session audio settings</button>{message&&<p role="status" className="voice-check-note">{message}</p>}{error&&<p role="alert" className="audio-panel-error">{error}</p>}
 </section>
}
