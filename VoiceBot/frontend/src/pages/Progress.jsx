import { StatCard, prettyHours } from '../ui/core'
import { Icon } from '../ui/Icon'
import { PageSkeleton } from '../ui/feedback'
import { ProgressChart } from '../ui/ProgressChart'
import { EmptyArt } from '../ui/EmptyArt'

export function SkillEvidence({ skill }) {
  const observed=Object.entries(skill.subskill_scores||{}).filter(([name])=>(skill.subskill_sessions?.[name]||0)>0)
  return <details className="h-skill-detail"><summary><div className="h-skill-row"><strong>{skill.name}</strong><div><i style={{width:`${skill.sessions?skill.score:0}%`}}/></div><b>{skill.sessions?`${Math.round(skill.score)}%`:'—'}</b></div></summary>
    {skill.sessions&&observed.length?<ul>{observed.map(([name,score])=><li key={name}><span>{name}</span><b>{Math.round(score)}%</b></li>)}</ul>:<p>No subskill evidence recorded yet.</p>}
  </details>
}

export function SessionHistory({ rows=[] }) {
  if(!rows.length)return <EmptyArt kind="chat" title="No lessons yet">Start a lesson to build your history.</EmptyArt>
  return <div className="hk-table-wrap"><table className="hk-table">
    <caption className="sr-only">All your sessions</caption>
    <thead><tr><th scope="col">Lesson</th><th scope="col">Status</th><th scope="col" className="num">Score</th></tr></thead>
    <tbody>{rows.map(row=><tr key={row.id}><td><strong>{row.title}</strong><small>{row.skill_id.replaceAll('-',' ')} · {row.difficulty} · {new Date(row.completed_at||row.created_at).toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'})}</small></td><td><span className={`h-status ${row.status}`}>{row.status==='active'?'In progress':row.status==='canceled'?'Left early':'Completed'}</span></td><td className="num"><b>{row.overall==null?'—':`${Math.round(row.overall)}%`}</b></td></tr>)}</tbody>
  </table></div>
}

export function ProgressPage({ data, history }) {
  if(!data)return <PageSkeleton/>
  return <main className="page hikari-page"><header className="h-page-head"><div><h1>Progress</h1><p>Track your learning journey and see how you’re improving over time.</p></div></header><section className="h-stats"><StatCard icon="target" label="Practice evidence" value={data.completed_sessions?`${Math.round(data.overall)}%`:'Not assessed'}/><StatCard icon="history" label="Completed Sessions" value={data.completed_sessions}/><StatCard icon="clock" label="Total Practice Time" value={prettyHours(data.practice_minutes)}/><StatCard icon="flame" label="Current Streak" value={`${data.current_streak} ${data.current_streak===1?'day':'days'}`}/></section><section className="h-progress-grid"><article className="h-card"><h2>Score over time</h2><p>Your overall score for each completed lesson.</p><ProgressChart points={data.progress_history}/></article><article className="h-card"><h2>Recorded practice evidence</h2><p>Select a skill to see its subskills. These scores describe practice in Hikari, not a certified level.</p>{data.skills.map(skill=><SkillEvidence key={skill.id} skill={skill}/>)}</article><article className="h-card h-history-card"><h2>All sessions</h2><SessionHistory rows={history}/></article><article className="h-card"><h2>Recent Completed Sessions</h2>{data.recent_sessions.length?data.recent_sessions.map(item=><div className="h-session-row" key={item.id}><span><Icon name="check"/></span><div><strong>{item.title}</strong><small>{new Date(item.completed_at).toLocaleDateString()}</small></div><b>{Math.round(item.overall)}%</b></div>):<EmptyArt kind="lantern" title="Nothing finished yet">Finished lessons will show here with their scores.</EmptyArt>}</article><article className="h-card"><h2>Strengths & Focus Areas</h2><div className="h-focus good"><strong>Your Strengths</strong><div className="h-tags">{data.strengths.map(item=><span key={item.id}>{item.name}</span>)}</div></div><div className="h-focus"><strong>Focus Areas</strong><div className="h-tags">{data.focus_areas.map(item=><span key={item.id}>{item.name}</span>)}</div></div></article></section></main>
}
