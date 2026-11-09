import {useCallback,useEffect,useMemo,useState} from 'react'
import './Administration.css'

const parseList=value=>{try{const out=JSON.parse(value||'[]');return Array.isArray(out)?out:[]}catch{return []}}
const lines=value=>value.split('\n').map(item=>item.trim()).filter(Boolean)
const TABS={
  skills:{label:'Skills',rows:c=>c.skills,title:r=>r.name,detail:r=>r.category,active:r=>r.active,
    blank:{name:'',description:'',category:'workplace',active:true},
    load:r=>({name:r.name,description:r.description||'',category:r.category||'workplace',active:!!r.active}),
    fields:[['name','Name'],['description','Description','area'],['category','Category'],['active','Active','check']]},
  subskills:{label:'Subskills',rows:c=>c.subskills,title:r=>r.name,detail:r=>r.skill_id,active:r=>r.active,
    blank:{skill_id:'',name:'',description:'',active:true},
    load:r=>({skill_id:r.skill_id,name:r.name,description:r.description||'',active:!!r.active}),
    fields:[['skill_id','Skill','skill'],['name','Name'],['description','Description','area'],['active','Active','check']]},
  activities:{label:'Lessons',rows:c=>c.activities,title:r=>r.title,detail:r=>`${r.primary_skill_id}${r.upgraded?' · case pack':''}`,active:r=>r.active,
    blank:{skill_id:'',title:'',description:'',context:'',objectives:'',success_criteria:'',opening_situation:'',learner_role:'Learner',ai_roles:'Colleague',roleplay_mode:'one_to_one',difficulty:'beginner',estimated_minutes:15,posture_mode:'off',knowledge_mode:'off'},
    load:r=>({posture_mode:r.posture_mode||'off',knowledge_mode:r.knowledge_mode||'off'}),
    editFields:[['posture_mode','Posture assessment','select',['off','optional']],['knowledge_mode','Company knowledge','select',['off','optional','required']]],
    fields:[['skill_id','Skill','skill'],['title','Title'],['description','Description','area'],['context','Scenario','area'],['objectives','Objectives, one per line','area'],['success_criteria','Success criteria, one per line','area'],['opening_situation','Opening line','area'],['learner_role','Learner role'],['ai_roles','AI roles, one per line','area'],['roleplay_mode','Roleplay mode','select',['one_to_one','learner_with_ai_team','ai_team_vs_learner','round_robin']],['difficulty','Difficulty','select',['beginner','intermediate','advanced','adaptive']],['estimated_minutes','Minutes','number'],['posture_mode','Posture assessment','select',['off','optional']],['knowledge_mode','Company knowledge','select',['off','optional','required']]]},
  scenarios:{label:'Scenarios',rows:c=>c.scenarios,title:r=>r.activity_id,detail:r=>`version ${r.version||1}`,active:r=>r.active,noCreate:true,
    load:r=>({context:r.context||'',objectives:parseList(r.objectives_json).join('\n'),success_criteria:parseList(r.success_criteria_json).join('\n'),opening_situation:r.opening_situation||'',active:!!r.active}),
    fields:[['context','Scenario','area'],['objectives','Objectives, one per line','area'],['success_criteria','Success criteria, one per line','area'],['opening_situation','Opening line','area'],['active','Active','check']]},
}

function payload(tab,editing,form){
  if(tab==='activities'&&editing)return ['lesson-settings',form]
  if(tab==='activities')return ['activities',{...form,objectives:lines(form.objectives),success_criteria:lines(form.success_criteria),ai_roles:lines(form.ai_roles),estimated_minutes:Number(form.estimated_minutes),active:true}]
  if(tab==='scenarios')return ['scenarios',{...form,objectives:lines(form.objectives),success_criteria:lines(form.success_criteria)}]
  return [tab,form]
}

