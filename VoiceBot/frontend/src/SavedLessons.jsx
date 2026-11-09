import {useState} from 'react'
import './SavedLessons.css'

export default function SavedLessons({lessons,skills,onResume}) {
  const [expanded,setExpanded]=useState(false),[opening,setOpening]=useState(null),[error,setError]=useState('')
  const active=lessons.filter(lesson=>lesson.status==='active')
  if(!active.length)return null
  const resume=async id=>{
    if(opening)return
    setOpening(id);setError('')
    try{await onResume(id)}catch(error){setError(error.message)}finally{setOpening(null)}
  }
  return <section className="saved-learning" aria-labelledby="saved-learning-title">
    <header><div><p className="saved-learning-eyebrow">PICK UP WHERE YOU LEFT OFF</p><h2 id="saved-learning-title">Continue learning <span>{active.length}</span></h2></div><span className="saved-learning-note">Your conversations are saved</span></header>
    <div id="saved-learning-list" className={`saved-learning-list ${expanded?'expanded':''}`}>
      {(expanded?active:active.slice(0,3)).map(lesson=>{
        const date=new Date(lesson.created_at)
        const skill=skills.find(skill=>skill.id===lesson.skill_id)?.name||lesson.skill_id?.replaceAll('-',' ')
        return <article className="saved-learning-row" key={lesson.id}>
          <span className="saved-learning-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M7 4h10a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3h-6l-5 3v-3a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3Z"/><path d="M7 9h10M7 13h6"/></svg></span>
          <div className="saved-learning-info"><h3>{lesson.title}</h3><div><span>{skill}</span><span className="saved-learning-level">{lesson.difficulty}</span>{!Number.isNaN(date.getTime())&&<time dateTime={lesson.created_at} title={date.toLocaleString()}>Started {date.toLocaleDateString(undefined,{month:'short',day:'numeric'})} · {date.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'})}</time>}</div></div>
          <button className="saved-learning-resume" disabled={!!opening} onClick={()=>resume(lesson.id)} aria-label={`Resume ${lesson.title}`}>{opening===lesson.id?'Opening…':'Resume'}<span aria-hidden="true">↗</span></button>
        </article>
      })}
    </div>
    {active.length>3&&<footer><span>{expanded?active.length:3} of {active.length} saved lessons</span><button aria-expanded={expanded} aria-controls="saved-learning-list" onClick={()=>setExpanded(value=>!value)}>{expanded?'Show fewer':'View all saved lessons'} <span aria-hidden="true">{expanded?'−':'+'}</span></button></footer>}
    {error&&<p className="saved-learning-error" role="alert">{error}</p>}
  </section>
}
