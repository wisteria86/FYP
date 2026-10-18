import {useEffect,useRef,useState} from 'react'
import {microphoneConstraints,listMicrophones} from './micDevices.mjs'
import {createCleanCapture} from './noiseReduction.mjs'
import {createInputLevel,emptyLevels,accumulateLevels,levelSummary} from './inputLevel.mjs'
import {monitorMicrophone} from './micMonitor.mjs'

import {captureModes,captureMode,compareWords} from './voiceComparison.mjs'
import {loadSessionAudio,saveSessionAudio} from './sessionAudio.mjs'
import {record,release} from './voiceTestCapture.mjs'

export default function VoiceInputTest({request,runtime}){
  const [open,setOpen]=useState(false),[devices,setDevices]=useState([])
  const [device,setDevice]=useState(()=>localStorage.getItem('hikari-mic-id')||'')
  const [mode,setMode]=useState('rnnoise')
  const [controlLevel,setControlLevel]=useState(false),[gainDb,setGainDb]=useState(-6)
  const [meters,setMeters]=useState(null)
  const [expected,setExpected]=useState('Hello Hikari, I would like to practise my English today.')
  const [history,setHistory]=useState([])
  const [sessionSaved,setSessionSaved]=useState('')
  const [decoderMethods,setDecoderMethods]=useState(['greedy_search','modified_beam_search'])
  const [beamWidth,setBeamWidth]=useState(4),[decoderResults,setDecoderResults]=useState(null)
  const recorded=useRef(null)
  const [phase,setPhase]=useState('idle'),[error,setError]=useState(''),[level,setLevel]=useState(0)
  const [result,setResult]=useState(null),[audio,setAudio]=useState(null),[refreshing,setRefreshing]=useState(false)
  const active=useRef(null),urls=useRef([]),mounted=useRef(true)
  const busy=['starting','recording','recognizing','comparing'].includes(phase)
  useEffect(()=>setSessionSaved(''),[mode,controlLevel,gainDb,device])
  useEffect(()=>{mounted.current=true;return()=>{
    mounted.current=false
    if(active.current){active.current.cancelled=true;active.current.controller.abort();release(active.current)}
    urls.current.forEach(url=>URL.revokeObjectURL(url))
  }},[])
  const refresh=async()=>{
    setRefreshing(true);setError('')
    try{const next=await listMicrophones(navigator.mediaDevices,true);if(mounted.current)setDevices(next)}
    catch(error){if(mounted.current)setError(error.message)}
    finally{if(mounted.current)setRefreshing(false)}
  }
  const finish=async(run)=>{
    if(run!==active.current||run.finishing||run.cancelled)return
    run.finishing=true;clearTimeout(run.timer);run.stopMonitor?.()
    setPhase('recognizing');setLevel(0)
    try{
      run.recordings.forEach(item=>{if(item.recorder.state!=='inactive')item.recorder.stop()})
      const blobs=await Promise.all(run.recordings.map(item=>item.done))
      release(run)
      if(run.cancelled)return
      urls.current.forEach(url=>URL.revokeObjectURL(url))
      urls.current=blobs.map(blob=>URL.createObjectURL(blob))
      setAudio({original:urls.current[0],cleaned:urls.current[1]||null,mode:run.mode.id,gainDb:run.gainDb})
      const form=new FormData()
      const chosen=blobs.at(-1)
      recorded.current={blob:chosen,mode:run.mode.name,gainDb:run.gainDb}
      form.append('file',chosen,chosen.type.includes('mp4')?'microphone.m4a':'microphone.webm')
      form.append('language','English');form.append('duration_ms',String(performance.now()-run.started))
      const started=performance.now()
      run.timer=setTimeout(()=>run.controller.abort(),45000)
      const out=await request('/transcribe',{method:'POST',body:form,signal:run.controller.signal})
      if(!run.cancelled){
        const next={...out,wall_ms:Math.round(performance.now()-started),mode:run.mode.name,
          expected:run.expected,comparison:compareWords(run.expected,out.text||''),settings:run.settings,
          device:run.device,noise_reduction:!!run.clean,gainDb:run.gainDb,levels:{input:levelSummary(run.inputLevels),output:levelSummary(run.outputLevels)}}
        setResult(next);setHistory(items=>[next,...items].slice(0,6));setPhase('done')
      }
    }catch(error){if(!run.cancelled){setError(error.name==='AbortError'?'Recognition timed out. Try a shorter recording.':error.message);setPhase('error')}}
    finally{release(run);if(active.current===run)active.current=null}
  }
  const compareDecoders=async()=>{
    if(active.current||!recorded.current||!decoderMethods.length)return
    const run={controller:new AbortController(),recordings:[]};active.current=run
    setPhase('comparing');setError('');setDecoderResults(null)
    const recording=recorded.current,reference=expected
    try{
      const form=new FormData()
      form.append('file',recording.blob,'microphone.audio')
      form.append('methods',JSON.stringify(decoderMethods));form.append('beam_width',String(beamWidth))
      run.timer=setTimeout(()=>run.controller.abort(),195000)
      const response=await request('/stt/compare-decoders',{method:'POST',body:form,signal:run.controller.signal})
      if(!run.cancelled){
        setDecoderResults({mode:recording.mode,gainDb:recording.gainDb,reference,
          rows:response.results.map(item=>({...item,comparison:item.status==='ok'?compareWords(reference,item.text||''):null}))})
        setPhase('done')
      }
    }catch(error){if(!run.cancelled){setError(error.name==='AbortError'?'Decoder comparison timed out.':error.message);setPhase('error')}}
    finally{release(run);if(active.current===run)active.current=null}
  }
  const start=async()=>{
    if(active.current||refreshing)return
    const run={controller:new AbortController(),recordings:[],mode:captureMode(mode),expected,gainDb:controlLevel?gainDb:0,inputLevels:emptyLevels(),outputLevels:emptyLevels()};active.current=run
    setPhase('starting');setError('');setResult(null);setMeters(null);setDecoderResults(null);recorded.current=null
    urls.current.forEach(url=>URL.revokeObjectURL(url));urls.current=[];setAudio(null)
    try{
      run.stream=await navigator.mediaDevices.getUserMedia({audio:microphoneConstraints(device,{noiseSuppression:run.mode.browser})})
      if(run.cancelled){release(run);return}
      const track=run.stream.getAudioTracks()[0]
      run.settings=track.getSettings();run.device=track.label||'System default microphone'
      const Context=window.AudioContext||window.webkitAudioContext
      run.context=new Context({sampleRate:48000});await run.context.resume()
      if(controlLevel)run.levelGraph=createInputLevel(run.context,run.stream,run.gainDb)
      const leveledStream=run.levelGraph?.stream||run.stream
      if(run.mode.rnnoise)run.clean=await createCleanCapture(run.context,leveledStream)
      if(run.cancelled){release(run);return}
      const source=run.clean?.source||run.context.createMediaStreamSource(run.levelGraph?.stream||run.stream)
      run.recordings=[record(run.stream)]
      if(run.clean||run.levelGraph)run.recordings.push(record(run.clean?.stream||run.levelGraph.stream))
      const monitorError=error=>{
        if(run.cancelled)return
        run.cancelled=true;run.controller.abort();release(run);active.current=null;setError(error.message);setPhase('error')
      }
      const rawSource=run.context.createMediaStreamSource(run.stream)
      const stopInput=monitorMicrophone(run.context,rawSource,(rms,frame)=>accumulateLevels(run.inputLevels,frame),monitorError)
      const stopOutput=monitorMicrophone(run.context,source,(rms,frame)=>{
        if(run.cancelled)return
        accumulateLevels(run.outputLevels,frame)
        setLevel(Math.min(100,rms*500))
        setMeters({input:levelSummary(run.inputLevels),output:levelSummary(run.outputLevels)})
      },monitorError)
      run.stopMonitor=()=>{stopInput();stopOutput();rawSource.disconnect()}
      run.recordings.forEach(item=>{item.recorder.start(100);item.recorder.addEventListener('error',()=>finish(run),{once:true})})
      run.started=performance.now();setPhase('recording')
      run.timer=setTimeout(()=>finish(run),10000)
    }catch(error){release(run);if(!run.cancelled){setError(error.message);setPhase('error')}if(active.current===run)active.current=null}
  }
  return <section className="settings-section voice-input-test">
    <div className="section-title"><div><p className="eyebrow">VOICE INPUT CHECK</p><h2>Test microphone & recognition</h2><p>Compare three capture modes against the same spoken sentence.</p></div><button className="primary-outline-btn" disabled={busy} onClick={()=>setOpen(value=>!value)} aria-expanded={open} aria-controls="voice-input-check">{open?'Close test':'Open test'}</button></div>
    {open&&<div id="voice-input-check">
      <div className="voice-picker-row"><label>Microphone<select value={device} disabled={busy||refreshing} onChange={event=>setDevice(event.target.value)}><option value="">System default microphone</option>{device&&!devices.some(item=>item.deviceId===device)&&<option value={device}>Saved session microphone</option>}{devices.map((item,index)=><option key={item.deviceId} value={item.deviceId}>{item.label||`Microphone ${index+1}`}</option>)}</select></label><button className="primary-outline-btn" disabled={busy||refreshing} onClick={refresh}>{refreshing?'Finding microphones…':'Enable / refresh microphones'}</button></div>
      <div className="voice-picker-row"><label>Audio processing<select value={mode} disabled={busy} onChange={event=>setMode(event.target.value)}>{captureModes.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>
      <div className="voice-level-control"><label className="voice-check-toggle"><input type="checkbox" checked={controlLevel} disabled={busy} onChange={event=>setControlLevel(event.target.checked)}/> Control input level</label>{controlLevel&&<label>Software gain: {gainDb>0?'+':''}{gainDb} dB<input aria-label="Software input gain" type="range" min="-24" max="6" step="1" value={gainDb} disabled={busy} onChange={event=>setGainDb(Number(event.target.value))}/></label>}<p className="voice-check-note">Applies before extra noise reduction and recognition. Start at −6 dB and compare the same phrase. This does not change system microphone gain or repair audio already clipped during capture.</p></div>
      <label className="voice-check-reference">What I will say (optional)<textarea rows={2} value={expected} disabled={busy} onChange={event=>setExpected(event.target.value)} placeholder="Enter the sentence you will read aloud."/></label>
      <p className="voice-check-note">Read the same sentence once per mode. Echo cancellation stays on and automatic gain stays off. Browsers may ignore unsupported capture settings.</p>
      <p className="voice-check-note">Recognizer: {runtime?.engine||'active engine'} · English · Records up to 10 seconds. Test options do not change session preferences.</p>
      <button className="primary-outline-btn" disabled={busy} onClick={()=>{try{saveSessionAudio(localStorage,{...loadSessionAudio(localStorage),deviceId:device,mode,gainEnabled:controlLevel,gainDb});setSessionSaved('Saved for your next voice session.')}catch(error){setError(error.message)}}}>Use these settings in sessions</button>{sessionSaved&&<p role="status" className="voice-check-note">{sessionSaved}</p>}
      <div className="voice-check-actions"><button className="primary-outline-btn" disabled={busy||refreshing} onClick={start}>Start test</button>{phase==='recording'&&<button className="voice-check-stop" onClick={()=>finish(active.current)}>Stop & recognize</button>}<span role="status">{phase==='starting'?'Preparing microphone…':phase==='recording'?'Speak naturally, then stop.':phase==='recognizing'?'Recognizing your recording…':phase==='comparing'?'Comparing decoders on the saved recording…':phase==='done'?'Test complete':phase==='error'?'Test needs attention':''}</span></div>
      {phase==='recording'&&<meter className="voice-check-meter" aria-label="Processed microphone level" min="0" max="100" value={level}/>}
      {meters&&<div className="voice-level-meters">{[['Captured input',meters.input],['Recognition input',meters.output]].map(([label,stats])=><div key={label}><strong>{label}</strong><meter min="0" max="1" value={stats.peak} aria-label={`${label} peak`}/><small>Peak {stats.peak.toFixed(3)} · RMS {stats.rms.toFixed(3)} · Near-clipping {stats.nearClippedPercent.toFixed(2)}%</small></div>)}{meters.input.nearClippedPercent>0&&<p className="voice-check-note">Some sampled input is near full scale. Lower system microphone gain or boost if the recording sounds distorted.</p>}<p className="voice-check-note">Measurements sample short audio windows; near-clipping counts samples at or above 0.99 and is a warning, not proof of distortion.</p></div>}
      {error&&<div className="settings-alert error" role="alert"><p>{error}</p></div>}
      {audio&&<div className="voice-check-playback"><label>{audio.cleaned?'Captured recording before extra processing':'Captured recording · sent to recognizer'}<audio controls src={audio.original}/><a href={audio.original} download="hikari-original.webm">Save original recording</a></label>{audio.cleaned&&<label>Processed recording · sent to recognizer<audio controls src={audio.cleaned}/><a href={audio.cleaned} download="hikari-cleaned.webm">Save cleaned recording</a></label>}</div>}
      {result&&<div className="voice-check-result"><strong>{result.text?.trim()?'What Hikari heard':'No words recognized'}</strong><p>{result.text?.trim()||'Listen to the recording and check the selected microphone.'}</p><small>{result.engine||runtime?.engine||'Recognizer'} · Backend {Math.round(result.latency_ms||0)} ms · Round trip {result.wall_ms} ms · {result.mode} · Gain {result.gainDb} dB{result.needs_retry?' · Low-confidence result: try another recording.':''}</small>{result.comparison&&<p className="voice-check-note">Word errors: {result.comparison.errors} across {result.comparison.words} reference words ({result.comparison.wer}% word error rate; lower is better).</p>}<p className="voice-check-note">Microphone: {result.device} · Browser suppression reported: {String(result.settings.noiseSuppression??'not reported')}</p>{result.input_audio&&<p className="voice-check-note">Decoded audio: {Math.round(result.input_audio.duration_ms)} ms · RMS {result.input_audio.rms} · Peak {result.input_audio.peak}</p>}</div>}
      <div className="voice-decoder-test"><h3>Compare decoding methods</h3><p className="voice-check-note">Record once above, then run either or both methods on the exact same processed audio. Session decoding stays unchanged. Each decoder loads separately; unsupported methods are reported without stopping Hikari.</p>
        <div className="voice-decoder-options">{[['greedy_search','Greedy search'],['modified_beam_search','Modified beam search']].map(([id,label])=><label key={id}><input type="checkbox" checked={decoderMethods.includes(id)} disabled={busy} onChange={event=>setDecoderMethods(items=>event.target.checked?[...items,id]:items.filter(item=>item!==id))}/>{label}</label>)}<label>Beam width<input type="number" min="1" max="8" value={beamWidth} disabled={busy||!decoderMethods.includes('modified_beam_search')} onChange={event=>setBeamWidth(Number(event.target.value))}/></label></div>
        <button className="primary-outline-btn" disabled={busy||!recorded.current||!decoderMethods.length||!Number.isInteger(beamWidth)||beamWidth<1||beamWidth>8} onClick={compareDecoders}>Compare on this recording</button>
        {decoderResults&&<><p className="voice-check-note">{decoderResults.mode} · Gain {decoderResults.gainDb} dB · Same audio for every method. Recognition time excludes model loading; these are isolated recorded-audio tests, not live-session latency.</p><div className="decoder-results">{decoderResults.rows.map(item=><article key={item.method}><strong>{item.method==='greedy_search'?'Greedy search':'Modified beam search'}</strong>{item.status==='ok'?<><p>{item.text||'No words recognized'}</p><dl><div><dt>Recognition</dt><dd>{Math.round(item.recognition_ms)} ms</dd></div><div><dt>Real-time factor</dt><dd>{item.realtime_factor}</dd></div><div><dt>Model load + warmup</dt><dd>{Math.round(item.load_ms)} ms</dd></div><div><dt>Audio decoding</dt><dd>{Math.round(item.audio_decode_ms)} ms</dd></div>{item.comparison&&<div><dt>Word error rate</dt><dd>{item.comparison.wer}%</dd></div>}</dl><small>Sherpa-ONNX {item.runtime_version}{item.beam_width?` · Beam ${item.beam_width}`:''} · Final padding {item.finalize_timing?.padding_seconds} s</small></>:<p role="status">{item.status==='unsupported'?'Unavailable: ':''}{item.message}</p>}</article>)}</div></>}
      </div>
      {history.length>0&&<div className="voice-check-history"><div><h3>Recent comparisons</h3><button className="primary-outline-btn" disabled={busy} onClick={()=>setHistory([])}>Clear</button></div><p className="voice-check-note">Last six tests in this view. Compare the same microphone, sentence, and recognizer; word error rate measures transcription differences, not pronunciation quality.</p>{history.map((item,index)=><article key={index}><strong>{item.mode}</strong><p>{item.text||'No words recognized'}</p>{item.expected&&<small>Reference: {item.expected}</small>}<small>{item.device} · Gain {item.gainDb} dB · {item.engine||runtime?.engine||'Recognizer'} · {Math.round(item.latency_ms||0)} ms{item.comparison?` · ${item.comparison.wer}% word error rate`:''}</small><small>Sampled near-clipping: input {item.levels.input.nearClippedPercent.toFixed(2)}% → recognition {item.levels.output.nearClippedPercent.toFixed(2)}%</small></article>)}</div>}
    </div>}
  </section>
}
