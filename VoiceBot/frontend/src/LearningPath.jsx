import {useCallback,useEffect,useState} from 'react'
import './LearningPath.css'

function Lesson({lesson,onStart,current}){
  const [open,setOpen]=useState(false)
  const begin=()=>onStart(lesson.skill_id,lesson.level==='adaptive'?'intermediate':(lesson.level||'intermediate'),lesson.id)
  return <li className={`path-lesson ${lesson.state} ${lesson.locked?'locked':''} ${lesson.checkpoint?'checkpoint':''} ${current?'current':''}`} aria-current={current?'step':undefined}>
    <span className="path-dot" aria-hidden="true"/>
    <div className="path-lesson-main">
      <div><strong>{lesson.title}{lesson.checkpoint&&<em> Checkpoint</em>}</strong><small>{lesson.state_label}{lesson.attempts?` · ${lesson.attempts} ${lesson.attempts===1?'attempt':'attempts'}`:''}{lesson.locked?' · Locked until the checkpoint before it':''}</small></div>
      <div className="path-actions">
        {lesson.can_do&&<button className="path-link" aria-expanded={open} onClick={()=>setOpen(value=>!value)}>{open?'Hide':'What I showed'}</button>}
        <button className={lesson.locked?'path-link':'h-soft'} onClick={begin}>{lesson.locked?'Try anyway':lesson.attempts?'Practise again':'Start'}</button>
      </div>
    </div>
    {open&&lesson.can_do&&<div className="path-evidence"><p>In this lesson you showed that you can:</p><ul>{lesson.can_do.objectives.map(item=><li key={item}>{item.toLowerCase()}</li>)}</ul>{lesson.can_do.evidence&&<blockquote>{lesson.can_do.evidence}</blockquote>}<small>A later review with a new case will check whether this lasts.</small></div>}
  </li>
}

export default function LearningPath({request,onStart}){
  const [path,setPath]=useState(null),[error,setError]=useState('')
  const load=useCallback(async()=>{try{setPath(await request('/learning-path'))}catch(e){setError(e.message)}},[request])
  useEffect(()=>{load()},[load])
  if(error)return <main className="page hikari-page"><p role="alert">{error}</p></main>
  if(!path)return <main className="page hikari-page"><p>Loading your path…</p></main>
  return <main className="page hikari-page learning-path"><header className="h-page-head"><div><h1>Learning Path</h1><p>Move through units at your own pace. Each unit ends with a checkpoint that opens the next one.</p></div></header>
    <section className="path-summary">
      <article className="h-card"><strong>{path.counts.independent_today}</strong><span>shown today</span></article>
      <article className="h-card"><strong>{path.counts.transferred}</strong><span>used in a new case</span></article>
      <article className="h-card"><strong>{path.counts.retained_later}</strong><span>retained later</span></article>
    </section>
    {path.next&&<article className="h-card path-next"><div><small>NEXT UP</small><h2>{path.next.title}</h2><p>{path.next.description}</p></div><button className="h-primary" onClick={()=>onStart(path.next.skill_id,path.next.level||'intermediate',path.next.id)}>{path.next.attempts?'Continue':'Start'}</button></article>}
    {path.due_reviews.length>0&&<article className="h-card path-reviews"><h2>Reviews due</h2><p>A new case with different details, to check whether what you showed has lasted.</p><ul>{path.due_reviews.map(item=><li key={item.id}><span>{item.title}<small> · {item.interval_days}-day review</small></span><button className="h-soft" onClick={()=>onStart(item.primary_skill_id,item.proficiency_level||(item.difficulty==='adaptive'?'intermediate':item.difficulty),item.activity_id,{review_id:item.id})}>Start review</button></li>)}</ul></article>}
    {path.units.map(unit=><section className={`h-card path-unit ${unit.unlocked?'':'closed'}`} key={unit.number}><header><div><small>UNIT {unit.number}</small><h2>{unit.title}</h2><p>{unit.summary}</p></div><b>{unit.shown} / {unit.total}</b></header><div className="path-meter" role="progressbar" aria-label={`${unit.title} progress`} aria-valuemin={0} aria-valuemax={unit.total} aria-valuenow={unit.shown}><i style={{width:`${unit.total?unit.shown/unit.total*100:0}%`}}/></div><ul>{unit.lessons.map(lesson=><Lesson key={lesson.id} lesson={lesson} onStart={onStart} current={path.next?.id===lesson.id}/>)}</ul></section>)}
    <details className="h-card path-unit" open><summary><h2>Workplace skills</h2></summary><p>Practise these in any order.</p><ul>{path.workplace.map(lesson=><Lesson key={lesson.id} lesson={lesson} onStart={onStart}/>)}</ul></details>
    <small className="path-note">{path.note}</small>
  </main>
}
