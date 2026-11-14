import { StatCard } from '../ui/core'
import { Icon, skillIcon } from '../ui/Icon'
import { PageSkeleton } from '../ui/feedback'
import { EmptyArt } from '../ui/EmptyArt'

function greeting(name) {
  const hour = new Date().getHours()
  const part = hour < 5 ? 'Good evening' : hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
  const first = String(name || '').trim().split(/\s+/)[0]
  return first ? `${part}, ${first}` : part
}

export function HomePage({ data, onStart, setView, savedLessons }) {
  if(!data)return <PageSkeleton/>
  return <main className="page hikari-page"><header className="h-page-head"><div><h1>{greeting(data.user?.name)}</h1><p>Keep practicing and build the skills you need for a stronger tomorrow.</p></div><button className="h-primary" onClick={()=>setView('training')}><Icon name="play"/> Start Training</button></header>
    {savedLessons}
    <section className="h-stats">
      <StatCard icon="target" label="Practice evidence" value={data.completed_sessions?`${Math.round(data.overall)}%`:'Not assessed'} detail="Task evidence, not a certified language level"/>
      <StatCard icon="history" label="Completed Sessions" value={data.completed_sessions} detail={data.completed_sessions?'+ progress saved':'Start your baseline'}/>
      <StatCard icon="sparkles" label="Skills in Progress" value={data.skills_in_progress}/>
      <StatCard icon="flame" label="Current Streak" value={`${data.current_streak} ${data.current_streak===1?'day':'days'}`} detail={data.current_streak>1?'Great consistency!':data.current_streak?'Good start. Come back tomorrow.':'Complete a session today'}/>
    </section>
    <section className="h-home-grid"><article className="h-card h-skills"><div className="h-card-title"><h2>Your Skills</h2><button onClick={()=>setView('progress')}>View All ›</button></div>{data.skills.slice(0,5).map(skill=><div className="h-skill-row" key={skill.id}><span>{skill.name.slice(0,1)}</span><strong>{skill.name}</strong><div><i style={{width:`${skill.sessions?skill.score:0}%`}}/></div><b>{skill.sessions?`${Math.round(skill.score)}%`:'—'}</b></div>)}</article>
      <article className="h-card h-recommended"><h2>Recommended Next Activity</h2><div className="h-feature"><span className="feature-icon"><Icon name={skillIcon(data.recommendation.skill_id||data.recommendation.activity_id)}/></span><h3>{data.recommendation.skill}</h3><p>{data.recommendation.reason}</p><div className="h-tags"><span>{data.recommendation.skill}</span><span>{data.recommendation.difficulty}</span></div><button className="h-primary" onClick={()=>onStart(data.recommendation.skill_id,data.recommendation.difficulty,data.recommendation.activity_id)}><Icon name="play"/> Start Activity</button></div></article>
      <article className="h-card"><div className="h-card-title"><h2>Recent Sessions</h2><button onClick={()=>setView('progress')}>View All ›</button></div>{data.recent_sessions.length?data.recent_sessions.slice(0,3).map(item=><div className="h-session-row" key={item.id}><span><Icon name="check"/></span><div><strong>{item.title}</strong><small>{new Date(item.completed_at).toLocaleDateString()}</small></div><b>{Math.round(item.overall)}%</b></div>):<EmptyArt kind="lantern" title="Your first light">Complete a lesson and your results appear here.</EmptyArt>}</article>
      <article className="h-card"><div className="h-card-title"><h2>Your Training Plan</h2><button onClick={()=>setView('plan')}>View Plan</button></div>{data.plan.map((item,index)=><button className="h-plan-row" key={item.skill_id} onClick={()=>onStart(item.skill_id,item.difficulty==='adaptive'?'intermediate':(item.difficulty||'beginner'),item.activity_id)}><span>{index+1}</span><div><strong>{item.activity}</strong><small>Focus on {item.focus}</small></div><i><Icon name="chevronRight"/></i></button>)}</article>
    </section>
  </main>
}
