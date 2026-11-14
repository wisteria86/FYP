import { useState } from 'react'
import { Icon, skillIcon } from '../ui/Icon'

export function TrainingPage({ activities, onStart }) {
  const [query,setQuery]=useState(''),[category,setCategory]=useState('All'),[language,setLanguage]=useState('All languages')
  const roleplayLabels={one_to_one:'1-to-1 AI',learner_with_ai_team:'You + AI vs AI',ai_team_vs_learner:'AI Team vs You',round_robin:'Round Robin'}
  const multiCategory='Multiple AI Roleplay'
  const upgradedCategory='Upgraded lessons'
  const hasOlder=activities.some(item=>!item.upgraded)
  const categories=['All',...(hasOlder?[upgradedCategory]:[]),...new Set(activities.map(item=>item.skill_name)),multiCategory,'You + AI vs AI','AI Team vs You','Round Robin']
  const languages=['All languages',...new Set(activities.map(item=>item.training_language).filter(Boolean))]
  const filtered=activities.filter(item=>{
    const matchesCategory=category==='All'||(category===upgradedCategory&&item.upgraded)||category===item.skill_name||(category===multiCategory&&item.scenario_type==='multi_ai_roleplay')||category===roleplayLabels[item.roleplay_mode]
    const matchesLanguage=language==='All languages'||item.training_language===language
    return matchesCategory&&matchesLanguage&&`${item.title} ${item.description} ${item.subskills.join(' ')}`.toLowerCase().includes(query.toLowerCase())
  })
  // Upgraded lessons come first, keeping their order. Sorting a copy leaves the catalog untouched.
  const ordered=[...filtered].sort((a,b)=>Number(!!b.upgraded)-Number(!!a.upgraded))
  return <main className="page hikari-page"><header className="h-page-head"><div><h1>Training</h1><p>Practice languages, workplace communication, negotiation, interviews, critical thinking, and more.</p></div></header><div className="h-search"><Icon name="search"/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search training activities…"/></div><div className="h-filter-row language-filters">{languages.map(item=><button key={item} className={language===item?'active':''} onClick={()=>setLanguage(item)}>{item}</button>)}</div><div className="h-filter-row">{categories.map(item=><button key={item} className={category===item?'active':''} onClick={()=>setCategory(item)}>{item}</button>)}</div><section className="h-training-grid">{ordered.map(item=><article className="h-training-card" key={item.id}><span className="training-icon"><Icon name={skillIcon(item.primary_skill_id||item.id)}/></span>{hasOlder&&item.upgraded&&<span className="training-upgraded">Upgraded conversation</span>}{item.sequence_number&&<small>ENGLISH {item.sequence_number} / 30</small>}<h2>{item.title}</h2><p>{item.description}</p><div className="training-meta"><span><Icon name="clock"/> {item.estimated_minutes} min</span><span><Icon name="level"/> {item.proficiency_level||item.difficulty}</span></div><div className="h-tags">{item.training_language&&<span>{item.training_language}</span>}<span>{item.skill_name}</span><span>{roleplayLabels[item.roleplay_mode]||'AI Roleplay'}</span>{item.subskills.slice(0,1).map(tag=><span key={tag}>{tag}</span>)}</div><button className="h-primary" onClick={()=>onStart(item.primary_skill_id,item.difficulty==='adaptive'?'intermediate':item.difficulty,item.id)}><Icon name="play"/> Start Training</button></article>)}</section></main>
}