export default function Administration({request}) {
  const [catalog,setCatalog]=useState(null),[tab,setTab]=useState('skills'),[query,setQuery]=useState(''),[identifier,setIdentifier]=useState(''),[editing,setEditing]=useState(false),[form,setForm]=useState(TABS.skills.blank),[upgraded,setUpgraded]=useState(false),[message,setMessage]=useState(''),[busy,setBusy]=useState(false),[chunks,setChunks]=useState('')
  const load=useCallback(async()=>{
    try{const [next,configuration]=await Promise.all([request('/admin/catalog'),request('/admin/configuration')]);setCatalog(next);setChunks(String(configuration.max_document_chunks))}
    catch(error){setMessage(error.message)}
  },[request])
  useEffect(()=>{load()},[load])
  const spec=TABS[tab]
  const rows=useMemo(()=>catalog?spec.rows(catalog).filter(row=>`${spec.title(row)} ${row.id}`.toLowerCase().includes(query.toLowerCase())):[],[catalog,spec,query])
  const choose=key=>{setTab(key);setQuery('');setEditing(false);setIdentifier('');setUpgraded(false);setForm(TABS[key].blank||{});setMessage('')}
  const open=row=>{setEditing(true);setIdentifier(row.id);setUpgraded(!!row.upgraded);setForm(spec.load(row));setMessage('')}
  const fresh=()=>{setEditing(false);setIdentifier('');setUpgraded(false);setForm(spec.blank);setMessage('')}
  const save=async event=>{
    event.preventDefault();setBusy(true);setMessage('')
    try{
      const [path,body]=payload(tab,editing,form)
      await request(`/admin/${path}/${encodeURIComponent(identifier)}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
      await load();setEditing(true);setMessage('Saved. Sessions already started keep the version they began with.')
    }catch(error){setMessage(error.message)}finally{setBusy(false)}
  }
  const saveChunks=async()=>{try{setMessage('');await request('/admin/configuration',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({max_document_chunks:Number(chunks)})});setMessage('Configuration saved.')}catch(error){setMessage(error.message)}}
  const fields=tab==='activities'&&editing?spec.editFields:spec.fields
  const field=([key,label,type,options])=>{
    const value=form[key]??''
    const change=next=>setForm({...form,[key]:next})
    if(type==='check')return <label className="admin-check" key={key}><input type="checkbox" checked={!!value} onChange={e=>change(e.target.checked)}/>{label}</label>
    if(type==='area')return <label key={key}>{label}<textarea value={value} required={key!=='description'} onChange={e=>change(e.target.value)}/></label>
    if(type==='select')return <label key={key}>{label}<select value={value} onChange={e=>change(e.target.value)}>{options.map(option=><option key={option} value={option}>{option.replaceAll('_',' ')}</option>)}</select></label>
    if(type==='skill')return <label key={key}>{label}<select value={value} required onChange={e=>change(e.target.value)}><option value="">Choose a skill</option>{catalog?.skills.map(skill=><option key={skill.id} value={skill.id}>{skill.name}</option>)}</select></label>
    return <label key={key}>{label}<input type={type==='number'?'number':'text'} value={value} required onChange={e=>change(e.target.value)}/></label>
  }
  return <section className="h-card admin-panel"><h2>Platform administration</h2><p>Changes affect future training, not completed sessions. Deactivate records rather than deleting learner history.</p>
    <div className="admin-tabs" role="tablist">{Object.entries(TABS).map(([key,item])=><button key={key} role="tab" aria-selected={tab===key} className={tab===key?'active':''} onClick={()=>choose(key)}>{item.label}{catalog?` (${item.rows(catalog).length})`:''}</button>)}</div>
    <div className="admin-layout">
      <div className="admin-list"><input aria-label="Search records" placeholder="Search…" value={query} onChange={e=>setQuery(e.target.value)}/>{!spec.noCreate&&<button className="h-soft" onClick={fresh}>+ New</button>}
        <ul>{rows.map(row=><li key={row.id}><button className={identifier===row.id?'selected':''} onClick={()=>open(row)}><strong>{spec.title(row)}</strong><small>{spec.detail(row)}{spec.active(row)?'':' · inactive'}</small></button></li>)}</ul>
      </div>
      <form className="admin-editor" onSubmit={save}>
        {spec.noCreate&&!editing?<p>Choose a scenario to edit it.</p>:<>
          <label>Identifier<input value={identifier} required disabled={editing} pattern="[a-z0-9][a-z0-9-]*" title="Lowercase letters, numbers and hyphens" onChange={e=>setIdentifier(e.target.value)}/></label>
          {upgraded&&<p className="admin-note">This lesson's conversation comes from a case pack in content/cases. Only its posture and knowledge settings are edited here.</p>}
          {fields.map(field)}
          <button className="h-primary" disabled={busy}>{busy?'Saving…':'Save'}</button>
        </>}
      </form>
    </div>
    <div className="admin-config"><label>Maximum chunks per document<input type="number" min="1" max="1000" value={chunks} onChange={e=>setChunks(e.target.value)}/></label><button className="h-soft" onClick={saveChunks}>Save setting</button></div>
    {message&&<p role="status">{message}</p>}
  </section>
}
