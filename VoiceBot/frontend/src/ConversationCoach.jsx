import {useEffect,useRef,useState} from 'react'
import './ConversationCoach.css'

export default function ConversationCoach({runtime,turns,onAction,onAddress,addressed,onDebrief,onEndAttempt,onPause,onDelete,onRetry,busy}){
  const [open,setOpen]=useState(false),[error,setError]=useState(''),[correction,setCorrection]=useState(''),[turnId,setTurnId]=useState('')
  const [reflection,setReflection]=useState(runtime?.reflection||'')
  const [clock,setClock]=useState(Date.now())
  const retryAt=Date.parse(runtime?.provider_status?.retry_at||'')
  const retrySeconds=Number.isFinite(retryAt)?Math.max(0,Math.ceil((retryAt-clock)/1000)):0
  useEffect(()=>{
    setClock(Date.now())
    if(!Number.isFinite(retryAt)||retryAt<=Date.now())return
    const timer=setInterval(()=>{setClock(Date.now());if(Date.now()>=retryAt)clearInterval(timer)},1000)
    return()=>clearInterval(timer)
  },[retryAt])
  const [prep,setPrep]=useState({target:'',alternative:'',walk_away:'',reason:'',...runtime?.preparation})
  const [offer,setOffer]=useState({price:11000,currency:'USD',seats:20,delivery_days:30,support_months:3,rationale:'',condition:''})
  const dialog=useRef(null),trigger=useRef(null)
  useEffect(()=>{
    if(!open)return
    const previous=document.activeElement
    dialog.current?.focus()
    const key=event=>{
      if(event.key==='Escape')setOpen(false)
      if(event.key==='Tab'){
        const nodes=[...dialog.current.querySelectorAll('button:not(:disabled),select,input,textarea,[tabindex="0"]')].filter(n=>n.getClientRects().length)
        if(!nodes.length)return
        if(event.shiftKey&&document.activeElement===nodes[0]){event.preventDefault();nodes.at(-1).focus()}
        else if(!event.shiftKey&&document.activeElement===nodes.at(-1)){event.preventDefault();nodes[0].focus()}
      }
    }
    document.addEventListener('keydown',key)
    return()=>{document.removeEventListener('keydown',key);if(previous?.isConnected)previous.focus()}
  },[open])
  if(!runtime)return null
  const perform=async(action,data={})=>{try{setError('');await onAction(action,data)}catch(e){setError(e.message)}}
  const people=runtime.definition.participants.filter(p=>p.kind==='ai'),last=runtime.coach.at(-1)
  return <section className="conversation-coach" aria-label="Conversation controls">
    <div className="runtime-toolbar"><label>Speaking to <select value={addressed} onChange={e=>onAddress(e.target.value)}><option value="">Open floor</option>{people.map(p=><option key={p.id} value={p.id}>{p.name} · {p.role}</option>)}</select></label>
      <button onClick={()=>{setOpen(true);perform('coach')}}>Ask coach</button><button ref={trigger} onClick={()=>setOpen(true)} aria-expanded={open} aria-controls="lesson-support-drawer">Lesson support{last&&<span className="coach-unread" aria-label="Coach feedback available"/>}</button>
      <button onClick={onPause}>{runtime.paused?'Resume lesson':'Pause lesson'}</button>
      {runtime.scene&&!runtime.completed&&<button disabled={busy} onClick={onEndAttempt}>Finish and get feedback</button>}
    </div>
    {runtime.definition.brief&&<details className="task-brief"><summary>Your task</summary><p><strong>{runtime.definition.brief.you_are}</strong> {runtime.definition.brief.situation}</p><p>{runtime.definition.brief.task}</p><p><strong>You're done when:</strong> {runtime.definition.brief.done_looks_like}</p></details>}
    {last?.inline&&<div className="coach-inline" role="status" lang={runtime.preferences.coach_language==='Urdu'?'ur':'en'} dir={runtime.preferences.coach_language==='Urdu'?'rtl':'ltr'}><strong>Coach</strong><span>{last.text}</span></div>}
    {runtime.provider_status?.available===false&&<div className="runtime-notice" role="status"><span>{runtime.provider_status.reason}</span>{runtime.failed_turn_id&&<button disabled={busy||retrySeconds>0} onClick={onRetry}>{busy?'Retrying…':retrySeconds>0?`Retry in ${retrySeconds}s`:'Retry response'}</button>}</div>}
    {runtime.completed&&!runtime.extra_practice&&<div className="lesson-closure" role="status"><strong>You demonstrated the lesson objectives.</strong><p>Finish the exchange at your pace. This records today’s achievement, not permanent mastery.</p><button onClick={onDebrief}>View debrief</button><button onClick={()=>perform('extra_practice')}>Keep practising</button></div>}
    {open&&<div className="coach-overlay" onMouseDown={e=>{if(e.target===e.currentTarget)setOpen(false)}}>
      <section id="lesson-support-drawer" className="coach-drawer" role="dialog" aria-modal="true" aria-labelledby="coach-heading" ref={dialog} tabIndex={-1}>
      <header><div><small>PRIVATE LEARNING SUPPORT</small><h2 id="coach-heading">Your coach</h2></div><button aria-label="Close lesson support" onClick={()=>setOpen(false)}>×</button></header>
      <div className="coach-details">
      {last&&<div className="coach-message" lang={runtime.preferences.coach_language==='Urdu'?'ur':'en'} dir={runtime.preferences.coach_language==='Urdu'?'rtl':'ltr'}><strong>{last.target}</strong><p>{last.text}</p></div>}
      {runtime.repairs?.length>0&&<details><summary>Scenario corrections</summary>{runtime.repairs.slice(-2).map((r,i)=><p key={i}>Earlier: “{r.quote}”<br/>Established fact: {r.binding_fact}</p>)}</details>}
      <p>Participants are AI simulations. Characters stay in role; this coach provides learning support. English dialogue includes optional Urdu help. Other language modes are experimental.</p>
      <div className="coach-preferences">{[['correction_style','Corrections',['on_request','selective','debrief']],['coach_language','Coach language',['English','Urdu']],['challenge','Challenge',['beginner','intermediate','advanced']],['intensity','Interaction intensity',['gentle','balanced','challenging']]].map(([key,label,options])=><label key={key}>{label}<select value={runtime.preferences[key]} onChange={e=>perform('preferences',{[key]:e.target.value})}>{options.map(v=><option key={v} value={v}>{v.replaceAll('_',' ')}</option>)}</select></label>)}</div>
      <ul>{runtime.progress.criteria.map(c=><li key={c.id}>{c.met?'Demonstrated':'Practising'}: {c.name}</li>)}</ul>
      <small>{runtime.progress.evaluation_mode}. Assisted examples are practice; a fresh answer supplies independent evidence.</small>
      <details><summary>Correct a recognition mistake</summary><select value={turnId} onChange={e=>{setTurnId(e.target.value);setCorrection(turns.find(t=>String(t.id)===e.target.value)?.text||'')}}><option value="">Choose your response</option>{turns.filter(t=>t.role==='user'&&t.id).map(t=><option key={t.id} value={t.id}>{t.text.slice(0,90)}</option>)}</select><textarea aria-label="Correct transcript" value={correction} onChange={e=>setCorrection(e.target.value)}/><button disabled={!turnId||!correction.trim()} onClick={()=>perform('correct',{turn_id:Number(turnId),text:correction})}>Save correction and review evidence</button><p>The original is retained. Unreliable audio is excluded from assessment.</p></details>
      {runtime.definition.negotiation&&<details><summary>Private preparation and offer ledger</summary><p>Only you and your coach see these preparation notes.</p><dl className="preparation-brief"><dt>Your target</dt><dd>USD {runtime.definition.negotiation.preparation_brief.target?.toLocaleString()}</dd><dt>Your approved limit</dt><dd>USD {runtime.definition.negotiation.preparation_brief.maximum?.toLocaleString()}</dd><dt>Your alternative</dt><dd>{runtime.definition.negotiation.preparation_brief.alternative}</dd></dl>{Object.keys(prep).map(key=><label key={key}>{{target:'Your target',alternative:'Your alternative',walk_away:'Your walk-away limit',reason:'Your reasoning'}[key]}<input value={prep[key]} onChange={e=>setPrep({...prep,[key]:e.target.value})}/></label>)}<button onClick={()=>perform('prepare',prep)}>Save private preparation</button>
        <h3>Propose a package</h3>{Object.keys(offer).filter(k=>k!=='currency').map(key=><label key={key}>{{price:'Price (USD)',seats:'Training seats',delivery_days:'Delivery (days)',support_months:'Support (months)',rationale:'Why this offer works',condition:'Condition or requested return'}[key]}{typeof offer[key]==='number'?<input type="number" value={offer[key]} onChange={e=>setOffer({...offer,[key]:Number(e.target.value)})}/>:<input value={offer[key]} onChange={e=>setOffer({...offer,[key]:e.target.value})}/>}</label>)}<button onClick={()=>perform('offer',offer)}>Propose USD package</button>
        {runtime.offers.map(o=><article key={o.id}><strong>{o.status} · {o.seller_response.replaceAll('_',' ')}</strong><p>USD {o.terms.price} · {o.terms.seats} seats · {o.terms.delivery_days} days · {o.terms.support_months} months support</p><p>{o.reason}</p>{o.status==='proposed'&&<><button disabled={o.seller_response!=='acceptable_pending_confirmation'} onClick={()=>perform('accept',{offer_id:o.id})}>Confirm agreement</button><button onClick={()=>perform('withdraw',{offer_id:o.id})}>Withdraw</button></>}</article>)}
      </details>}
      <label>Optional reflection: what would you change next time?<textarea value={reflection} onChange={e=>setReflection(e.target.value)}/></label><button onClick={()=>perform('reflect',{text:reflection})}>Save reflection</button><button onClick={()=>perform('skip')}>Skip for now</button>
      <details><summary>Data and privacy</summary><p>Transcripts, corrections and evidence are stored locally and relevant context goes to the configured AI provider. Raw microphone recordings are not saved by this runtime. Camera use is optional.</p><button onClick={onDelete}>Delete this conversation’s text and evidence</button></details>
      {error&&<p role="alert">{error}</p>}
      </div></section></div>}
  </section>
}
