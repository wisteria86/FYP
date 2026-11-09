import {useCallback,useEffect,useState} from 'react'
import './TeamPanel.css'

export default function GoalsPanel({request,onChanged}){
  const [goals,setGoals]=useState([]),[skills,setSkills]=useState([]),[title,setTitle]=useState(''),[skillId,setSkillId]=useState(''),[targetDate,setTargetDate]=useState(''),[error,setError]=useState('')
  const load=useCallback(async()=>{
    try{const [nextGoals,nextSkills]=await Promise.all([request('/goals'),request('/skills')]);setGoals(nextGoals);setSkills(nextSkills)}
    catch(e){setError(e.message)}
  },[request])
  useEffect(()=>{load()},[load])
  const add=async event=>{
    event.preventDefault()
    try{
      setError('')
      await request('/goals',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,skill_id:skillId||null,target_date:targetDate||null})})
      setTitle('');setSkillId('');setTargetDate('');await load();await onChanged?.()
    }catch(e){setError(e.message)}
  }
  const finish=async id=>{try{setError('');await request(`/goals/${id}/close`,{method:'POST'});await load();await onChanged?.()}catch(e){setError(e.message)}}
  const nameOf=id=>skills.find(skill=>skill.id===id)?.name
  return <article className="h-card team-panel">
    <h2>Your training goals</h2>
    <p>Goals linked to a skill come first in your training plan after your next completed lesson.</p>
    {goals.length?<ul className="goal-list">{goals.map(goal=><li key={goal.id}><div><strong>{goal.title}</strong><small>{[nameOf(goal.skill_id),goal.target_date&&`by ${goal.target_date}`].filter(Boolean).join(' · ')||'No skill linked'}</small></div><button className="h-soft" onClick={()=>finish(goal.id)}>Mark done</button></li>)}</ul>:<p>No goals yet.</p>}
    <form className="team-row" onSubmit={add}>
      <label>Goal <input value={title} maxLength={160} required onChange={e=>setTitle(e.target.value)} placeholder="Prepare for my promotion interview"/></label>
      <label>Skill <select value={skillId} onChange={e=>setSkillId(e.target.value)}><option value="">No specific skill</option>{skills.map(skill=><option key={skill.id} value={skill.id}>{skill.name}</option>)}</select></label>
      <label>Target date <input type="date" value={targetDate} onChange={e=>setTargetDate(e.target.value)}/></label>
      <button className="h-soft" disabled={!title.trim()}>Add goal</button>
    </form>
    {error&&<p role="alert">{error}</p>}
  </article>
}
