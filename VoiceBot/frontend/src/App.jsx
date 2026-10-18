import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import './Monitor.css'
import Administration from './Administration'
import VoiceInputTest from './VoiceInputTest'
import SessionAudioSettings from './SessionAudioSettings'
import {loadSessionAudio,saveSessionAudio,sessionAudioMode} from './sessionAudio.mjs'
import {createInputLevel} from './inputLevel.mjs'
import {CaptureClock} from './captureClock.mjs'
import { IncrementalTranscriber } from './incrementalTranscriber.mjs'
import { StreamingTranscriber } from './streamingTranscriber.mjs'
import { listMicrophones, microphoneConstraints } from './micDevices.mjs'
import { createCleanCapture } from './noiseReduction.mjs'
import {turnDetection,captureLimitReason} from './turnEnding.mjs'
import { startSilero } from './sileroVad.mjs'
import { monitorMicrophone } from './micMonitor.mjs'

const API = '/api'
const api = async (path, options = {}) => {
  const response = await fetch(`${API}${path}`, {credentials:'same-origin',...options})
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error=new Error(data.error?.message||data.detail||'Something went wrong')
    error.status=response.status
    throw error
  }
  return data
}

const Icon = ({ name }) => {
  const paths = {
    dashboard: <><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></>,
    practice: <><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3"/></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></>,
    docs: <><path d="M6 2h9l4 4v16H6z"/><path d="M14 2v5h5M9 12h7M9 16h7"/></>,
    monitor: <><path d="M3 3v18h18"/><path d="m6 16 4-5 3 3 5-8"/><path d="M17 6h1v1"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1z"/></>,
    send: <><path d="M22 2 11 13"/><path d="m22 2-7 20-4-9-9-4z"/></>,
    camera: <><path d="M14.5 4 16 7h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h3l1.5-3z"/><circle cx="12" cy="13" r="3"/></>,
    speaker: <><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></>,
    stop: <><rect x="6" y="6" width="12" height="12" rx="2"/></>,
    check: <><polyline points="20 6 9 17 4 12"/></>,
    sparkles: <><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z"/></>,
  }
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

function AuthScreen({ onAuthenticated }) {
  const [mode,setMode]=useState('login'),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const [form,setForm]=useState({name:'',email:'',password:'',organization_name:''})
  const submit=async event=>{
    event.preventDefault();setBusy(true);setError('')
    try{
      const body=mode==='login'?{email:form.email,password:form.password}:form
      const result=await api(`/auth/${mode}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
      await onAuthenticated(result.user)
    }catch(e){setError(e.message)}finally{setBusy(false)}
  }
  const update=event=>setForm(value=>({...value,[event.target.name]:event.target.value}))
  return <main className="auth-page"><section className="auth-intro"><div className="auth-brand">✦ <strong>Hikari</strong></div><p>AI-powered workplace training</p><h1>Practise difficult conversations before they happen.</h1><span>Private progress, adaptive scenarios, and realistic voice roleplay in one training workspace.</span></section><section className="auth-panel"><div className="auth-card"><p className="eyebrow">{mode==='login'?'WELCOME BACK':'CREATE YOUR WORKSPACE'}</p><h2>{mode==='login'?'Sign in to Hikari':'Start training with Hikari'}</h2><p>Your progress and sessions stay connected to your account.</p><form onSubmit={submit}>{mode==='register'&&<><label>Full name<input name="name" value={form.name} onChange={update} autoComplete="name" required/></label><label>Organization<input name="organization_name" value={form.organization_name} onChange={update} autoComplete="organization" required/></label></>}<label>Email address<input name="email" type="email" value={form.email} onChange={update} autoComplete="email" required/></label><label>Password<input name="password" type="password" value={form.password} onChange={update} autoComplete={mode==='login'?'current-password':'new-password'} minLength={mode==='register'?10:1} required/></label>{mode==='register'&&<small>Use at least 10 characters with a letter and a number.</small>}{error&&<div className="auth-error">{error}</div>}<button className="h-primary" disabled={busy}>{busy?'Please wait…':mode==='login'?'Sign in':'Create account'}</button></form><button className="auth-switch" onClick={()=>{setMode(value=>value==='login'?'register':'login');setError('')}}>{mode==='login'?'New to Hikari? Create an account':'Already have an account? Sign in'}</button></div></section></main>
}

function Sidebar({ view, setView, health, user, onLogout }) {
  const nav = [
    ['home', 'Home', 'dashboard'],
    ['training', 'Training', 'practice'],
    ['progress', 'Progress', 'history'],
    ['plan', 'Training Plan', 'docs'],
    ['resources', 'Resources', 'docs'],
    ['settings', 'Settings', 'settings'],
  ]
  return <aside className="sidebar">
    <div className="brand"><span className="brand-mark">✦</span><div><strong>Hikari</strong></div></div>
    <nav>{nav.map(([id, label, icon]) => <button key={id} className={view === id ? 'active' : ''} onClick={() => setView(id)}><Icon name={icon}/>{label}</button>)}</nav>
    <div className="profile"><span>{(user?.name||'User').slice(0,1)}</span><div><strong>{user?.name||'User'}</strong><small>{health.status==='ready'?'Voice ready':'Limited mode'}</small></div><button onClick={onLogout} title="Sign out">↪</button></div>
  </aside>
}

function ScoreRing({ score, size = 116 }) {
  const r = 45, c = 2 * Math.PI * r
  return <div className="score-ring" style={{ width: size, height: size }}>
    <svg viewBox="0 0 110 110"><circle className="ring-base" cx="55" cy="55" r={r}/><circle className="ring-value" cx="55" cy="55" r={r} strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)}/></svg>
    <div><strong>{Math.round(score)}</strong><small>/100</small></div>
  </div>
}

function Dashboard({ data, onStart, setView, health }) {
  if (!data) return <Loading/>
  const engineLabel = health?.engine ? (health.engine === 'kokoro' ? 'Kokoro ONNX (Default)' : health.engine.toUpperCase()) : 'Kokoro ONNX (Default)'
  return <main className="page">
    <header className="page-head">
      <div>
        <p className="eyebrow">YOUR TRAINING SPACE</p>
        <h1>Welcome back, {data.user.name.split(' ')[0]}</h1>
        <p>Build confidence through short, realistic workplace conversations.</p>
      </div>
      <div className="header-actions">
        <button className="settings-trigger-btn" onClick={() => setView('settings')} title="Configure TTS Engine & Voices">
          <Icon name="settings"/> Voice: {engineLabel}
        </button>
        <button className="primary" onClick={() => setView('practice')}>Start practice</button>
      </div>
    </header>
    <div className="dashboard-tts-banner">
      <div className="tts-banner-left">
        <span className="live-dot ready"/>
        <div>
          <strong>Speech Engine: {engineLabel}</strong>
          <small>Sub-second neural voice synthesis active for real-time roleplays ({health?.sample_rate ? `${health.sample_rate/1000} kHz` : '24 kHz'}).</small>
        </div>
      </div>
      <button className="text-action-btn" onClick={() => setView('settings')}>
        Change Voice Settings →
      </button>
    </div>
    <section className="overview-grid">
      <article className="overall-card"><div><p className="label">Overall proficiency</p><h2>{data.completed_sessions ? 'Building momentum' : 'Ready for baseline'}</h2><p>{data.completed_sessions ? `${data.completed_sessions} completed session${data.completed_sessions === 1 ? '' : 's'}` : 'Complete your first scenario to establish a score.'}</p></div><ScoreRing score={data.overall}/></article>
      <article className="recommend-card"><div className="card-kicker">RECOMMENDED NEXT</div><h2>{data.recommendation.skill}</h2><p>{data.recommendation.reason}</p><div className="rec-footer"><span>{data.recommendation.difficulty}</span><button onClick={() => onStart(data.recommendation.skill_id, data.recommendation.difficulty,data.recommendation.activity_id)}>Practise now →</button></div></article>
    </section>
    <section className="section"><div className="section-title"><div><p className="eyebrow">SKILL MAP</p><h2>Your capabilities</h2></div><button className="text-button" onClick={() => setView('practice')}>View all</button></div>
      <div className="skill-grid">{data.skills.slice(0, 6).map(skill => <article className="skill-card" key={skill.id}><div className="skill-top"><span className="skill-glyph">{skill.name.slice(0,1)}</span><span className="skill-score">{Math.round(skill.score)}</span></div><h3>{skill.name}</h3><p>{skill.description}</p><div className="progress"><i style={{width: `${skill.score}%`}}/></div><small>{skill.sessions ? `${skill.sessions} session${skill.sessions > 1 ? 's' : ''}` : 'Not practised yet'}</small></article>)}</div>
    </section>
    <section className="section split"><div><p className="eyebrow">THREE-SESSION PLAN</p><h2>Focused practice</h2><div className="plan-list">{data.plan.map((item, i) => <button key={item.day} onClick={() => onStart(item.skill_id, i ? 'intermediate' : 'beginner')}><span>{i + 1}</span><div><strong>{item.activity}</strong><small>Focus: {item.focus}</small></div><b>→</b></button>)}</div></div><div><p className="eyebrow">RECENT RESULTS</p><h2>Session history</h2>{data.recent_sessions.length ? <div className="result-list">{data.recent_sessions.slice(0,3).map(s => <div key={s.id}><span>{s.title.slice(0,1)}</span><div><strong>{s.title}</strong><small>{s.skill_id.replaceAll('-', ' ')}</small></div><b>{Math.round(s.overall)}</b></div>)}</div> : <div className="empty-panel">Your completed roleplays will appear here.</div>}</div></section>
  </main>
}

function Practice({ skills, onStart }) {
  const [difficulty, setDifficulty] = useState('intermediate')
  return <main className="page"><header className="page-head compact"><div><p className="eyebrow">SCENARIO LIBRARY</p><h1>Choose what to practise</h1><p>Every roleplay adapts to your current proficiency and recent results.</p></div><div className="difficulty">{['beginner','intermediate','advanced'].map(x => <button className={difficulty === x ? 'active' : ''} onClick={() => setDifficulty(x)} key={x}>{x}</button>)}</div></header>
    <div className="catalog">{skills.map((skill, i) => <article key={skill.id}><div className="catalog-number">{String(i + 1).padStart(2,'0')}</div><div><h2>{skill.name}</h2><p>{skill.description}</p><div className="tags">{skill.subskills.map(x => <span key={x}>{x}</span>)}</div></div><div className="catalog-action"><strong>{Math.round(skill.score)}</strong><small>proficiency</small><button onClick={() => onStart(skill.id, difficulty)}>Start →</button></div></article>)}</div>
  </main>
}

const prettyHours = minutes => minutes >= 60 ? `${(minutes/60).toFixed(1)} hours` : `${Math.round(minutes)} min`

function StatCard({ icon, label, value, detail }) {
  return <article className="h-stat"><span><Icon name={icon}/></span><div><small>{label}</small><strong>{value}</strong>{detail&&<em>{detail}</em>}</div></article>
}

function HomePage({ data, onStart, setView }) {
  if(!data)return <Loading/>
  return <main className="page hikari-page"><header className="h-page-head"><div><h1>Good morning!</h1><p>Keep practicing and build the skills you need for a stronger tomorrow.</p></div><button className="h-primary" onClick={()=>setView('training')}>▶ Start Training</button></header>
    <section className="h-stats">
      <StatCard icon="monitor" label="Overall Proficiency" value={`${Math.round(data.overall)}%`}/>
      <StatCard icon="history" label="Completed Sessions" value={data.completed_sessions} detail={data.completed_sessions?'+ progress saved':'Start your baseline'}/>
      <StatCard icon="sparkles" label="Skills in Progress" value={data.skills_in_progress}/>
      <StatCard icon="history" label="Current Streak" value={`${data.current_streak} days`} detail={data.current_streak?'Great consistency!':'Complete a session today'}/>
    </section>
    <section className="h-home-grid"><article className="h-card h-skills"><div className="h-card-title"><h2>Your Skills</h2><button onClick={()=>setView('progress')}>View All ›</button></div>{data.skills.slice(0,5).map(skill=><div className="h-skill-row" key={skill.id}><span>{skill.name.slice(0,1)}</span><strong>{skill.name}</strong><div><i style={{width:`${skill.score}%`}}/></div><b>{Math.round(skill.score)}%</b></div>)}</article>
      <article className="h-card h-recommended"><h2>Recommended Next Activity</h2><div className="h-feature"><span className="feature-icon">♟</span><h3>{data.recommendation.skill}</h3><p>{data.recommendation.reason}</p><div className="h-tags"><span>{data.recommendation.skill}</span><span>{data.recommendation.difficulty}</span></div><button className="h-primary" onClick={()=>onStart(data.recommendation.skill_id,data.recommendation.difficulty,data.recommendation.activity_id)}>▶ Start Activity</button></div></article>
      <article className="h-card"><div className="h-card-title"><h2>Recent Sessions</h2><button onClick={()=>setView('progress')}>View All ›</button></div>{data.recent_sessions.length?data.recent_sessions.slice(0,3).map(item=><div className="h-session-row" key={item.id}><span>✓</span><div><strong>{item.title}</strong><small>{new Date(item.completed_at).toLocaleDateString()}</small></div><b>{Math.round(item.overall)}%</b></div>):<div className="h-empty">Complete a training activity to see results here.</div>}</article>
      <article className="h-card"><div className="h-card-title"><h2>Your Training Plan</h2><button onClick={()=>setView('plan')}>View Plan</button></div>{data.plan.map((item,index)=><button className="h-plan-row" key={item.skill_id} onClick={()=>onStart(item.skill_id,item.difficulty==='adaptive'?'intermediate':(item.difficulty||'beginner'),item.activity_id)}><span>{index+1}</span><div><strong>{item.activity}</strong><small>Focus on {item.focus}</small></div><i>{'○'}</i></button>)}</article>
    </section>
  </main>
}

function TrainingPage({ activities, onStart }) {
  const [query,setQuery]=useState(''),[category,setCategory]=useState('All'),[language,setLanguage]=useState('All languages')
  const roleplayLabels={one_to_one:'1-to-1 AI',learner_with_ai_team:'You + AI vs AI',ai_team_vs_learner:'AI Team vs You',round_robin:'Round Robin'}
  const multiCategory='Multiple AI Roleplay'
  const categories=['All',...new Set(activities.map(item=>item.skill_name)),multiCategory,'You + AI vs AI','AI Team vs You','Round Robin']
  const languages=['All languages',...new Set(activities.map(item=>item.training_language).filter(Boolean))]
  const filtered=activities.filter(item=>{
    const matchesCategory=category==='All'||category===item.skill_name||(category===multiCategory&&item.scenario_type==='multi_ai_roleplay')||category===roleplayLabels[item.roleplay_mode]
    const matchesLanguage=language==='All languages'||item.training_language===language
    return matchesCategory&&matchesLanguage&&`${item.title} ${item.description} ${item.subskills.join(' ')}`.toLowerCase().includes(query.toLowerCase())
  })
  return <main className="page hikari-page"><header className="h-page-head"><div><h1>Training</h1><p>Practice languages, workplace communication, negotiation, interviews, critical thinking, and more.</p></div></header><div className="h-search"><span>⌕</span><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search training activities…"/></div><div className="h-filter-row language-filters">{languages.map(item=><button key={item} className={language===item?'active':''} onClick={()=>setLanguage(item)}>{item}</button>)}</div><div className="h-filter-row">{categories.map(item=><button key={item} className={category===item?'active':''} onClick={()=>setCategory(item)}>{item}</button>)}</div><section className="h-training-grid">{filtered.map(item=><article className="h-training-card" key={item.id}><span className="training-icon">◉</span>{item.sequence_number&&<small>ENGLISH {item.sequence_number} / 30</small>}<h2>{item.title}</h2><p>{item.description}</p><div className="training-meta"><span>◷ {item.estimated_minutes} min</span><span>▥ {item.proficiency_level||item.difficulty}</span></div><div className="h-tags">{item.training_language&&<span>{item.training_language}</span>}<span>{item.skill_name}</span><span>{roleplayLabels[item.roleplay_mode]||'AI Roleplay'}</span>{item.subskills.slice(0,1).map(tag=><span key={tag}>{tag}</span>)}</div><button className="h-primary" onClick={()=>onStart(item.primary_skill_id,item.difficulty==='adaptive'?'intermediate':item.difficulty,item.id)}>▶ Start Training</button></article>)}</section></main>
}

function ProgressChart({ points }) {
  const values=points.map(item=>Number(item.overall)); if(!values.length)return <div className="h-chart-empty">Your progress chart will appear after your first completed session.</div>
  const coords=values.map((value,index)=>`${30+index*(700/Math.max(values.length-1,1))},${190-value*1.5}`).join(' ')
  return <svg className="h-progress-chart" viewBox="0 0 760 220"><line x1="30" y1="190" x2="730" y2="190"/><line x1="30" y1="40" x2="730" y2="40"/><polyline points={coords}/>{values.map((value,index)=><circle key={index} cx={30+index*(700/Math.max(values.length-1,1))} cy={190-value*1.5} r="5"/>)}</svg>
}

function ProgressPage({ data }) {
  if(!data)return <Loading/>
  return <main className="page hikari-page"><header className="h-page-head"><div><h1>Progress</h1><p>Track your learning journey and see how you’re improving over time.</p></div></header><section className="h-stats"><StatCard icon="monitor" label="Overall Progress" value={`${Math.round(data.overall)}%`}/><StatCard icon="history" label="Completed Sessions" value={data.completed_sessions}/><StatCard icon="sparkles" label="Total Practice Time" value={prettyHours(data.practice_minutes)}/><StatCard icon="history" label="Current Streak" value={`${data.current_streak} days`}/></section><section className="h-progress-grid"><article className="h-card"><h2>Weekly Improvement</h2><p>Performance from your stored assessments.</p><ProgressChart points={data.progress_history}/></article><article className="h-card"><h2>Skill Proficiency</h2>{data.skills.slice(0,6).map(skill=><div className="h-skill-row" key={skill.id}><strong>{skill.name}</strong><div><i style={{width:`${skill.score}%`}}/></div><b>{Math.round(skill.score)}%</b></div>)}</article><article className="h-card"><h2>Recent Completed Sessions</h2>{data.recent_sessions.length?data.recent_sessions.map(item=><div className="h-session-row" key={item.id}><span>✓</span><div><strong>{item.title}</strong><small>{new Date(item.completed_at).toLocaleDateString()}</small></div><b>{Math.round(item.overall)}%</b></div>):<div className="h-empty">No completed sessions yet.</div>}</article><article className="h-card"><h2>Strengths & Focus Areas</h2><div className="h-focus good"><strong>Your Strengths</strong><div className="h-tags">{data.strengths.map(item=><span key={item.id}>{item.name}</span>)}</div></div><div className="h-focus"><strong>Focus Areas</strong><div className="h-tags">{data.focus_areas.map(item=><span key={item.id}>{item.name}</span>)}</div></div></article></section></main>
}

function PlanPage({ data, onStart }) {
  if(!data)return <Loading/>
  const completed=(data.persistent_plan?.activities||[]).filter(item=>item.status==='completed').length
  return <main className="page hikari-page"><header className="h-page-head"><div><h1>Training Plan</h1><p>A personalized plan to help you build the skills you need for a stronger tomorrow.</p></div></header><section className="h-plan-summary"><article className="h-card"><small>Current Goal</small><h2>Improve {data.focus_areas[0]?.name||'Professional Communication'}</h2><p>Build confidence through focused practice and measurable feedback.</p></article><article className="h-card"><small>Plan Progress</small><h2>{Math.round(completed/Math.max(completed+data.plan.length,1)*100)}%</h2><div className="h-bar"><i style={{width:`${completed/Math.max(completed+data.plan.length,1)*100}%`}}/></div><p>{completed} / {completed+data.plan.length} activities completed</p></article></section><section className="h-progress-grid"><article className="h-card h-roadmap"><h2>Your Recommended Roadmap</h2>{data.plan.map((item,index)=><button key={item.skill_id} onClick={()=>onStart(item.skill_id,item.difficulty==='adaptive'?'intermediate':(item.difficulty||'beginner'),item.activity_id)}><span>{index+1}</span><div><strong>{item.activity}</strong><small>Develop {item.focus}</small></div><b>Week {index*2+1}–{index*2+2}</b></button>)}</article><article className="h-card"><h2>Upcoming Activities</h2>{data.plan.map((item,index)=><div className="h-session-row" key={item.skill_id}><span>›</span><div><strong>{item.activity}</strong><small>{item.focus} · 15 min</small></div>{index===0&&<button className="h-small" onClick={()=>onStart(item.skill_id,item.difficulty==='adaptive'?'intermediate':(item.difficulty||'beginner'),item.activity_id)}>▶ Start</button>}</div>)}</article></section></main>
}

function ResourcesPage({ resources, docs, reload }) {
  const [query,setQuery]=useState(''),[category,setCategory]=useState('All'),[selected,setSelected]=useState(null)
  const filtered=resources.filter(item=>(category==='All'||item.resource_type===category)&&`${item.title} ${item.description}`.toLowerCase().includes(query.toLowerCase()))
  return <main className="page hikari-page"><header className="h-page-head"><div><h1>Resources</h1><p>Explore guides, templates, and practical materials to support your learning journey.</p></div></header><div className="h-search"><span>⌕</span><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search resources…"/></div><div className="h-filter-row">{['All','guide','checklist','video','article','template'].map(item=><button key={item} className={category===item?'active':''} onClick={()=>setCategory(item)}>{item}</button>)}</div>{filtered[0]&&<article className="h-resource-feature"><small>FEATURED RESOURCE</small><h2>{filtered[0].title}</h2><p>{filtered[0].description}</p><button className="h-primary" onClick={()=>setSelected(filtered[0])}>Open Resource</button></article>}<div className="h-card-title"><h2>Resource Library</h2><span>{filtered.length} resources</span></div><section className="h-resource-grid">{filtered.map(item=><article className="h-resource-card" key={item.id}><span>▤</span><div><h3>{item.title}</h3><p>{item.description}</p><small>{item.resource_type}</small></div><button onClick={()=>setSelected(item)}>Open</button></article>)}</section><details className="h-knowledge"><summary>Company knowledge documents ({docs.length})</summary><Documents docs={docs} reload={reload}/></details>{selected&&<div className="resource-modal" onClick={()=>setSelected(null)}><article onClick={event=>event.stopPropagation()}><button className="resource-close" onClick={()=>setSelected(null)}>×</button><small>{selected.resource_type}</small><h2>{selected.title}</h2><p>{selected.content_text||selected.description}</p>{selected.skills&&<div className="h-tags">{selected.skills.split(', ').map(skill=><span key={skill}>{skill}</span>)}</div>}</article></div>}</main>
}

function SettingsHub({ dashboard, health, setView, onChanged }) {
  const [mic,setMic]=useState('Not tested'),[camera,setCamera]=useState('Not tested')
  const [name,setName]=useState(dashboard?.user.name||'')
  const [message,setMessage]=useState(''),[saving,setSaving]=useState(false)
  const [currentPassword,setCurrentPassword]=useState(''),[newPassword,setNewPassword]=useState('')
  const testMic=async()=>{try{const stream=await navigator.mediaDevices.getUserMedia({audio:microphoneConstraints()});setMic(stream.getAudioTracks()[0]?.label||'Microphone ready');stream.getTracks().forEach(track=>track.stop())}catch(e){setMic(`Unavailable: ${e.message}`)}}
  const testCamera=async()=>{try{const stream=await navigator.mediaDevices.getUserMedia({video:true});setCamera(stream.getVideoTracks()[0]?.label||'Camera ready');stream.getTracks().forEach(track=>track.stop())}catch(e){setCamera(`Unavailable: ${e.message}`)}}
  const save=async()=>{setSaving(true);try{setMessage('Saving…');await api('/auth/profile',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});await onChanged();setMessage('Profile saved.')}catch(error){setMessage(error.message)}finally{setSaving(false)}}
  const changePassword=async()=>{setSaving(true);try{setMessage('Updating password…');await api('/auth/password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:currentPassword,new_password:newPassword})});setCurrentPassword('');setNewPassword('');setMessage('Password updated.')}catch(error){setMessage(error.message)}finally{setSaving(false)}}
  return <main className="page hikari-page settings-hub">
    <header className="h-page-head"><div><h1>Settings</h1><p>Manage your profile, devices, language preferences, and speech engines.</p></div><button className="h-primary" onClick={save} disabled={saving||name.trim().length<2}>{saving?'Saving…':'Save Profile'}</button></header>
    {message&&<div className="notice" role="status">{message}</div>}
    <section className="h-settings-grid" aria-label="Profile and device settings">
      <article className="h-card"><h2>Profile</h2><label>Full Name<input value={name} onChange={event=>setName(event.target.value)}/></label><label>Email<input value={dashboard?.user.email||''} readOnly/></label><label>Organization<input value={dashboard?.user.organization||'Hikari'} readOnly/></label></article>
      <article className="h-card"><h2>Account</h2><label>Current Password<input type="password" autoComplete="current-password" value={currentPassword} onChange={event=>setCurrentPassword(event.target.value)}/></label><label>New Password<input type="password" autoComplete="new-password" value={newPassword} minLength="10" onChange={event=>setNewPassword(event.target.value)}/></label><button className="h-soft" onClick={changePassword} disabled={saving||!currentPassword||newPassword.length<10}>Change Password</button></article>
      <article className="h-card"><h2>Audio & Microphone</h2><p>{mic}</p><button className="h-soft" onClick={testMic}>Test Microphone</button><small>Voice engine: {health.engine||'loading'} · Recognition: {health.stt_runtime?.model||'loading'}</small><button className="h-soft" onClick={()=>setView('monitor')}>Open testing monitor</button></article>
      <article className="h-card"><h2>Camera & Permissions</h2><p>{camera}</p><button className="h-soft" onClick={testCamera}>Test Camera</button><small>Camera analysis is optional and limited to posture indicators.</small></article>
    </section>
    <Settings onChanged={onChanged} embedded/>
  </main>
}

function ScenarioPreparation({ briefing, onBegin, onCancel, busy, documents=[], onConfigure }) {
  const isGroup=briefing.scenario_type==='multi_ai_roleplay'
  const learning=briefing.learning_design
  return <main className="prep-page">
    <header className="prep-header"><button onClick={onCancel}>← Back to training</button><div><span>✦</span><strong>Hikari Training</strong></div></header>
    <section className="prep-hero"><p className="eyebrow">SCENARIO PREPARATION</p><h1>{briefing.title}</h1><p>{briefing.description}</p><div className="prep-badges"><span>{briefing.difficulty}</span><span>{briefing.estimated_minutes} minutes</span><span>{isGroup?'Multiple AI Roleplay':'1-to-1 AI Roleplay'}</span></div><p>{briefing.adaptation_reason}</p></section>
    <section className="prep-grid"><article><small>YOUR ROLE</small><h2>{briefing.learner_role}</h2><p>{briefing.situation}</p></article>
      <article><small>PARTICIPANTS</small><h2>{briefing.participants.length} AI {briefing.participants.length===1?'participant':'participants'}</h2><div className="prep-people">{briefing.participants.map(person=><span key={person}>● {person}</span>)}</div></article>
      <article className="prep-objectives"><small>YOUR OBJECTIVES</small><h2>What to practise</h2><ol>{briefing.objectives.map(item=><li key={item}>{item}</li>)}</ol>{briefing.previous_feedback?.map(item=><p key={item}>{item}</p>)}</article>
      <article><small>{learning?'LANGUAGE TOOLKIT':'TARGET SKILL'}</small><h2>{learning?.focus||briefing.target_skill}</h2>{learning?<><p>{learning.grammar}</p><div className="h-tags">{learning.vocabulary.map(item=><span key={item}>{item}</span>)}</div><div className="prep-models">{learning.examples.map(item=><p key={item}>“{item}”</p>)}</div></>:<div className="h-tags">{briefing.subskills.map(item=><span key={item}>{item}</span>)}</div>}<p className="prep-note">Practise the objectives with your own information. If a target is missing, the lesson continues with guidance.</p></article>
      <article><h2>Lesson capabilities</h2>{briefing.posture_mode==='optional'?<label><input type="checkbox" checked={briefing.posture_enabled} disabled={busy} onChange={event=>onConfigure({posture_enabled:event.target.checked})}/> Optional posture assessment (camera consent required)</label>:<p>Posture assessment is not used for this lesson. Camera video alone does not affect your score.</p>}
        {briefing.knowledge_mode!=='off'&&<><h3>Company knowledge {briefing.knowledge_mode==='required'?'— required':'— optional'}</h3><p>Select the documents this attempt may use. Excerpts may be sent to your configured AI provider.</p>{documents.filter(item=>item.status==='ready').map(doc=><label className="lesson-document" key={doc.id}><input type="checkbox" checked={briefing.document_ids?.includes(doc.id)} disabled={busy} onChange={event=>onConfigure({document_ids:event.target.checked?[...(briefing.document_ids||[]),doc.id]:(briefing.document_ids||[]).filter(id=>id!==doc.id)})}/>{doc.name}</label>)}{!documents.length&&<p>Upload authorized documents from Resources before using company-knowledge training.</p>}</>}
      </article></section>
    <footer className="prep-actions"><button onClick={onCancel}>Choose another lesson</button><button className="h-primary" onClick={onBegin} disabled={busy}>{busy?'Preparing session…':'Join training session →'}</button></footer>
  </main>
}

function SourceEvidence({sources=[]}) {
  return sources.length?<details className="source-evidence"><summary>Policy sources ({sources.length})</summary>{sources.map((source,index)=><blockquote key={`${source.document_id||source.name}-${index}`}><strong>{source.name}</strong><p>{source.excerpt||source.text}</p></blockquote>)}</details>:null
}

function Roleplay({ session, setSession, onComplete, onCancel, health, onOpenSettings, userSettings }) {
  const [mode, setMode] = useState('voice')
  const [callActive, setCallActive] = useState(false)
  const [muted, setMuted] = useState(false)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [recording, setRecording] = useState(false)
  const [capturePaused,setCapturePaused]=useState(false)
  const [voiceDraft,setVoiceDraft]=useState(null)
  const voiceDraftRef=useRef(null),reviewSending=useRef(false)
  const [micState, setMicState] = useState('idle')
  const [micLevel, setMicLevel] = useState(0)
  const [micDevice, setMicDevice] = useState('No microphone selected')
  const [voiceState, setVoiceState] = useState('idle')
  const [activeSpeaker, setActiveSpeaker] = useState(null)
  const [sessionProgress, setSessionProgress] = useState(null)
  const [audioPanelOpen,setAudioPanelOpen]=useState(false)
  const audioPanelRef=useRef(null),audioButtonRef=useRef(null)
  const [micOptions, setMicOptions] = useState([])
  const [sessionAudio,setSessionAudio]=useState(()=>loadSessionAudio(localStorage))
  const automaticTurnEnd=sessionAudio.inputMode==='auto'
  const audioMode=sessionAudioMode(sessionAudio)
  const micLevelGraph=useRef(null)
  const micDenoiser=useRef(null)
  const micVad=useRef(null)
  const [micListError,setMicListError]=useState('')
  const [micRefreshing,setMicRefreshing]=useState(false)
  const [selectedMic, setSelectedMic] = useState(()=>loadSessionAudio(localStorage).deviceId)
  const [camera, setCamera] = useState(false)
  const [captions, setCaptions] = useState(userSettings?.captions_enabled??true)
  const [elapsed, setElapsed] = useState(0)
  const [posture, setPosture] = useState(null)
  const [postureReason,setPostureReason]=useState('Enable your camera and keep your head, shoulders and hips visible.')
  const recorder = useRef(null), chunks = useRef([]), started = useRef(0), video = useRef(null), media = useRef(null), chatEnd = useRef(null)
  const playbackContext = useRef(null), playbackTail = useRef(0)
  const playbackSources = useRef(new Set())
  const voiceRequest = useRef(null)
  const sending = useRef(false)
  const incrementalCapture = useRef(null)
  const streamingCapture = useRef(null)
  const micStarting = useRef(false)
  const lastCapture = useRef(null)
  const latencyTrial = useRef(null)
  const callActiveRef = useRef(false), mutedRef = useRef(false), modeRef = useRef('voice'), beginListening = useRef(null), discardCapture = useRef(false)
  const micStream = useRef(null), micContext = useRef(null), micFrame = useRef(null), speechSeen = useRef(false), lastSpeech = useRef(0), peakLevel = useRef(0), lastLevelReport = useRef(0), noiseFloor = useRef(.003)
  useEffect(() => { chatEnd.current?.scrollIntoView({behavior:'smooth'}) }, [session.turns, busy])
  useEffect(()=>{const update=()=>setElapsed(Math.max(0,Math.floor((Date.now()-Date.parse(session.created_at))/1000)));update();const timer=setInterval(update,1000);return()=>clearInterval(timer)},[session.created_at])
  useEffect(() => () => { if(voiceDraftRef.current)URL.revokeObjectURL(voiceDraftRef.current.url);streamingCapture.current?.cancel();incrementalCapture.current?.cancel();media.current?.getTracks().forEach(t => t.stop()); micStream.current?.getTracks().forEach(t => t.stop()); micFrame.current?.(); micVad.current?.stop();micDenoiser.current?.destroy();micLevelGraph.current?.destroy();micContext.current?.close(); playbackContext.current?.close() }, [])
  useEffect(()=>{
    if(!audioPanelOpen)return
    const previous=document.activeElement
    const panel=audioPanelRef.current
    panel?.querySelector('button')?.focus()
    const handleKey=event=>{
      if(event.key==='Escape'){event.preventDefault();setAudioPanelOpen(false)}
      if(event.key==='Tab'){
        const controls=[...panel.querySelectorAll('button:not(:disabled),select:not(:disabled),input:not(:disabled)')]
        const first=controls[0],last=controls.at(-1)
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
      }
    }
    document.addEventListener('keydown',handleKey)
    return()=>{document.removeEventListener('keydown',handleKey);if(previous?.isConnected)previous.focus()}
  },[audioPanelOpen])
  useEffect(()=>{
    const refresh=()=>{if(!callActive){const value=loadSessionAudio(localStorage);setSessionAudio(value);setSelectedMic(value.deviceId)}}
    refresh();window.addEventListener('hikari-session-audio-changed',refresh)
    return()=>window.removeEventListener('hikari-session-audio-changed',refresh)
  },[callActive])
  const refreshMicrophones=useCallback(async(requestAccess=false)=>{
    setMicRefreshing(true)
    try{
      const devices=await listMicrophones(navigator.mediaDevices,requestAccess)
      setMicOptions(devices);setMicListError('')
    }catch(error){setMicListError(error.message)}finally{setMicRefreshing(false)}
  },[])
  useEffect(()=>{
    const refresh=()=>{refreshMicrophones(false)}
    refresh()
    navigator.mediaDevices?.addEventListener?.('devicechange',refresh)
    window.addEventListener('focus',refresh)
    return()=>{navigator.mediaDevices?.removeEventListener?.('devicechange',refresh);window.removeEventListener('focus',refresh)}
  },[refreshMicrophones])
  useEffect(() => {
    if (!camera||!session.posture_enabled) return undefined
    const worker=new Worker(new URL('./pose.worker.js',import.meta.url),{type:'module'})
    let inFlight=false,disposed=false
    worker.onmessage=async({data})=>{
      inFlight=false
      if(disposed)return
      if(data.error){setError(`Posture analysis unavailable: ${data.error}. Voice training can continue.`);return}
      if(!data.landmarks?.length){setPosture(null);setPostureReason('No body detected. Keep your head, shoulders and hips visible.');return}
      try{
        const out=await api(`/sessions/${session.id}/posture-landmarks`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({landmarks:data.landmarks})})
        if(!disposed){setPosture(out.available?out.scores:null);setPostureReason(out.reason||'Visible-body presentation indicators, not medical advice.')}
      }catch(error){if(!disposed)setError(`Posture analysis unavailable: ${error.message}. Voice training can continue.`)}
    }
    const analyse = async () => {
      if (!video.current?.videoWidth||inFlight||disposed) return
      try {
        inFlight=true
        const bitmap=await createImageBitmap(video.current)
        if(disposed){bitmap.close();return}
        worker.postMessage({bitmap,timestamp:performance.now()},[bitmap])
      } catch {inFlight=false}
    }
    analyse()
    const timer=setInterval(analyse,5000)
    return ()=>{disposed=true;clearInterval(timer);worker.terminate()}
  }, [camera, session.id,session.posture_enabled])
  const ensureAudioReady = async () => {
    const AudioContext=window.AudioContext||window.webkitAudioContext
    if(!AudioContext)throw new Error('This browser does not support streamed audio playback.')
    if(!playbackContext.current)playbackContext.current=new AudioContext()
    if(playbackContext.current.state==='suspended')await playbackContext.current.resume()
    return playbackContext.current
  }
  const playChunk = async b64 => {
    const receivedAt=performance.now()
    const context=await ensureAudioReady()
    const readyAt=performance.now()
    const bytes=Uint8Array.from(atob(b64),character=>character.charCodeAt(0))
    const decodeStarted=performance.now()
    const buffer=await context.decodeAudioData(bytes.buffer.slice(0))
    const decodedAt=performance.now()
    const source=context.createBufferSource();source.buffer=buffer;source.connect(context.destination)
    playbackSources.current.add(source)
    source.onended=()=>playbackSources.current.delete(source)
    const lead=.025
    const at=Math.max(context.currentTime+lead,playbackTail.current);source.start(at);playbackTail.current=at+buffer.duration
    if(latencyTrial.current&&!latencyTrial.current.reported){
      const trial=latencyTrial.current
      trial.reported=true
      const outputLatency=(context.outputLatency||context.baseLatency||0)*1000
      const audibleAt=performance.now()+(at-context.currentTime)*1000+outputLatency
      console.info('[Hikari playback latency]',{response_to_audio_received_ms:Math.round(receivedAt-trial.responseStart),context_ready_ms:Math.round(readyAt-receivedAt),base64_ms:Math.round(decodeStarted-readyAt),decode_ms:Math.round(decodedAt-decodeStarted),schedule_wait_ms:Math.round((at-context.currentTime)*1000),output_latency_ms:Math.round(outputLatency)})
      console.info('[Hikari latency]',{endpointing_ms:Math.round(trial.stopped-trial.speechEnd),transcription_ms:Math.round(trial.transcriptionMs),response_to_playback_ms:Math.round(audibleAt-trial.responseStart),total_ms:Math.round(audibleAt-trial.speechEnd),transcription_path:trial.transcriptionPath})
      reportMic({event:'playback_started',state:'session',transcription_path:trial.transcriptionPath,duration_ms:audibleAt-trial.speechEnd,engine:trial.engine,endpointing_ms:trial.stopped-trial.speechEnd,transcription_wall_ms:trial.transcriptionMs,response_to_playback_ms:audibleAt-trial.responseStart,audio_output_latency_ms:outputLatency})
    }
    return playbackTail.current
  }
  const waitForPlayback = async () => {
    const context=playbackContext.current
    if(!context)return
    const remaining=Math.max(0,playbackTail.current-context.currentTime)*1000
    if(remaining)await new Promise(resolve=>setTimeout(resolve,remaining+80))
  }
  const replay = async audioChunks => {
    try{playbackTail.current=0;setVoiceState('replaying');for(const chunk of audioChunks)await playChunk(chunk);await waitForPlayback();setVoiceState('ready')}
    catch(e){setVoiceState('blocked');setError(`Audio playback failed: ${e.message}. Allow sound for localhost, then use Play response.`)}
  }
  const streamVoice = async (reply,correlationId,resumeListening=true,speakerName=null) => {
    const controller=new AbortController();voiceRequest.current=controller
    playbackTail.current=0
    setActiveSpeaker(speakerName||session.counterpart)
    setVoiceState('generating')
    const response=await fetch(`${API}/tts/stream`,{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({text:reply,correlation_id:correlationId})})
    if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.detail||'Voice engine is unavailable.')}
    if(!response.body)throw new Error('Streaming audio is not supported by this browser.')
    const reader=response.body.getReader(),decoder=new TextDecoder();let pending='',received=0
    while(true){
      const {value,done}=await reader.read();pending+=decoder.decode(value||new Uint8Array(),{stream:!done})
      const lines=pending.split('\n');pending=lines.pop()||''
      for(const line of lines){
        if(!line.trim())continue
        const event=JSON.parse(line)
        if(event.tts_timing)console.info('[Hikari TTS latency]',event.tts_timing)
        if(event.type==='error')throw new Error(event.message)
        if(event.type==='audio'){
          received+=1
          setSession(s=>({...s,turns:s.turns.map(turn=>turn.correlationId===correlationId?{...turn,audioChunks:[...(turn.audioChunks||[]),event.audio_b64]}:turn)}))
          setVoiceState(received===1?'speaking':'streaming')
          await playChunk(event.audio_b64)
        }
      }
      if(done)break
    }
    if(!received)throw new Error('Voice engine returned no playable audio.')
    await waitForPlayback()
    setVoiceState('ready')
    if(resumeListening)setActiveSpeaker(null)
    if(automaticTurnEnd&&resumeListening&&callActiveRef.current&&modeRef.current==='voice'&&!mutedRef.current){
      setTimeout(()=>{if(callActiveRef.current&&!mutedRef.current)beginListening.current?.()},180)
    }
  }
  const reportMic = payload => api('/monitor/microphone',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).catch(()=>{})
  const send = async (value = text, duration = 0) => {
    if (!value.trim() || sending.current) return
    sending.current=true
    voiceRequest.current=new AbortController()
    ensureAudioReady().catch(()=>{})
    setBusy(true); setError(''); setText('')
    setSession(s => ({...s, turns:[...s.turns,{role:'user',text:value,created_at:new Date().toISOString()}]}))
    try {
      let result, streamed=false
      const receivedAudio={}
      if(modeRef.current==='voice'){
        const response=await fetch(`${API}/sessions/${session.id}/voice-stream`,{method:'POST',signal:voiceRequest.current.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({text:value,duration_seconds:duration,synthesize_audio:false})})
        if(!response.ok)throw new Error('Voice response could not start.')
        const reader=response.body.getReader(), decoder=new TextDecoder();let pending=''
        playbackTail.current=0;setVoiceState('generating')
        while(true){
          const {value:bytes,done}=await reader.read();pending+=decoder.decode(bytes||new Uint8Array(),{stream:!done})
          const lines=pending.split('\n');pending=lines.pop()||''
          for(const line of lines){
            if(!line.trim())continue
            const event=JSON.parse(line)
        if(event.tts_timing)console.info('[Hikari TTS latency]',event.tts_timing)
            if(event.type==='error')throw new Error(event.message)
            if(event.type==='speech_error'){setError(event.message);streamed=true}
            if(event.type==='speech_text')setSession(s=>{
              const existing=s.turns.find(turn=>turn.provisional&&turn.speaker_name===event.speaker)
              return {...s,turns:existing?s.turns.map(turn=>turn===existing?{...turn,text:`${turn.text} ${event.text}`}:turn):[...s.turns,{role:'assistant',speaker_name:event.speaker,text:event.text,provisional:true,created_at:new Date().toISOString()}]}
            })
            if(event.timing)console.info('[Hikari backend latency]',event.timing)
            if(event.kokoro_timing)console.info('[Hikari Kokoro latency]',event.kokoro_timing)
            if(event.type==='audio'){(receivedAudio[event.speaker]??=[]).push(event.audio_b64);setActiveSpeaker(event.speaker);setVoiceState('speaking');await playChunk(event.audio_b64);streamed=true}
            if(event.type==='result')result=event.result
          }
          if(done)break
        }
        if(!result)throw new Error('The voice response ended unexpectedly.')
      }else result=await api(`/sessions/${session.id}/turn`, {method:'POST',signal:voiceRequest.current.signal, headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:value,duration_seconds:duration,synthesize_audio:false})})
      setSessionProgress(result.session_progress||null)
    const responses=result.responses?.length?result.responses:[{text:result.text,correlation_id:result.correlation_id,speaker:session.counterpart}]
      setSession(s => ({...s, turns:[...s.turns.filter(turn=>!turn.provisional),...responses.map(reply=>({role:'assistant',text:reply.text,speaker_name:reply.speaker,caption_text:reply.caption_text,sources:result.sources,correlationId:reply.correlation_id,audioChunks:receivedAudio[reply.speaker]||[],created_at:reply.created_at||new Date().toISOString()}))]}))
      for(let index=0;modeRef.current==='voice'&&!streamed&&index<responses.length;index+=1){
        const reply=responses[index]
        await streamVoice(reply.text,reply.correlation_id,index===responses.length-1,reply.speaker)
      }
      if(streamed){
        await waitForPlayback();setVoiceState('ready');setActiveSpeaker(null)
        if(automaticTurnEnd&&result.session_progress?.outcome!=='success'&&callActiveRef.current&&!mutedRef.current)setTimeout(()=>{if(callActiveRef.current&&!mutedRef.current&&modeRef.current==='voice')beginListening.current?.()},180)
      }
      if(result.session_progress?.outcome==='success'){
        stopCall()
        await onComplete()
      }
    } catch (e) {
      if(e.name==='AbortError')return
      setVoiceState('failed');setError(`${e.message} The conversation is still active.`)
      if(automaticTurnEnd&&callActiveRef.current&&modeRef.current==='voice'&&!mutedRef.current)setTimeout(()=>{if(callActiveRef.current&&!mutedRef.current&&modeRef.current==='voice')beginListening.current?.()},500)
    } finally { sending.current=false;setBusy(false) }
  }
  const toggleMic = async () => {
    if(micStarting.current||['recording','paused'].includes(recorder.current?.state)||voiceDraftRef.current)return true
    if(!callActiveRef.current||mutedRef.current||modeRef.current!=='voice')return false
    micStarting.current=true
    try {
      await ensureAudioReady()
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone capture requires localhost or HTTPS.')
      const audioOptions=microphoneConstraints(selectedMic,{noiseSuppression:audioMode.browser})
      let stream=micStream.current
      if(!stream?.getAudioTracks().some(track=>track.readyState==='live')){
        try{stream=await navigator.mediaDevices.getUserMedia({audio:audioOptions})}catch(firstError){if(!selectedMic)throw firstError;localStorage.removeItem('hikari-mic-id');setSelectedMic('');setSessionAudio(saveSessionAudio(localStorage,{...sessionAudio,deviceId:''}));stream=await navigator.mediaDevices.getUserMedia({audio:microphoneConstraints('',{noiseSuppression:audioMode.browser})})}
      }
      micStream.current=stream
      const track=stream.getAudioTracks()[0], settings=track.getSettings(), device=track.label||'Default microphone'
      console.info('[Hikari microphone settings]',{device,...settings})
      const devices=(await navigator.mediaDevices.enumerateDevices()).filter(item=>item.kind==='audioinput')
      setMicOptions(devices);if(!selectedMic&&settings.deviceId){setSelectedMic(settings.deviceId);localStorage.setItem('hikari-mic-id',settings.deviceId)}
      setMicDevice(device); setMicState('listening'); setMicLevel(0); speechSeen.current=false; lastSpeech.current=0; peakLevel.current=0;lastLevelReport.current=0;noiseFloor.current=.0003
      reportMic({event:'connected',device,state:'ready',sample_rate:settings.sampleRate,channel_count:settings.channelCount})
      const AudioContext=window.AudioContext||window.webkitAudioContext
      const context=new AudioContext({sampleRate:48000})
      micContext.current=context
      if(context.state==='suspended')await context.resume()
      const levelGraph=sessionAudio.gainEnabled?createInputLevel(context,stream,sessionAudio.gainDb):null
      micLevelGraph.current=levelGraph
      const leveledStream=levelGraph?.stream||stream
      const capture=audioMode.rnnoise?await createCleanCapture(context,leveledStream):null
      micDenoiser.current=capture
      const source=capture?.source||context.createMediaStreamSource(leveledStream)
      const recordingStream=capture?.stream||leveledStream
      console.info('[Hikari session audio]',{mode:audioMode.id,gain_db:sessionAudio.gainEnabled?sessionAudio.gainDb:0,live_recognition:sessionAudio.liveRecognition})
      console.info('[Hikari noise reduction]',{enabled:!!capture,engine:capture?'RNNoise':audioMode.browser?'browser':'none',sample_rate:context.sampleRate})
      if(!callActiveRef.current||mutedRef.current||modeRef.current!=='voice'){
        capture?.destroy();levelGraph?.destroy();micLevelGraph.current=null;micDenoiser.current=null;stream.getTracks().forEach(track=>track.stop());await context.close();micStream.current=null;micContext.current=null;return false
      }
      const preferredMime=['audio/webm;codecs=opus','audio/webm'].find(type=>MediaRecorder.isTypeSupported?.(type))
      const r = preferredMime?new MediaRecorder(recordingStream,{mimeType:preferredMime}):new MediaRecorder(recordingStream); chunks.current=[]; started.current=performance.now(); recorder.current=r
      const decodeCapture=(blob,signal)=>{
        const form=new FormData();form.append('file',blob,'speech.webm');form.append('language',session.training_language||'English');form.append('context',`${session.title}. ${session.situation}`);form.append('duration_ms',String(performance.now()-started.current));form.append('partial','true');form.append('decoding_method',sessionAudio.decodingMethod)
        return api('/transcribe',{method:'POST',body:form,signal:AbortSignal.any&&AbortSignal.timeout?AbortSignal.any([signal,AbortSignal.timeout(12000)]):signal})
      }
      const incremental=new IncrementalTranscriber(decodeCapture,partial=>{setText(partial);setMicState('transcribing live')})
      incrementalCapture.current=incremental
      let live=null
      if(sessionAudio.liveRecognition&&health?.stt_runtime?.streaming&&(session.training_language||'English')==='English'){
        live=new StreamingTranscriber(session.id,partial=>{setText(partial);setMicState('transcribing live')},sessionAudio.decodingMethod)
        streamingCapture.current=live
        if(!await live.start(context,source)){live=null;streamingCapture.current=null}
      }
      if(!callActiveRef.current||mutedRef.current){live?.cancel();incremental.cancel();source.disconnect();capture?.destroy();levelGraph?.destroy();micLevelGraph.current=null;micDenoiser.current=null;await context.close();return false}
      let lastSnapshot=0
      r.ondataavailable = e => {
        if(!e.data.size)return
        chunks.current.push(e.data)
        const now=performance.now(),paused=now-lastSpeech.current>300
        if(automaticTurnEnd&&!live?.ready&&r.state==='recording'&&speechSeen.current&&(now-lastSnapshot>1500||(paused&&now-lastSnapshot>350))){
          if(incremental.push(new Blob(chunks.current,{type:r.mimeType||'audio/webm'}),now))lastSnapshot=now
        }
      }
      r.onstop = async () => {
        const stoppedAt=performance.now()
        console.info('[Hikari capture endpoint]',{reason:r.hikariStopReason||stopReason,capture_ms:Math.round(stoppedAt-started.current),silence_ms:Math.round(stoppedAt-lastSpeech.current)})
        latencyTrial.current=speechSeen.current?{speechEnd:lastSpeech.current,stopped:stoppedAt,reported:false}:null
        const captureMs=r.captureClock.elapsed(performance.now())
        lastCapture.current=new Blob(chunks.current,{type:r.mimeType||'audio/webm'})
        micFrame.current?.(); micFrame.current=null
        micVad.current?.stop();micVad.current=null
        setRecording(false);setCapturePaused(false)
        if((speechSeen.current||!automaticTurnEnd)&&!discardCapture.current)setBusy(true)
        const transcriptionStarted=performance.now()
        let cleanupStarted=false
        const cleanupCapture=()=>{
          if(cleanupStarted)return
          cleanupStarted=true
          source.disconnect()
          capture?.destroy();levelGraph?.destroy()
          if(micLevelGraph.current===levelGraph)micLevelGraph.current=null
          if(!automaticTurnEnd){stream.getTracks().forEach(track=>track.stop());if(micStream.current===stream)micStream.current=null}
          if(micDenoiser.current===capture)micDenoiser.current=null
          if(micContext.current===context)micContext.current=null
          const cleanupAt=performance.now()
          context.close().then(()=>console.info('[Hikari capture cleanup]',{close_ms:Math.round(performance.now()-cleanupAt)})).catch(()=>{})
        }
        if(!automaticTurnEnd&&!discardCapture.current&&callActiveRef.current&&!mutedRef.current){
          const liveResult=live?await live.finish(cleanupCapture):null
          incremental.cancel();cleanupCapture()
          if(!callActiveRef.current||mutedRef.current||discardCapture.current){setBusy(false);return}
          if(voiceDraftRef.current)URL.revokeObjectURL(voiceDraftRef.current.url)
          const draft={blob:lastCapture.current,url:URL.createObjectURL(lastCapture.current),durationMs:captureMs,liveResult}
          voiceDraftRef.current=draft;setVoiceDraft(draft);setMicLevel(0);setMicState('review');setVoiceState('ready');setBusy(false)
          latencyTrial.current=null
          await sendReviewedVoice()
          return
        }
        let liveResult=null
        if(live){
          // Flush captured PCM before closing its context; overlap cleanup with
          // backend finalization rather than delaying the response request.
          if(speechSeen.current&&!discardCapture.current)liveResult=await live.finish(cleanupCapture)
          else live.cancel()
          if(streamingCapture.current===live)streamingCapture.current=null
        }
        cleanupCapture()
        if(live?.timing)console.info('[Hikari transcription stages]',live.timing)
        console.info('[Hikari recognition outcome]',{live_final_received:!!liveResult,input_audio:liveResult?.input_audio??null,captured_audio_ms:liveResult?.captured_audio_ms??null,text_chars:liveResult?.text?.trim().length??0,needs_retry:liveResult?.needs_retry??null,capture_ms:Math.round(captureMs),recorded_bytes:chunks.current.reduce((total,chunk)=>total+chunk.size,0)})
        if(!callActiveRef.current||mutedRef.current){stream.getTracks().forEach(t=>t.stop());micStream.current=null}
        setRecording(false);setMicLevel(0)
        if(discardCapture.current){incremental.cancel();discardCapture.current=false;setMicState('idle');setBusy(false);return}
        const resumeCapture=()=>setTimeout(()=>{
          if(callActiveRef.current&&!mutedRef.current&&modeRef.current==='voice')beginListening.current?.()
        },350)
        // Quiet capture rotation must not transcribe silence or strand a connected call.
        if(!speechSeen.current){
          incremental.cancel();setMicState('listening')
          const warning=track.muted||peakLevel.current<.05
            ? `No microphone audio is arriving from ${device}. Check the selected device and its hardware mute switch.`
            : `Audio is arriving from ${device}, but speech was too quiet to detect. Check its input volume or choose another microphone.`
          setError(warning);reportMic({event:'error',device,state:'no speech',peak_percent:peakLevel.current,error:warning});resumeCapture();return
        }
        setMicState('transcribing');setBusy(true)
        reportMic({event:'stopped',device,state:'transcribing',duration_ms:captureMs,peak_percent:peakLevel.current})
        try {
          const form=new FormData();form.append('file',new Blob(chunks.current,{type:r.mimeType||'audio/webm'}),'speech.webm');form.append('language',session.training_language||'English');form.append('context',`${session.title}. ${session.situation}`);form.append('duration_ms',String(captureMs));form.append('decoding_method',sessionAudio.decodingMethod)
          const reusable=liveResult?.text?liveResult:await incremental.finish(lastSpeech.current)
          if(incremental.controller.signal.aborted){setBusy(false);return}
          const signal=AbortSignal.any&&AbortSignal.timeout?AbortSignal.any([incremental.controller.signal,AbortSignal.timeout(45000)]):incremental.controller.signal
          const out=reusable||await api('/transcribe',{method:'POST',body:form,signal})
          if(incremental.controller.signal.aborted){setBusy(false);return}
          if(latencyTrial.current)latencyTrial.current.transcriptionMs=performance.now()-transcriptionStarted
          console.info('[Hikari transcript decision]',{text_chars:out.text?.trim().length??0,needs_retry:!!out.needs_retry,engine:out.engine||'unknown',input_audio:out.input_audio??null})
          if(!out.text?.trim())throw new Error('Nemotron returned an empty transcript. No message was sent. Check the selected microphone, then choose Retry microphone.')
          if(out.needs_retry){
            setText(out.text);setMicState('retry');setBusy(false);setError(`I heard “${out.text}”, but it was too short or uncertain. Please say the full sentence again.`);reportMic({event:'error',device,state:'retry',duration_ms:out.latency_ms||0,peak_percent:peakLevel.current,transcript:out.text,error:out.retry_reason});return
          }
          setText(out.text);setMicState('transcribed');reportMic({event:'transcribed',device,state:'complete',duration_ms:out.latency_ms||0,peak_percent:peakLevel.current,transcript:out.text})
          if(latencyTrial.current){
            console.info('[Hikari transcription latency]',{backend_finalize_or_decode_ms:out.latency_ms,transcription_path:liveResult?.text?'live':reusable?'incremental':'recorded'})
            latencyTrial.current.engine=health?.engine||'unknown'
            latencyTrial.current.transcriptionPath=liveResult?.text?'live':reusable?'incremental':'recorded'
            latencyTrial.current.responseStart=performance.now()
          }
          await send(out.text,captureMs/1000)
        } catch(e){
          if(incremental.controller.signal.aborted){setBusy(false);return}
          setMicState('error');setError(e.message);reportMic({event:'error',device,state:'error',duration_ms:captureMs,peak_percent:peakLevel.current,error:e.message});setBusy(false);console.error('[Hikari recognition failed]',e)
        }
      }
      let stopReason='unknown'
      const markSpeech=()=>{
        if(r.state!=='recording')return
        if(!speechSeen.current){
          speechSeen.current=true;setError('');setMicState('speech detected')
          reportMic({event:'speech_detected',device,state:'recording',duration_ms:performance.now()-started.current})
        }
      }
      // VAD only decides turn boundaries. MediaRecorder and live recognition
      // retain the continuous capture, including audio before speech detection.
      const vad=automaticTurnEnd?await startSilero(context,recordingStream,{
        onProbability:probability=>{if(r.state==='recording'&&probability>=turnDetection.positiveThreshold)lastSpeech.current=performance.now()},
        onSpeech:markSpeech,
        onEnd:()=>{if(automaticTurnEnd&&r.state==='recording'&&speechSeen.current){stopReason='silero_silence';r.stop()}},
      }):{error:null,stop:async()=>{}}
      micVad.current=vad
      if(!callActiveRef.current||mutedRef.current||modeRef.current!=='voice'){
        await vad.stop();micVad.current=null;live?.cancel();incremental.cancel()
        source.disconnect();capture?.destroy();micDenoiser.current=null
        await context.close();micContext.current=null;return false
      }
      const analyse=rms=>{
        if(r.state!=='recording')return
        const level=Math.min(100,rms*500);peakLevel.current=Math.max(peakLevel.current,level);setMicLevel(level)
        const now=performance.now(),elapsed=r.captureClock.elapsed(now)
        if(now-lastLevelReport.current>500){lastLevelReport.current=now;reportMic({event:'level',device,state:speechSeen.current?'speech detected':'listening',duration_ms:elapsed,level_percent:level,peak_percent:peakLevel.current})}
        if(vad.error){stopReason='vad_error';discardCapture.current=true;setError(`Speech detection failed: ${vad.error}. Rejoin the call.`);r.stop();return}
        const limitReason=captureLimitReason(elapsed,speechSeen.current,automaticTurnEnd)
        if(limitReason){stopReason=limitReason;r.stop()}
      }
      started.current=performance.now();r.captureClock=new CaptureClock(started.current)
      setCapturePaused(false)
      r.start(100); setRecording(true);reportMic({event:'listening',device,state:'listening'})
      micFrame.current=monitorMicrophone(context,source,analyse,error=>{
        setError(error.message);reportMic({event:'error',device,state:'error',error:error.message})
        if(r.state==='recording')r.stop()
      });return true
    } catch(e) {
      micFrame.current?.();micFrame.current=null
      micVad.current?.stop();micVad.current=null
      streamingCapture.current?.cancel();incrementalCapture.current?.cancel()
      micDenoiser.current?.destroy();micDenoiser.current=null
      micLevelGraph.current?.destroy();micLevelGraph.current=null
      micStream.current?.getTracks().forEach(track=>track.stop());micStream.current=null
      if(micContext.current)await micContext.current.close().catch(()=>{});micContext.current=null
      setMicState('error');setError(`Microphone unavailable: ${e.message}`);reportMic({event:'error',state:'error',error:e.message});return false
    } finally {micStarting.current=false}
  }
  beginListening.current=toggleMic
  // Resume microphone capture after waitForPlayback completes. A volume-only
  // interruption detector cannot distinguish the learner from speaker echo,
  // and can abort the bot's own audio immediately on laptops.
  const stopCall = () => {
    if(voiceDraftRef.current)URL.revokeObjectURL(voiceDraftRef.current.url)
    voiceDraftRef.current=null;setVoiceDraft(null);setCapturePaused(false)
    streamingCapture.current?.cancel();streamingCapture.current=null
    incrementalCapture.current?.cancel();incrementalCapture.current=null
    voiceRequest.current?.abort();voiceRequest.current=null
    callActiveRef.current=false;setCallActive(false);mutedRef.current=false;setMuted(false);setVoiceState('idle');setMicState('idle')
    if(['recording','paused'].includes(recorder.current?.state)){discardCapture.current=true;recorder.current.stop()}
    else{micStream.current?.getTracks().forEach(track=>track.stop());micStream.current=null}
    micVad.current?.stop();micVad.current=null
    micDenoiser.current?.destroy();micDenoiser.current=null
    micLevelGraph.current?.destroy();micLevelGraph.current=null
    playbackContext.current?.close();playbackContext.current=null;playbackTail.current=0
  }
  const startCall = async () => {
    if (health?.components?.stt === false) {
      setError('Speech recognition is offline. Restart Hikari without --skip-models, then refresh this page.')
      return
    }
    callActiveRef.current = true; modeRef.current = 'voice'; mutedRef.current = false; setCallActive(true); setMuted(false); setError('')
    try {
      await ensureAudioReady()
      if(!micStream.current?.active){
        try{micStream.current=await navigator.mediaDevices.getUserMedia({audio:microphoneConstraints(selectedMic,{noiseSuppression:audioMode.browser})})}
        catch(error){
          if(!selectedMic||!['NotFoundError','OverconstrainedError'].includes(error.name))throw error
          localStorage.removeItem('hikari-mic-id');setSelectedMic('');setSessionAudio(saveSessionAudio(localStorage,{...sessionAudio,deviceId:''}))
          micStream.current=await navigator.mediaDevices.getUserMedia({audio:microphoneConstraints('',{noiseSuppression:audioMode.browser})})
        }
      }
      const track=micStream.current.getAudioTracks()[0]
      console.info('[Hikari microphone settings]',{device:track.label,...track.getSettings()})
      await refreshMicrophones(false)
    } catch(e) {
      setError(e.message);callActiveRef.current=false;setCallActive(false);return
    }
    const openingTurn = session.turns?.[0]
    const hasUserSpoken = session.turns?.some(t => t.role === 'user')
    if (openingTurn && openingTurn.role === 'assistant' && !hasUserSpoken) {
      streamVoice(openingTurn.text, openingTurn.correlationId || 'opening-turn', true, openingTurn.speaker_name)
        .catch(e => {
          if(e.name==='AbortError')return
          setVoiceState('failed')
          setError(`Voice playback failed: ${e.message}. You can still proceed by speaking.`)
          if(automaticTurnEnd)setTimeout(() => {if(callActiveRef.current&&!mutedRef.current&&modeRef.current==='voice')beginListening.current?.()}, 600)
        })
    } else {
      if (automaticTurnEnd&&!await toggleMic()) { callActiveRef.current = false; setCallActive(false) }
    }
  }
  const changeMode = next => {
    if(next===mode)return
    if(callActiveRef.current)stopCall()
    modeRef.current=next;setMode(next);setError('')
  }
  const toggleMute = () => {
    const next=!muted;mutedRef.current=next;setMuted(next)
    if(next&&['recording','paused'].includes(recorder.current?.state)){discardCapture.current=true;recorder.current.stop()}
    if(next){streamingCapture.current?.cancel();incrementalCapture.current?.cancel();micStream.current?.getTracks().forEach(track=>track.stop());micStream.current=null}
    if(automaticTurnEnd&&!next&&callActiveRef.current&&!busy&&voiceState==='ready')setTimeout(()=>beginListening.current?.(),100)
  }
  const toggleCamera = async () => {
    if (camera) { media.current?.getTracks().forEach(t=>t.stop()); media.current=null; setCamera(false); return }
    try {
      const stream=await navigator.mediaDevices.getUserMedia({video:{width:640,height:480}}); media.current=stream; setCamera(true)
      setTimeout(()=>{ if(video.current) video.current.srcObject=stream },0)
    } catch(e){setError(`Camera unavailable: ${e.message}`)}
  }
  const downloadCapture=()=>{
    if(!lastCapture.current)return
    const url=URL.createObjectURL(lastCapture.current)
    const link=document.createElement('a')
    link.href=url;link.download='hikari-microphone.webm';link.click()
    setTimeout(()=>URL.revokeObjectURL(url),1000)
  }
  const sendReviewedVoice=async()=>{
    const draft=voiceDraftRef.current
    if(!draft||reviewSending.current||!callActiveRef.current||mutedRef.current)return
    reviewSending.current=true;setBusy(true);setError('');setMicState('transcribing')
    const controller=new AbortController();voiceRequest.current=controller
    const timer=setTimeout(()=>controller.abort(),45000)
    try{
      const form=new FormData();form.append('file',draft.blob,'speech.webm');form.append('decoding_method',sessionAudio.decodingMethod)
      form.append('language',session.training_language||'English');form.append('duration_ms',String(draft.durationMs))
      form.append('context',`${session.title}. ${session.situation}`)
      const out=draft.liveResult?.text?.trim()?draft.liveResult:await api('/transcribe',{method:'POST',body:form,signal:controller.signal})
      if(!callActiveRef.current||voiceDraftRef.current!==draft||controller.signal.aborted)return
      if(!out.text?.trim()){URL.revokeObjectURL(draft.url);voiceDraftRef.current=null;setVoiceDraft(null);throw new Error('No words recognized. Press Record voice to try another turn.')}
      URL.revokeObjectURL(draft.url);voiceDraftRef.current=null;setVoiceDraft(null)
      setMicState('transcribed');await send(out.text,draft.durationMs/1000)
    }catch(error){if(error.name!=='AbortError'){setMicState('error');setError(error.message)}else if(callActiveRef.current){setMicState('error');setError('Recognition was interrupted or timed out. Your recording is still available.')}}
    finally{clearTimeout(timer);reviewSending.current=false;setBusy(false)}
  }
  const toggleVoiceRecording=()=>{
    const current=recorder.current
    if(current?.state==='recording'){
      current.hikariStopReason='manual_send';current.stop()
    }else if(voiceDraftRef.current){
      sendReviewedVoice()
    }else{
      beginListening.current?.()
    }
  }
  const latestReply=[...session.turns].reverse().find(turn=>turn.role==='assistant')
  const callStatus=!callActive?'Ready to start':voiceDraft?'Preparing your voice message…':capturePaused?'Recording paused':!recording&&['error','retry'].includes(micState)?'Recognition needs attention':voiceState==='speaking'||voiceState==='streaming'?`${activeSpeaker||session.counterpart} is speaking`:muted?'Microphone muted':micState==='transcribing'?'Understanding you…':voiceState==='generating'||busy?'Preparing response…':recording?(micState==='speech detected'?'Listening to you…':'Listening…'):'Connected'
  const participants=session.participants||[{participant_type:'learner',display_name:'You'},{participant_type:'ai',display_name:session.counterpart}]
  const aiParticipants=participants.filter(person=>person.participant_type==='ai')
  const multipleAI=aiParticipants.length>1
  const formatTime=value=>`${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`
  const finishSession=async()=>{try{await onComplete();stopCall()}catch(error){setError(error.message)}}
  const leaveSession=async()=>{try{stopCall();await onCancel()}catch(error){setError(error.message)}}
  const participantTile=(person,index,isLearner=false)=><div key={person.id||`${person.display_name}-${index}`} className={`participant-tile ${!isLearner&&person.display_name===activeSpeaker&&(voiceState==='speaking'||voiceState==='streaming')?'active-speaker':''}`}>
    {isLearner&&camera?<video ref={video} autoPlay muted playsInline/>:<div className={`participant-avatar ${!isLearner&&index===0&&callActive?'pulse':''}`}><span>●</span></div>}
    <strong>{person.display_name}{!isLearner&&index===0?` (${person.scenario_role||session.counterpart})`:''}</strong>
    <span className="tile-mic">{isLearner&&!muted&&recording?'▮▮▮':'⌁'}</span>
  </div>
  return <main className="session-window">
    <header className="session-header"><div><h1>{session.title}</h1><p>{session.description||session.situation}</p></div><div className="session-header-actions"><div className="session-clock"><span/> <strong>{formatTime(elapsed)}</strong><small>{callActive?'In Session':'Ready'}</small></div><i/><button className="h-small" onClick={finishSession} disabled={busy||sessionProgress?.outcome!=='success'}>Finish lesson</button><button className="session-end-top" onClick={leaveSession}>☎ &nbsp; End Session</button></div></header>
    <div className="session-body">
      <section className="session-call-area">
        {error&&<div className="session-error" role="alert">{error}{lastCapture.current&&['error','retry'].includes(micState)&&<button onClick={downloadCapture}>Save microphone recording</button>}{callActive&&!recording&&!busy&&['error','retry'].includes(micState)&&<button onClick={()=>{setError('');beginListening.current?.()}} disabled={muted}>Retry microphone</button>}</div>}
        {sessionProgress&&<div className={`session-progress ${sessionProgress.outcome}`}><strong>{sessionProgress.outcome==='success'?'Objectives achieved':'Keep learning'}</strong><span>{sessionProgress.criteria?.filter(item=>item.met).length || 0}/{sessionProgress.criteria?.length || 0} objectives{sessionProgress.missing?.length?` · Next: ${sessionProgress.missing[0]}`:''}{sessionProgress.evaluation_mode?` · ${sessionProgress.evaluation_mode}`:''}</span></div>}
        {mode==='voice'?<div className={`participant-stage ${multipleAI?'participant-grid':'single-participant'}`}>
          {multipleAI?<>{aiParticipants.map((person,index)=>participantTile(person,index))}{participantTile(participants.find(person=>person.participant_type==='learner')||{display_name:'You'},aiParticipants.length,true)}</>:<>
            <div className={`hero-participant ${voiceState==='speaking'||voiceState==='streaming'?'speaking':''}`}><div className="hero-rings"><span>●</span></div><b>{callStatus}</b><small>{aiParticipants[0]?.display_name||session.counterpart}</small></div>
            <div className="self-pip">{camera?<video ref={video} autoPlay muted playsInline/>:<div className="pip-avatar">●</div>}<strong>You</strong><span>{muted?'⌁':'◉'}</span></div>
            <div className="ai-role-label">▮▮▮ &nbsp; AI Roleplay</div>
          </>}
          <button ref={audioButtonRef} className="session-audio-tab" aria-label="Open audio settings" aria-haspopup="dialog" aria-expanded={audioPanelOpen} aria-controls="session-audio-panel" onClick={()=>setAudioPanelOpen(true)}><Icon name="settings"/><span>Audio</span></button>
          {audioPanelOpen&&<div className="session-audio-backdrop" onClick={()=>setAudioPanelOpen(false)}>
            <section ref={audioPanelRef} id="session-audio-panel" className="session-audio-panel" role="dialog" aria-modal="true" aria-labelledby="session-audio-title" onClick={event=>event.stopPropagation()}>
              <header><div><p>CALL PREFERENCES</p><h2 id="session-audio-title">Audio settings</h2></div><button className="audio-panel-close" aria-label="Close audio settings" onClick={()=>setAudioPanelOpen(false)}>×</button></header>
              <div className="audio-panel-content">
                <label className="audio-device-label" htmlFor="session-microphone">Microphone</label>
                <p className="audio-panel-description">{automaticTurnEnd?'Automatic input listens between replies and sends after a pause. You can also press Stop & send.':'Use the bottom Record voice button to start. Press it again to stop and send.'} Recordings are limited to 80 seconds.</p>
                <p className="audio-panel-description">Choose the input you want to use for this conversation.</p>
                <select id="session-microphone" value={selectedMic} disabled={callActive||micRefreshing} onChange={event=>{setSelectedMic(event.target.value);setSessionAudio(saveSessionAudio(localStorage,{...sessionAudio,deviceId:event.target.value}))}}>
                  <option value="">System default microphone</option>
                  {selectedMic&&!micOptions.some(item=>item.deviceId===selectedMic)&&<option value={selectedMic}>Previously selected microphone</option>}
                  {micOptions.map((item,index)=><option value={item.deviceId} key={item.deviceId}>{item.label||`Microphone ${index+1}`}</option>)}
                </select>
                <button className="audio-refresh" disabled={micRefreshing} onClick={()=>refreshMicrophones(!callActive)}>{micRefreshing?'Finding microphones…':'Enable / refresh microphones'}</button>
                <p className="audio-panel-note">Decoder: {sessionAudio.decodingMethod==='greedy_search'?'Greedy':'Modified beam'} · Input: {automaticTurnEnd?'Automatic':'Manual'} · Session processing: {audioMode.name} · Gain {sessionAudio.gainEnabled?`${sessionAudio.gainDb} dB`:'off'} · Live recognition {sessionAudio.liveRecognition?'on':'off'}. Change processing preferences on the Settings page before joining your next session.</p>
                {callActive&&<p className="audio-panel-note">Input settings are locked during a call. Switch to chat before changing them.</p>}
                {!callActive&&micOptions.length===0&&<p className="audio-panel-note">Enable microphone access to see your devices.</p>}
                {micListError&&<p className="audio-panel-error" role="alert">{micListError}</p>}
              </div>
              <footer><button onClick={()=>setAudioPanelOpen(false)}>Done</button></footer>
            </section>
          </div>}
          {!callActive&&<div className="join-overlay"><h2>Ready to begin?</h2><p>{health?.components?.stt===false?'Speech recognition is offline. Start Hikari normally before joining.':automaticTurnEnd?'Your microphone starts automatically. Pause after speaking to send your turn.':'Use Record voice below, then press Stop & send when you are finished.'}</p><button onClick={startCall} disabled={health?.components?.stt===false}>{health?.components?.stt===false?'Speech Recognition Offline':'Join Voice Session'}</button></div>}
          {captions&&latestReply&&<div className="live-caption"><strong>{latestReply.speaker_name||aiParticipants[0]?.display_name||session.counterpart}</strong><p>{latestReply.caption_text||latestReply.text}</p>{latestReply.caption_text&&<small>{userSettings?.native_language} captions · spoken English</small>}</div>}
        </div>:<div className="session-chat"><div className="messages">{session.turns.map((turn,index)=><div className={`turn ${turn.role}`} key={index}><small>{turn.role==='user'?'You':turn.speaker_name||session.counterpart}</small><p>{turn.text}</p><SourceEvidence sources={turn.sources}/>{captions&&turn.caption_text&&<small className="translated-caption">{turn.caption_text}</small>}</div>)}{busy&&<div className="turn assistant typing"><i/><i/><i/></div>}<div ref={chatEnd}/></div><div className="composer"><textarea value={text} onChange={event=>setText(event.target.value)} placeholder="Type your response…" onKeyDown={event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send()}}}/><button className="send" onClick={()=>send()} disabled={busy||!text.trim()}><Icon name="send"/></button></div></div>}
        {session.posture_enabled&&<section className="posture-live"><strong>Posture indicators</strong><span>{camera?postureReason:"Camera is off; posture is not assessed."}</span>{posture&&Object.entries(posture).filter(([,v])=>typeof v==="number").map(([k,v])=><small key={k}>{k.replaceAll("_"," ")}: {Math.round(v)} · </small>)}</section>}<div className="meeting-controls">{mode==='voice'&&<button className={`voice-record-button ${recording?'selected is-recording':''}`} disabled={!callActive||muted||busy||micStarting.current||['speaking','streaming','generating'].includes(voiceState)} aria-pressed={recording} onClick={toggleVoiceRecording}><span>{recording?'■':'●'}</span>{recording?'Stop & send':voiceDraft?'Retry send':'Record voice'}</button>}<button onClick={onOpenSettings}><span>⚙</span>Settings</button><button className={muted?'selected':''} onClick={toggleMute}><span>♩</span>{muted?'Unmute':'Mute'}</button><button className={camera?'selected':''} onClick={toggleCamera}><span>▣</span>Camera</button><button className="hangup" onClick={leaveSession}><span>☎</span>End Session</button><button className={captions?'selected':''} onClick={()=>setCaptions(value=>!value)}><span>▤</span>Captions</button><button onClick={()=>changeMode(mode==='voice'?'chat':'voice')}><span>•••</span>{mode==='voice'?'More':'Voice Call'}</button></div>
      </section>
      <aside className="session-transcript"><h2>Conversation</h2><div>{session.turns.map((turn,index)=><article className={turn.role} key={index}><div className="transcript-avatar">●</div><section><header><strong>{turn.role==='user'?'You':turn.speaker_name||session.counterpart}</strong><span>· {formatTime(Math.max(0,Math.floor((turn.elapsed_seconds??((Date.parse(turn.created_at)-Date.parse(session.created_at))/1000))||0)))}</span></header><p>{turn.text}</p><SourceEvidence sources={turn.sources}/>{captions&&turn.caption_text&&<small className="translated-caption">{turn.caption_text}</small>}</section></article>)}{busy&&<article><div className="transcript-avatar">●</div><section className="transcript-typing"><i/><i/><i/></section></article>}</div></aside>
    </div>
  </main>
}

function Assessment({ session, assessment, onDone }) {
  return <main className="assessment"><div className="assessment-hero"><p className="eyebrow">SESSION COMPLETE</p><h1>{session.title}</h1><ScoreRing score={assessment.overall} size={150}/><p>{assessment.feedback}</p></div><div className="assessment-grid"><section><p className="eyebrow">RUBRIC BREAKDOWN</p>{Object.entries(assessment.scores).map(([k,v])=><div className="metric" key={k}><span>{k.replaceAll('_',' ')}</span><div><i style={{width:`${v}%`}}/></div><strong>{Math.round(v)}</strong></div>)}</section><section><p className="eyebrow">COACHING NOTES</p><h3>What worked</h3>{assessment.strengths.map(x=><p className="note good" key={x}>✓ {x}</p>)}<h3>Improve next</h3>{assessment.improvements.map(x=><p className="note improve" key={x}>↗ {x}</p>)}</section></div>{Object.keys(assessment.visual_scores||{}).length>0&&<section className="evidence"><h3>Posture indicators · separate from proficiency</h3>{Object.entries(assessment.visual_scores).map(([k,v])=><p key={k}>{k.replaceAll("_"," ")}: {v}/100</p>)}<small>{assessment.posture_sample_count} camera samples · prototype presentation indicators, not medical advice</small></section>}<section className="evidence"><p className="eyebrow">EVIDENCE</p>{assessment.evidence.map(x=><p key={x}>{x}</p>)}</section><button className="primary done" onClick={onDone}>Back to overview</button></main>
}

function History({ rows }) { return <main className="page"><header className="page-head compact"><div><p className="eyebrow">YOUR RECORD</p><h1>Training history</h1><p>Review completed and in-progress practice sessions.</p></div></header><div className="history-table"><div className="table-head"><span>Scenario</span><span>Difficulty</span><span>Status</span><span>Score</span></div>{rows.length?rows.map(r=><div className="table-row" key={r.id}><span><strong>{r.title}</strong><small>{r.skill_id.replaceAll('-',' ')}</small></span><span>{r.difficulty}</span><span><i className={r.status}/>{r.status}</span><b>{r.overall?Math.round(r.overall):'—'}</b></div>):<div className="empty-panel">No sessions yet. Start a roleplay to build your history.</div>}</div></main> }

function Documents({ docs, reload }) {
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('')
  const upload=async e=>{const file=e.target.files[0];if(!file)return;setBusy(true);setMessage('');try{const form=new FormData();form.append('file',file);await api('/documents',{method:'POST',body:form});setMessage(`${file.name} is ready for grounded roleplays.`);reload()}catch(err){setMessage(err.message)}finally{setBusy(false);e.target.value=''}}
  const remove=async id=>{await api(`/documents/${id}`,{method:'DELETE'});reload()}
  return <main className="page"><header className="page-head compact"><div><p className="eyebrow">ORGANIZATION KNOWLEDGE</p><h1>Ground training in real policy</h1><p>Upload authorised material. Hikari retrieves relevant passages during roleplay and identifies the source.</p></div><label className="primary upload">{busy?'Processing…':'Upload document'}<input type="file" accept=".pdf,.docx,.txt,.md" onChange={upload} disabled={busy}/></label></header>{message&&<div className="notice">{message}</div>}<div className="document-info"><div><strong>Supported</strong><span>PDF, DOCX, TXT, MD · maximum 10 MB</span></div><div><strong>Private by design</strong><span>Stored only in your local Hikari database</span></div><div><strong>Traceable</strong><span>Source names appear beside grounded replies</span></div></div><div className="doc-list"><div className="table-head"><span>Document</span><span>Status</span><span>Chunks</span><span></span></div>{docs.length?docs.map(d=><div className="table-row" key={d.id}><span><strong>{d.name}</strong><small>{new Date(d.created_at).toLocaleDateString()}</small></span><span><i className="completed"/>ready</span><span>{d.chunks}</span><button className="delete" onClick={()=>remove(d.id)}>Remove</button></div>):<div className="empty-panel">No documents uploaded. General scenarios still work without them.</div>}</div></main>
}

const fmt = (value, unit='ms') => value == null ? '—' : `${Math.round(value)}${unit}`
function Sparkline({ values, max=100 }) {
  if (!values.length) return <div className="spark-empty">Collecting samples…</div>
  const points=values.map((v,i)=>`${i/(Math.max(values.length-1,1))*100},${38-Math.min(v/max,1)*34}`).join(' ')
  return <svg className="spark" viewBox="0 0 100 40" preserveAspectRatio="none"><polyline points={points}/></svg>
}

function Monitor(){
  const [snapshot,setSnapshot]=useState(null),[samples,setSamples]=useState([]),[clientMs,setClientMs]=useState(null),[paused,setPaused]=useState(false),[error,setError]=useState('')
  const refresh=useCallback(async()=>{if(paused)return;const started=performance.now();try{const next=await api('/monitor/snapshot');setClientMs(performance.now()-started);setSnapshot(next);setSamples(old=>[...old.slice(-29),{cpu:next.system.cpu_percent,ram:next.system.ram_percent,gpu:next.system.gpu?.utilization_percent||0,at:next.timestamp}]);setError('')}catch(e){setError(e.message)}},[paused])
  useEffect(()=>{refresh();const timer=setInterval(refresh,2000);return()=>clearInterval(timer)},[refresh])
  const reset=async()=>{await api('/monitor/reset',{method:'POST'});setSamples([]);refresh()}
  if(!snapshot)return <Loading/>
  const s=snapshot.system,g=s.gpu,last=snapshot.pipeline.latest_roleplay
  const micEvents=snapshot.recent.filter(event=>event.category==='microphone')
  const latestMic=micEvents[0],deviceEvent=micEvents.find(event=>event.device),transcriptEvent=micEvents.find(event=>event.transcript)
  const micActive=latestMic&&['connected','listening','level','speech_detected'].includes(latestMic.name)&&(Date.now()-new Date(latestMic.timestamp).getTime()<5000)
  const status=(value,good,warn)=>value==null?'neutral':value<=good?'good':value<=warn?'warn':'bad'
  const cards=[
    ['Browser round trip',clientMs,'ms',250,700,'UI → API → UI'],
    ['HTTP p95',snapshot.http.p95_ms,'ms',500,1500,`${snapshot.http.requests} measured requests`],
    ['Process memory',s.process_rss_mb,' MB',3500,7000,'Backend working set'],
    ['System RAM',s.ram_percent,'%',75,90,`${s.ram_used_gb} of ${s.ram_total_gb} GB`],
    ['GPU load',g?.utilization_percent,'%',75,92,g?.name||'NVML unavailable'],
    ['VRAM',g?.memory_percent,'%',75,90,g?`${g.memory_used_mb} of ${g.memory_total_mb} MB`:'NVML unavailable'],
  ]
  return <main className="page monitor-page"><header className="page-head compact"><div><p className="eyebrow">TESTING CONSOLE</p><h1>Runtime monitor</h1><p>Live measurements from this local run, including bounded microphone diagnostics and recent transcription.</p></div><div className="monitor-actions"><button onClick={()=>setPaused(x=>!x)}>{paused?'Resume':'Pause'}</button><button onClick={reset}>Reset window</button></div></header>{error&&<div className="error">{error}</div>}
    <div className="monitor-status"><span className={`live-dot ${Object.values(snapshot.components).every(x=>x.ready)?'ready':''}`}/><strong>{Object.values(snapshot.components).every(x=>x.ready)?'All systems ready':'Running with unavailable components'}</strong><span>Uptime {Math.floor(snapshot.uptime_seconds/60)}m {Math.round(snapshot.uptime_seconds%60)}s</span><span>Refresh 2s</span></div>
    <section className="metric-cards">{cards.map(([label,value,unit,good,warn,detail])=><article key={label} className={status(value,good,warn)}><p>{label}</p><strong>{fmt(value,unit)}</strong><small>{detail}</small></article>)}</section>
    <section className="monitor-grid"><article className="monitor-panel"><div className="panel-title"><div><p className="eyebrow">RESOURCE TREND</p><h2>Last 60 seconds</h2></div><div className="legend"><span className="cpu">CPU</span><span className="ram">RAM</span><span className="gpu">GPU</span></div></div><div className="trend"><Sparkline values={samples.map(x=>x.cpu)}/><Sparkline values={samples.map(x=>x.ram)}/><Sparkline values={samples.map(x=>x.gpu)}/></div><div className="trend-values"><span>CPU <b>{fmt(s.cpu_percent,'%')}</b></span><span>RAM <b>{fmt(s.ram_percent,'%')}</b></span><span>GPU <b>{fmt(g?.utilization_percent,'%')}</b></span><span>GPU temp <b>{fmt(g?.temperature_c,'°C')}</b></span></div></article>
      <article className="monitor-panel"><p className="eyebrow">COMPONENTS</p><h2>Model readiness</h2><div className="component-list">{Object.entries(snapshot.components).map(([name,item])=><div key={name}><span className={`component-dot ${item.ready?'ready':'offline'}`}/><strong>{name.toUpperCase()}</strong><span>{item.ready?'Ready':item.error?'Failed':'Not loaded'}</span><b>{item.load_ms?fmt(item.load_ms):'—'}</b></div>)}</div></article></section>
    <section className="monitor-panel pipeline-panel"><div className="panel-title"><div><p className="eyebrow">LATEST VOICE TURN</p><h2>Latency breakdown</h2></div><span className="mode-pill">{last?.mode||'waiting'}</span></div>{last?<><div className="stage-grid">{[['Retrieval',last.retrieval_ms],['LLM first token',last.llm_ttft_ms],['Text visible',last.response_ready_ms],['First audio',last.first_audio_total_ms],['Voice complete',last.full_pipeline_ms]].map(([name,value])=><div key={name}><span>{name}</span><strong>{fmt(value)}</strong><i style={{width:`${Math.min((value||0)/Math.max(last.full_pipeline_ms||last.response_ready_ms,1)*100,100)}%`}}/></div>)}</div><div className="pipeline-foot"><span>{last.engine ? `${last.engine.toUpperCase()} first chunk` : 'TTS first chunk'} <b>{fmt(last.tts_first_audio_ms)}</b> · full synthesis <b>{fmt(last.tts_ms)}</b> · real-time factor <b>{last.tts_realtime_factor??'—'}</b></span><span>Generated audio <b>{last.audio_seconds??'—'}s</b> in <b>{last.tts_chunks??'—'}</b> chunks</span></div></>:<div className="empty-panel">Complete a roleplay turn to populate stage timings.</div>}</section>
      <section className="monitor-panel mic-panel"><div className="panel-title"><div><p className="eyebrow">MICROPHONE</p><h2>Input diagnostics</h2></div><span className={`mic-status ${micActive?'active':''}`}>{micActive?'Live input':'Not recording'}</span></div><div className="mic-diagnostics"><div><small>Selected device</small><strong>{deviceEvent?.device||'No capture recorded'}</strong><span>{deviceEvent?.sample_rate?`${deviceEvent.sample_rate} Hz · ${deviceEvent.channel_count||1} channel${deviceEvent.channel_count===1?'':'s'}`:'Click Speak inside a roleplay to connect.'}</span></div><div><small>Current state</small><strong>{micActive?(latestMic?.state||latestMic?.name):latestMic?.name||'Idle'}</strong><span>{latestMic?.error||'Speech uses an adaptive noise threshold and stops after 1.2 seconds of silence.'}</span></div><div><small>Input level</small><strong>{fmt(latestMic?.level_percent,'%')}</strong><div className="diagnostic-meter"><i style={{width:`${latestMic?.level_percent||0}%`}}/></div><span>Peak {fmt(latestMic?.peak_percent,'%')} · trigger {fmt(latestMic?.threshold_percent,'%')}</span></div></div><div className="transcript-monitor"><small>Latest detected speech</small><p>{transcriptEvent?.transcript||'No transcription yet. Start a roleplay, click Speak, and talk normally.'}</p>{transcriptEvent&&<span>Whisper completed in {fmt(transcriptEvent.duration_ms)} at {new Date(transcriptEvent.timestamp).toLocaleTimeString()}</span>}</div><div className="mic-event-strip">{micEvents.slice(0,8).map((event,i)=><span key={`${event.timestamp}-${i}`} className={event.ok?'':'failed'}><b>{event.name.replaceAll('_',' ')}</b>{event.level_percent!=null&&` · ${Math.round(event.level_percent)}%`}</span>)}</div></section>
    <section className="monitor-panel"><div className="panel-title"><div><p className="eyebrow">RECENT EVENTS</p><h2>Request log</h2></div><span>{snapshot.http.errors} errors · {snapshot.http.error_rate_percent}% rate</span></div><div className="event-table"><div><b>Time</b><b>Category</b><b>Operation</b><b>Duration</b><b>Result</b></div>{snapshot.recent.map((event,i)=><div key={`${event.timestamp}-${i}`}><span>{new Date(event.timestamp).toLocaleTimeString()}</span><span>{event.category}</span><span>{event.name}</span><span>{fmt(event.duration_ms)}</span><span className={event.ok?'event-ok':'event-bad'}>{event.ok?'OK':'Error'}</span></div>)}</div></section>
    <p className="monitor-note">Guide: round trip includes local browser and proxy overhead; HTTP timing is server work; LLM first token measures responsiveness; TTS real-time factor compares synthesis time with generated audio duration. Microphone transcripts and device details stay in this local process, are limited to the recent-event window, and disappear on restart or reset. Treat thresholds as test aids, not production service-level guarantees.</p>
  </main>
}

function Settings({ onChanged, embedded=false }){
  const [state, setState] = useState(null)
  const [recognition,setRecognition]=useState(null)
  const [recognitionEngine,setRecognitionEngine]=useState('nemotron')
  const [recognitionDevice,setRecognitionDevice]=useState('auto')
  const [selectedVoice, setSelectedVoice] = useState('af_heart')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState({ text: '', type: '' })
  const [testText, setTestText] = useState('Hello! I am Hikari, your workplace training assistant.')
  const [testing, setTesting] = useState(false)
  const [auditionPhase,setAuditionPhase]=useState('idle')
  const [testLatency, setTestLatency] = useState(null)
  const [languagePrefs, setLanguagePrefs] = useState({preferred_language:'English',native_language:'Urdu',proficiency_level:'beginner',captions_enabled:true})
  const audioContextRef = useRef(null)
  const currentSourceRef = useRef(null)
  const auditionRequest=useRef(null),auditionSources=useRef(new Set())
  useEffect(()=>()=>{auditionRequest.current?.abort();auditionSources.current.forEach(source=>{try{source.stop()}catch{}});audioContextRef.current?.close().catch(()=>{})},[])

  const load = useCallback(async () => {
    try {
      const [next, preferences, speech] = await Promise.all([api('/tts/engines'), api('/auth/settings'),api('/stt/engines')])
      setState(next)
      setRecognition(speech);setRecognitionEngine(speech.selected);setRecognitionDevice(speech.device)
      setLanguagePrefs(preferences)
      if (next.current_voice) setSelectedVoice(next.current_voice)
    } catch (e) {
      setMessage({ text: e.message, type: 'error' })
    }
  }, [])

  useEffect(() => { load() }, [load])

  const saveLanguagePrefs = async () => {
    setBusy(true)
    try {
      const saved = await api('/auth/settings', {
        method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(languagePrefs)
      })
      setLanguagePrefs(saved)
      setMessage({text:'Language and caption preferences saved.',type:'success'})
      await onChanged()
    } catch (e) {
      setMessage({text:e.message,type:'error'})
    } finally { setBusy(false) }
  }

  const applyEngine = async (engineId, voiceId = selectedVoice) => {
    setBusy(true)
    setMessage({ text: `Switching to ${engineId}… Please wait.`, type: 'info' })
    try {
      const payload = { engine: engineId }
      if (engineId === 'kokoro' && voiceId) payload.voice = voiceId
      const next = await api('/tts/engine', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      setState(next)
      if (next.current_voice) setSelectedVoice(next.current_voice)
      const engineObj = next.engines.find(e => e.id === next.active)
      const engineName = engineObj?.name || next.active
      setMessage({
        text: `${engineName} is now active${next.active === 'kokoro' ? ` (Voice: ${voiceId})` : ''}.`,
        type: 'success'
      })
      await onChanged()
    } catch (e) {
      setMessage({ text: `Failed to switch voice engine: ${e.message}`, type: 'error' })
      await load()
    } finally {
      setBusy(false)
    }
  }

  const applyRecognition=async()=>{
    setBusy(true);setMessage({text:'Loading recognition model. Keep the microphone paused…',type:'info'})
    try{
      const next=await api('/stt/engine',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({engine:recognitionEngine,device:recognitionDevice})})
      setRecognition(next)
      setMessage({text:`Recognition active: ${next.runtime?.model||next.selected} on ${next.runtime?.device||'unknown'}.${next.runtime?.fallback_reason?` ${next.runtime.fallback_reason}`:''}`,type:'success'})
      await onChanged()
    }catch(error){setMessage({text:error.message,type:'error'})}
    finally{setBusy(false)}
  }

  const stopAudio = () => {
    auditionRequest.current?.abort()
    auditionSources.current.forEach(source=>{try{source.stop()}catch{}});auditionSources.current.clear()
    if (currentSourceRef.current) {
      try { currentSourceRef.current.stop() } catch {}
      currentSourceRef.current = null
    }
    setTesting(false)
    setAuditionPhase('idle')
  }

  const testVoice = async () => {
    if (testing) {
      stopAudio()
      return
    }
    if (!testText.trim()) return
    setTesting(true)
    setAuditionPhase('generating');setTestLatency(null)
    const controller=new AbortController();auditionRequest.current=controller
    setMessage({ text: '', type: '' })
    const startTime = performance.now()

    try {
      if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
        const AudioCtx = window.AudioContext || window.webkitAudioContext
        audioContextRef.current = new AudioCtx()
      }
      if (audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume()
      }

      const response = await fetch(`${API}/tts/stream`, {
        method: 'POST',
        signal:controller.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: testText, correlation_id: 'test-audition' })
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || 'Voice synthesis failed.')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let pending = ''
      const audioChunks = []
      let firstChunkTime = null
      let playbackEnd=audioContextRef.current.currentTime

      while (true) {
        const { value, done } = await reader.read()
        pending += decoder.decode(value || new Uint8Array(), { stream: !done })
        const lines = pending.split('\n')
        pending = lines.pop() || ''
        for (const line of lines) {
          if (!line.trim()) continue
          const event = JSON.parse(line)
          if(event.tts_timing)console.info('[Hikari TTS latency]',event.tts_timing)
          if (event.type === 'error') throw new Error(event.message)
          if (event.type === 'audio') {
            if (!firstChunkTime) firstChunkTime = Math.round(performance.now() - startTime)
            const binary = atob(event.audio_b64)
            const bytes = new Uint8Array(binary.length)
            for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
            audioChunks.push(bytes)
            const context=audioContextRef.current
            const decoded=await context.decodeAudioData(bytes.buffer.slice(0))
            if(controller.signal.aborted)return
            const source=context.createBufferSource();source.buffer=decoded;source.connect(context.destination)
            auditionSources.current.add(source);source.onended=()=>auditionSources.current.delete(source)
            source.start(Math.max(context.currentTime+.05,playbackEnd))
            playbackEnd=Math.max(context.currentTime+.05,playbackEnd)+decoded.duration
            setAuditionPhase('playing')
          }
        }
        if (done) break
      }

      if (!audioChunks.length) throw new Error('No audio returned from engine.')

      setTestLatency(firstChunkTime || Math.round(performance.now() - startTime))

      await new Promise(resolve=>setTimeout(resolve,Math.max(0,playbackEnd-audioContextRef.current.currentTime)*1000+50))
    } catch (e) {
      if(e.name!=='AbortError')setMessage({ text: `Audio audition error: ${e.message}`, type: 'error' })
    } finally {if(auditionRequest.current===controller){setTesting(false);setAuditionPhase('idle')}}
  }

  if (!state) {
    return (
      <section className={`page settings-page${embedded?' settings-embedded':''}`}>
        <header className="page-head compact">
          <div>
            <p className="eyebrow">PREFERENCES</p>
            <h1>Voice Settings</h1>
          </div>
        </header>
        {message.text ? <div className="error">{message.text}</div> : <Loading />}
      </section>
    )
  }

  const activeEngineObj = state.engines.find(e => e.id === state.active)
  const isKokoroActive = state.active === 'kokoro'

  return (
    <section className={`page settings-page${embedded?' settings-embedded':''}`}>
      <header className="page-head">
        <div>
          <p className="eyebrow">VOICE & ENGINE PREFERENCES</p>
          <h2>Speech & Audio Settings</h2>
          <p>Configure text-to-speech engines, switch voice personas, and test local voice generation.</p>
        </div>
        <div className="active-engine-badge">
          <span className="live-dot ready" />
          <div>
            <strong>{activeEngineObj?.name || state.active} Active</strong>
            <small>{state.sample_rate / 1000} kHz · {state.active === 'kokoro' ? `${selectedVoice}` : state.runtime ? `${String(state.runtime.backend||state.runtime.device||'local').toUpperCase()} · ${state.runtime.device_name||'Local device'}` : 'Native'}</small>
          </div>
        </div>
      </header>

      {message.text && (
        <div className={`settings-alert ${message.type}`}>
          <span>{message.type === 'error' ? '⚠' : message.type === 'success' ? '✓' : 'ℹ'}</span>
          <p>{message.text}</p>
          <button type="button" aria-label="Dismiss notification" onClick={() => setMessage({ text: '', type: '' })}>✕</button>
        </div>
      )}

      <section className="settings-section">
        <div className="section-title"><div><p className="eyebrow">SPEECH RECOGNITION</p><h2>Microphone recognition engine</h2><p>Pause the microphone before switching. This changes recognition, not the AI voice.</p></div></div>
        <div className="voice-picker-row">
          <label>Recognition model<select value={recognitionEngine} disabled={busy} onChange={event=>setRecognitionEngine(event.target.value)}>{recognition?.engines.map(engine=><option key={engine.id} value={engine.id} disabled={!engine.installed}>{engine.name}{engine.installed?'':' — not installed'}</option>)}</select></label>
          <label>Execution device<select value={recognitionDevice} disabled={busy} onChange={event=>setRecognitionDevice(event.target.value)}><option value="auto">Automatic (GPU when available)</option><option value="cpu">CPU only</option></select></label>
          <button className="primary-outline-btn" disabled={busy||!recognition?.engines.find(engine=>engine.id===recognitionEngine)?.installed} onClick={applyRecognition}>Apply recognition mode</button>
        </div>
        <p>{recognition?.engines.find(engine=>engine.id===recognitionEngine)?.description}</p>
        <p>For English on CPU, try Nemotron with “CPU only”: it keeps live recognition and uses the same model weights. Whisper Small is the lower-cost multilingual option; Medium favors capacity over speed.</p>
        <small>Running: {recognition?.runtime?.model||'Not loaded'} · {recognition?.runtime?.device||'—'} · {recognition?.runtime?.compute_type||'—'}. CPU speed depends on the machine; equal GPU speed is not guaranteed.</small>
      </section>

      <SessionAudioSettings request={api}/>
      <VoiceInputTest request={api} runtime={recognition?.runtime}/>

      <section className="settings-section language-preferences">
        <div className="section-title"><div><p className="eyebrow">LANGUAGE LEARNING</p><h2>Dialogue & caption languages</h2><p>Beginner English stays spoken in English while captions are translated into your native language.</p></div></div>
        <div className="voice-picker-row">
          <label>Training language<select value={languagePrefs.preferred_language} onChange={e=>setLanguagePrefs({...languagePrefs,preferred_language:e.target.value})}>{['English','Japanese','Arabic','Chinese','Korean'].map(item=><option key={item}>{item}</option>)}</select></label>
          <label>Native caption language<select value={languagePrefs.native_language} onChange={e=>setLanguagePrefs({...languagePrefs,native_language:e.target.value})}>{['Urdu','English','Japanese','Arabic','Chinese','Korean'].map(item=><option key={item}>{item}</option>)}</select></label>
          <label>English proficiency<select value={languagePrefs.proficiency_level} onChange={e=>setLanguagePrefs({...languagePrefs,proficiency_level:e.target.value})}><option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select></label>
          <label>Translated captions<input type="checkbox" checked={languagePrefs.captions_enabled} onChange={e=>setLanguagePrefs({...languagePrefs,captions_enabled:e.target.checked})}/></label>
          <button className="primary-outline-btn" onClick={saveLanguagePrefs} disabled={busy}>Save language preferences</button>
        </div>
      </section>

      {/* TTS Engine Cards */}
      <section className="settings-section">
        <div className="section-title">
          <div>
            <p className="eyebrow">TTS ENGINES</p>
            <h2>Choose Speech Engine</h2>
          </div>
          {!isKokoroActive && (
            <button
              className="primary-outline-btn"
              onClick={() => applyEngine('kokoro', selectedVoice)}
              disabled={busy}
            >
              <Icon name="sparkles" /> Set Kokoro as Default
            </button>
          )}
        </div>

        {state.active==='chattts'&&state.runtime&&<div className={`settings-alert ${state.runtime.backend==='cuda'?'success':'error'}`}><span>{state.runtime.backend==='cuda'?'✓':'⚠'}</span><p><strong>ChatTTS acceleration:</strong> {state.runtime.device} · {state.runtime.device_name}. Model modules: {Object.entries(state.runtime.module_devices||{}).map(([name,device])=>`${name} ${device}`).join(', ')}.</p></div>}

        <div className="engine-cards-grid">
          {state.engines.map(engine => {
            const isActive = engine.id === state.active
            const isDefault = engine.default || engine.id === 'kokoro'

            return (
              <article
                key={engine.id}
                className={`engine-card-option ${isActive ? 'active' : ''} ${isDefault ? 'default-card' : ''}`}
              >
                <div className="engine-card-head">
                  <div>
                    <div className="badges-row">
                      {isDefault && <span className="badge badge-default">★ Default & Recommended</span>}
                      {isActive && <span className="badge badge-active">Active</span>}
                      {engine.latency_label && <span className="badge badge-latency">{engine.latency_label}</span>}
                    </div>
                    <h3>{engine.name}</h3>
                  </div>
                  <span className={`radio-indicator ${isActive ? 'checked' : ''}`}>
                    {isActive && <i />}
                  </span>
                </div>

                <p className="engine-desc">{engine.description}</p>

                {engine.features && (
                  <ul className="engine-feature-list">
                    {engine.features.map((feat, i) => (
                      <li key={i}>✓ {feat}</li>
                    ))}
                  </ul>
                )}

                <div className="engine-card-foot">
                  <span className="lang-tag">{engine.language}</span>
                  <button
                    className={`engine-action-btn ${isActive ? 'btn-active' : 'btn-switch'}`}
                    disabled={busy || isActive || (!engine.installed && !engine.download_on_select)}
                    onClick={(e) => {
                      e.stopPropagation()
                      applyEngine(engine.id, selectedVoice)
                    }}
                  >
                    {isActive ? 'Active' : busy ? 'Loading…' : !engine.installed ? (engine.download_on_select ? 'Download & Switch' : 'Not installed') : 'Switch Engine'}
                  </button>
                </div>
              </article>
            )
          })}
        </div>
      </section>

      {/* Kokoro Voice Persona Selection (active when Kokoro is chosen) */}
      {isKokoroActive && (
        <section className="settings-section">
          <div className="section-title">
            <div>
              <p className="eyebrow">VOICE PERSONA</p>
              <h2>Kokoro Voice Selection</h2>
            </div>
            <span className="voice-active-indicator">Current: <strong>{selectedVoice}</strong></span>
          </div>

          <div className="voice-selection-box">
            <div className="voice-picker-row">
              <label htmlFor="voice-select">
                <strong>Speaker Voice Profile</strong>
                <small>Select from high-definition natural voices (American, British, Japanese).</small>
              </label>
              <select
                id="voice-select"
                value={selectedVoice}
                onChange={(e) => {
                  const newVoice = e.target.value
                  setSelectedVoice(newVoice)
                  applyEngine('kokoro', newVoice)
                }}
                disabled={busy}
              >
                {state.voices?.map(v => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="voice-chips-grid">
              {state.voices?.map(v => (
                <button
                  key={v.id}
                  className={`voice-chip ${selectedVoice === v.id ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedVoice(v.id)
                    applyEngine('kokoro', v.id)
                  }}
                  disabled={busy}
                >
                  <div>
                    <strong>{v.name.split(' ')[0]}</strong>
                    <small>{v.gender} · {v.accent}</small>
                  </div>
                  {selectedVoice === v.id && <span className="chip-check">✓</span>}
                </button>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Real-time Voice Audition Lab */}
      <section className="settings-section audition-section">
        <div className="section-title">
          <div>
            <p className="eyebrow">INTERACTIVE AUDITION</p>
            <h2>Test Voice Playback</h2>
          </div>
          {testLatency && (
            <span className="latency-indicator">
              First audio received in <strong>{testLatency} ms</strong>
            </span>
          )}
        </div>

        <div className="audition-panel">
          <div className="audition-input-group">
            <label htmlFor="audition-text">Sample Phrase</label>
            <input
              id="audition-text"
              type="text"
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
              placeholder="Enter phrase to synthesize and test audio output…"
              disabled={testing}
            />
            <div className="sample-phrases">
              <span>Try quick phrases:</span>
              <button
                type="button"
                onClick={() => setTestText('Hello! I am Hikari, your workplace training assistant.')}
              >
                Greeting
              </button>
              <button
                type="button"
                onClick={() => setTestText('Thank you for contacting us today. How may I assist with your inquiry?')}
              >
                Customer Service
              </button>
              <button
                type="button"
                onClick={() => setTestText('Great job on your phrasing! That was clear, courteous, and reassuring.')}
              >
                Coaching Feedback
              </button>
            </div>
          </div>

          <div className="audition-actions">
            <button
              className={`primary test-play-btn ${testing ? 'playing' : ''}`}
              onClick={testVoice}
              disabled={busy||!testText.trim()}
            >
              <Icon name={testing ? 'stop' : 'speaker'} />
              {testing ? auditionPhase==='generating'?'Generating… Click to stop':'Playing… Click to stop' : 'Test Voice Audio'}
            </button>
            {testing && (
              <div className="audio-wave">
                <i /><i /><i /><i /><i />
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Engine Architecture Benchmarks */}
      <section className="settings-section">
        <div className="section-title">
          <div>
            <p className="eyebrow">SYSTEM ARCHITECTURE</p>
            <h2>Engine Benchmarks & Resource Profile</h2>
          </div>
        </div>

        <div className="benchmarks-grid">
          <div className="benchmark-card highlighted">
            <span className="bm-pill">DEFAULT</span>
            <h4>Kokoro ONNX</h4>
            <div className="bm-metric">
              <small>Time to First Audio</small>
              <strong>&lt; 150 ms</strong>
            </div>
            <div className="bm-metric">
              <small>System Memory</small>
              <strong>~400 MB</strong>
            </div>
            <div className="bm-metric">
              <small>Optimal Usage</small>
              <span>Instant roleplay conversations on CPU</span>
            </div>
          </div>

          <div className="benchmark-card">
            <span className="bm-pill neutral">ADVANCED</span>
            <h4>ChatTTS</h4>
            <div className="bm-metric">
              <small>Time to First Audio</small>
              <strong>~2,500 ms</strong>
            </div>
            <div className="bm-metric">
              <small>System Memory</small>
              <strong>~4 GB</strong>
            </div>
            <div className="bm-metric">
              <small>Optimal Usage</small>
              <span>Conversational prosody & laughter tokens</span>
            </div>
          </div>

          <div className="benchmark-card">
            <span className="bm-pill neutral">SPECIALIZED</span>
            <h4>VITS Piper</h4>
            <div className="bm-metric">
              <small>Time to First Audio</small>
              <strong>~300 ms</strong>
            </div>
            <div className="bm-metric">
              <small>System Memory</small>
              <strong>~200 MB</strong>
            </div>
            <div className="bm-metric">
              <small>Optimal Usage</small>
              <span>Native Japanese & Arabic language training</span>
            </div>
          </div>
        </div>
      </section>
    </section>
  )
}

function Loading(){return <div className="loading"><span>光</span><p>Preparing your training space…</p></div>}

function SettingsModal({ isOpen, onClose, onChanged }){
  const dialog=useRef(null)
  const closeRef=useRef(onClose);closeRef.current=onClose
  useEffect(()=>{
    if(!isOpen)return
    const previous=document.activeElement,overflow=document.body.style.overflow
    document.body.style.overflow='hidden';dialog.current?.querySelector('button')?.focus()
    const keydown=event=>{
      if(event.key==='Escape'){event.preventDefault();closeRef.current()}
      if(event.key==='Tab'){
        const controls=[...dialog.current.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled)')]
        const first=controls[0],last=controls[controls.length-1]
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
      }
    }
    document.addEventListener('keydown',keydown)
    return()=>{document.body.style.overflow=overflow;document.removeEventListener('keydown',keydown);previous?.focus()}
  },[isOpen])
  if (!isOpen) return null
  return (
    <div className="settings-modal-backdrop" onClick={onClose}>
      <div ref={dialog} className="settings-modal-dialog" role="dialog" aria-modal="true" aria-labelledby="speech-settings-title" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <p className="eyebrow">PREFERENCES</p>
            <h2 id="speech-settings-title">Speech & Voice Settings</h2>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close Settings">✕</button>
        </div>
        <div className="modal-scroll-area">
          <Settings onChanged={onChanged} />
        </div>
      </div>
    </div>
  )
}

export default function App(){
  const [privacyAccount,setPrivacyAccount]=useState('')
  const [account,setAccount]=useState(undefined),[view,setView]=useState('home'),[dashboard,setDashboard]=useState(null),[skills,setSkills]=useState([]),[history,setHistory]=useState([]),[docs,setDocs]=useState([]),[activities,setActivities]=useState([]),[resources,setResources]=useState([]),[userSettings,setUserSettings]=useState(null),[health,setHealth]=useState({status:'loading'}),[session,setSession]=useState(null),[preparation,setPreparation]=useState(null),[assessment,setAssessment]=useState(null),[error,setError]=useState(''),[settingsModal,setSettingsModal]=useState(false),[starting,setStarting]=useState(false)
  const load=useCallback(async()=>{try{const [d,s,h,dc,he,ac,rs,prefs]=await Promise.all([api('/dashboard'),api('/skills'),api('/sessions'),api('/documents'),api('/health'),api('/training/activities'),api('/resources'),api('/auth/settings')]);setDashboard(d);setSkills(s);setHistory(h);setDocs(dc);setHealth(he);setActivities(ac);setResources(rs);setUserSettings(prefs);setError('')}catch(e){if(e.status===401)setAccount(null);else setError(e.message)}},[])
  useEffect(()=>{api('/auth/me').then(async result=>{setAccount(result.user);await load()}).catch(e=>{if(e.status===401)setAccount(null);else{setAccount(null);setError(e.message)}})},[load])
  const authenticated=async user=>{setAccount(user);await load()}
  const logout=async()=>{await api('/auth/logout',{method:'POST'}).catch(()=>{});setAccount(null);setDashboard(null);setSession(null);setPreparation(null);setAssessment(null);setView('home')}
  const start=async(skillId,difficulty='intermediate',activityId=null,options={})=>{try{setError('');const preview=await api('/scenarios/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({skill_id:skillId,difficulty,activity_id:activityId,...options})});setPreparation(preview)}catch(e){setError(e.message)}}
  const beginSession=async()=>{try{setStarting(true);setError('');const s=await api('/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({skill_id:preparation.skill_id,difficulty:preparation.difficulty,activity_id:preparation.activity_id,preview_id:preparation.preview_id})});setSession(s);setPreparation(null);setAssessment(null)}catch(e){setError(e.message)}finally{setStarting(false)}}
  const complete=async()=>{try{const a=await api(`/sessions/${session.id}/complete`,{method:'POST'});setAssessment(a);await load()}catch(e){setError(e.message);throw e}}
  if(account===undefined)return <Loading/>
  if(!account)return <AuthScreen onAuthenticated={authenticated}/>
  if(privacyAccount!==account.id&&localStorage.getItem(`hikari-privacy-v1-${account.id}`)!=='accepted')return <main className="auth-page"><section className="auth-panel"><div className="auth-card"><h2>Before you start training</h2><p>Your transcript, AI responses, assessments and progress are saved in your local Hikari database. Organization documents are shared only within that organization.</p><p>The configured AI provider may receive your conversation and relevant excerpts from uploaded documents. Do not share passwords or confidential data without your organization’s permission. Microphone and camera access are optional browser permissions; pose analysis runs locally.</p><p>Scores are prototype estimates, not certified language proficiency or medical posture advice.</p><button className="h-primary" onClick={()=>{localStorage.setItem(`hikari-privacy-v1-${account.id}`,'accepted');setPrivacyAccount(account.id)}}>I understand — continue</button><button className="h-small" onClick={logout}>Sign out</button></div></section></main>
  if(session&&assessment)return <Assessment session={session} assessment={assessment} onDone={()=>{setSession(null);setAssessment(null);setView('home')}}/>
  if(session)return <><Roleplay session={session} setSession={setSession} onComplete={complete} onCancel={async()=>{await api(`/sessions/${session.id}/cancel`,{method:'POST'});setSession(null);setAssessment(null);await load()}} health={health} userSettings={userSettings} onOpenSettings={()=>setSettingsModal(true)}/><SettingsModal isOpen={settingsModal} onClose={()=>setSettingsModal(false)} onChanged={load}/></>
  if(preparation)return <><ScenarioPreparation briefing={preparation} documents={docs} onConfigure={options=>start(preparation.skill_id,preparation.difficulty,preparation.activity_id,{preview_id:preparation.preview_id,document_ids:preparation.document_ids,posture_enabled:preparation.posture_enabled,...options})} onBegin={beginSession} onCancel={()=>setPreparation(null)} busy={starting}/>{error&&<div className="global-error" role="alert">{error}</div>}</>
  return <div className="app-shell"><Sidebar view={view} setView={setView} health={health} user={dashboard?.user||account} onLogout={logout}/><div className="content">{error&&<div className="global-error">{error}</div>}{view==='home'&&<HomePage data={dashboard} onStart={start} setView={setView}/>} {view==='training'&&<TrainingPage activities={activities} onStart={start}/>} {view==='progress'&&<ProgressPage data={dashboard}/>} {view==='plan'&&<PlanPage data={dashboard} onStart={start}/>} {view==='resources'&&<ResourcesPage resources={resources} docs={docs} reload={load}/>} {view==='monitor'&&<Monitor/>} {view==='settings'&&<SettingsHub dashboard={dashboard} health={health} setView={setView} onChanged={load}/>}{view==='settings'&&account.is_admin&&<Administration request={api}/>}</div><SettingsModal isOpen={settingsModal} onClose={()=>setSettingsModal(false)} onChanged={load}/></div>
}
