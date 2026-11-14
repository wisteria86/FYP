import { useState } from 'react'
import { ScoreRing, api } from '../ui/core'
import { Icon } from '../ui/Icon'
import { GameTape } from '../call/GameTape'

export function Reflection({ sessionId }) {
  const [text,setText]=useState(''),[state,setState]=useState('')
  const save=async()=>{try{setState('');await api(`/sessions/${sessionId}/actions`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'reflect',request_id:crypto.randomUUID(),data:{text}})});setState('Saved.')}catch(e){setState(e.message)}}
  return <section className="evidence reflection-box"><p className="eyebrow">YOUR REFLECTION</p><label>What would you change in your next attempt? This is optional.<textarea value={text} maxLength={2000} onChange={e=>setText(e.target.value)}/></label><button className="h-soft" disabled={!text.trim()} onClick={save}>Save reflection</button>{state&&<small role="status"> {state}</small>}</section>
}

export function PostureSummary({ summary }) {
  if(!summary)return null
  if(!summary.available)return <section className="evidence"><h3>Posture indicators</h3><p>{summary.note}</p></section>
  return <section className="evidence"><h3>Posture indicators · separate from proficiency</h3>{summary.indicators.map(item=><p key={item.name}><strong>{item.name.replaceAll('_',' ')}:</strong> {Math.round(item.average)}/100, in a good position {item.steady_share}% of the time{item.trend==='not enough samples'?'':`, ${item.trend} during the session`}.{item.cue?` ${item.cue}`:''}</p>)}<small>{summary.samples} camera samples. {summary.note}</small></section>
}

export function Assessment({ session, assessment, onDone, onRetry, onPractiseMoment }) {
  return <main className="assessment"><div className="assessment-hero"><p className="eyebrow">SESSION COMPLETE</p><h1>{session.title}</h1><ScoreRing score={assessment.overall} size={150}/><p>{assessment.feedback}</p></div><div className="assessment-grid"><section><p className="eyebrow">RUBRIC BREAKDOWN</p>{Object.entries(assessment.scores).map(([k,v])=><div className="metric" key={k}><span>{k.replaceAll('_',' ')}</span><div><i style={{width:`${v}%`}}/></div><strong>{Math.round(v)}</strong></div>)}</section><section><p className="eyebrow">COACHING NOTES</p>{assessment.strengths.length>0&&<h3>What worked</h3>}{assessment.strengths.map(x=><p className="note good" key={x}><Icon name="checkCircle"/> {x}</p>)}<h3>Improve next</h3>{assessment.improvements.map(x=><p className="note improve" key={x}><Icon name="trendUp"/> {x}</p>)}</section></div><GameTape sessionId={session.id} onPractiseMoment={onPractiseMoment}/><PostureSummary summary={assessment.posture_summary}/>{assessment.speech_signal&&<section className="evidence"><h3>Speech recognition signal</h3><p>Average recognizer confidence across {assessment.speech_signal.turns} voice turns: {assessment.speech_signal.average}.</p><small>{assessment.speech_signal.note}</small></section>}<section className="evidence"><p className="eyebrow">EVIDENCE</p>{assessment.evidence.map(x=><p key={x}>{x}</p>)}</section><Reflection sessionId={session.id}/><div className="assessment-actions"><button className="h-soft" onClick={onRetry}>Try a new case of this lesson</button><button className="primary done" onClick={onDone}>Back to overview</button></div></main>
}
