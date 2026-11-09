import {useCallback,useEffect,useState} from 'react'
import './TeamPanel.css'

export default function TeamPanel({request}){
  const [org,setOrg]=useState(null),[team,setTeam]=useState(null),[code,setCode]=useState(''),[invite,setInvite]=useState(null),[role,setRole]=useState('learner'),[message,setMessage]=useState(''),[error,setError]=useState('')
  const load=useCallback(async()=>{
    try{
      const next=await request('/organization');setOrg(next)
      setTeam(next.can_view_team?await request('/organization/team'):null)
    }catch(e){setError(e.message)}
  },[request])
  useEffect(()=>{load()},[load])
  const post=(path,body)=>request(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  const createInvite=async()=>{try{setError('');setInvite(await post('/organization/invites',{role}))}catch(e){setError(e.message)}}
  const join=async()=>{try{setError('');const out=await post('/organization/join',{code});setCode('');setMessage(`You joined ${out.organization}.`);await load()}catch(e){setError(e.message)}}
  if(!org)return error?<article className="h-card team-panel"><p role="alert">{error}</p></article>:null
  return <article className="h-card team-panel">
    <h2>Your organization</h2>
    <p><strong>{org.organization}</strong> · your role: {org.role} · {org.members} {org.members===1?'member':'members'}</p>
    {org.can_invite&&<div className="team-row"><label>Invite as <select value={role} onChange={e=>setRole(e.target.value)}><option value="learner">Learner</option><option value="trainer">Trainer</option><option value="admin">Administrator</option></select></label><button className="h-soft" onClick={createInvite}>Create invite code</button></div>}
    {invite&&<p className="team-code" role="status">Share this code once: <code>{invite.code}</code>. It works for one person, for {invite.expires_in_days} days.</p>}
    <div className="team-row"><label>Join with a code <input value={code} onChange={e=>setCode(e.target.value)} placeholder="Invite code"/></label><button className="h-soft" disabled={code.trim().length<6} onClick={join}>Join</button></div>
    <small>If you join an organization, its trainers and administrators can see your practice summary: session counts, scores and the skill to practise next. They cannot see your transcripts, recordings or private notes.</small>
    {message&&<p role="status">{message}</p>}
    {error&&<p role="alert">{error}</p>}
    {team&&<section className="team-summary"><h3>Team progress</h3>
      <p>These scores describe practice in Hikari. They are not a measure of job performance and should not be used for hiring or appraisal decisions.</p>
      <div className="team-table" role="table" aria-label="Team progress"><div className="team-head" role="row"><span>Name</span><span>Role</span><span>Sessions</span><span>Average</span><span>Practise next</span></div>
        {team.members.map(m=><div className="team-line" role="row" key={`${m.name}-${m.role}`}><span>{m.name}</span><span>{m.role}</span><span>{m.completed_sessions}</span><span>{m.average==null?'—':`${Math.round(m.average)}%`}</span><span>{m.practice_next||'—'}</span></div>)}
      </div>
      {team.cohort.length>0&&<><h3>Where the team could use support</h3><ul>{team.cohort.slice(0,5).map(item=><li key={item.skill}>{item.skill}: {Math.round(item.average)}% across {item.learners} {item.learners===1?'learner':'learners'}</li>)}</ul></>}
    </section>}
  </article>
}
