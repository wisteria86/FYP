import './App.css'
import './Monitor.css'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useRoute } from './ui/router.mjs'
import Administration from './Administration'
import SavedLessons from './SavedLessons'
import TeamPanel from './TeamPanel'
import GoalsPanel from './GoalsPanel'
import LearningPath from './LearningPath'
import { Roleplay } from './call/Call'
import { AuthScreen } from './pages/Auth'
import { ScenarioPreparation } from './pages/Briefing'
import { HomePage } from './pages/Home'
import { Monitor } from './pages/Monitor'
import { PlanPage } from './pages/Plan'
import { ProgressPage } from './pages/Progress'
import { ResourcesPage } from './pages/Resources'
import { Assessment } from './pages/Results'
import { SettingsModal } from './pages/Settings'
import { SettingsHub } from './pages/SettingsHub'
import { TrainingPage } from './pages/Training'
import { Sidebar } from './ui/Sidebar'
import { Loading, api } from './ui/core'
import { useFeedback } from './ui/feedback'

export default function App(){
  const [privacyAccount,setPrivacyAccount]=useState('')
  const [route,navigate]=useRoute()
  const view=route.kind==='page'?route.view:'home'
  const setView=useCallback(next=>navigate({kind:'page',view:next}),[navigate])
  // The page to return to when a briefing, call or result closes.
  const lastPage=useRef('home')
  if(route.kind==='page')lastPage.current=route.view
  const leaving=useRef(null),opening=useRef('')
  const [account,setAccount]=useState(undefined),[dashboard,setDashboard]=useState(null),[skills,setSkills]=useState([]),[history,setHistory]=useState([]),[docs,setDocs]=useState([]),[activities,setActivities]=useState([]),[resources,setResources]=useState([]),[userSettings,setUserSettings]=useState(null),[health,setHealth]=useState({status:'loading'}),[session,setSession]=useState(null),[preparation,setPreparation]=useState(null),[assessment,setAssessment]=useState(null),[error,setError]=useState(''),[settingsModal,setSettingsModal]=useState(false),[starting,setStarting]=useState(false)
  const load=useCallback(async()=>{try{const [d,s,h,dc,he,ac,rs,prefs]=await Promise.all([api('/dashboard'),api('/skills'),api('/sessions'),api('/documents'),api('/health'),api('/training/activities'),api('/resources'),api('/auth/settings')]);setDashboard(d);setSkills(s);setHistory(h);setDocs(dc);setHealth(he);setActivities(ac);setResources(rs);setUserSettings(prefs);setError('')}catch(e){if(e.status===401)setAccount(null);else setError(e.message)}},[])
  useEffect(()=>{api('/auth/me').then(async result=>{setAccount(result.user);await load()}).catch(e=>{if(e.status===401)setAccount(null);else{setAccount(null);setError(e.message)}})},[load])
  const authenticated=async user=>{setAccount(user);await load()}
  const logout=async()=>{await api('/auth/logout',{method:'POST'}).catch(()=>{});setAccount(null);setDashboard(null);setSession(null);setPreparation(null);setAssessment(null);navigate({kind:'page',view:'home'},{replace:true})}
  const {toast}=useFeedback()
  useEffect(()=>{if(error){toast(error,{tone:'error'});setError('')}},[error,toast])
  const [challenge,setChallenge]=useState('')
  const start=async(skillId,difficulty='intermediate',activityId=null,options={},{replace=false}={})=>{try{setError('');const preview=await api('/scenarios/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({skill_id:skillId,difficulty,activity_id:activityId,...options})});setPreparation(preview);setSession(null);setAssessment(null);navigate({kind:'briefing',skill:preview.skill_id||skillId,level:difficulty,activity:preview.activity_id||activityId},{replace});return true}catch(e){setError(e.message);return false}}
  const beginSession=async()=>{try{setStarting(true);setError('');const s=await api('/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({skill_id:preparation.skill_id,difficulty:preparation.difficulty,activity_id:preparation.activity_id,preview_id:preparation.preview_id})});
    if(challenge&&s.runtime){const out=await api(`/sessions/${s.id}/actions`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'preferences',request_id:crypto.randomUUID(),data:{intensity:challenge,challenge:{gentle:'beginner',balanced:'intermediate',challenging:'advanced'}[challenge]}})});s.runtime=out.runtime}
    setChallenge('');setSession(s);setPreparation(null);setAssessment(null);navigate({kind:'session',id:s.id},{replace:true})}catch(e){setError(e.message)}finally{setStarting(false)}}
  // Opens a saved lesson: an active one resumes the call, a finished one shows its results.
  const openSession=useCallback(async(id,{replace=false}={})=>{
    const saved=await api(`/sessions/${id}`)
    if(saved.status!=='active'){
      if(!saved.assessment)throw new Error('This lesson has no results to show.')
      setPreparation(null);setSession(saved);setAssessment(saved.assessment);navigate({kind:'results',id},{replace:true});return
    }
    if(saved.runtime?.paused)await api(`/sessions/${id}/actions`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'resume',request_id:crypto.randomUUID()})})
    setPreparation(null);setSession(await api(`/sessions/${id}`));setAssessment(null);setError('')
    navigate({kind:'session',id},{replace})
  },[navigate])
  const resumeSession=id=>openSession(id).catch(e=>setError(e.message))
  const complete=async(endAttempt=false)=>{try{const a=await api(`/sessions/${session.id}/complete${endAttempt?'?end_attempt=true':''}`,{method:'POST'});setAssessment(a);navigate({kind:'results',id:session.id},{replace:true});await load()}catch(e){setError(e.message);throw e}}
  // Keep what is on screen in step with the address, including Back, Forward and refresh.
  useEffect(()=>{
    if(!account)return
    if(route.kind==='page'){
      if(preparation)setPreparation(null)
      if(session&&assessment){setSession(null);setAssessment(null)}
      else if(session&&leaving.current!=='busy'){
        // Leaving a live call pauses it so it can be resumed later; a deleted one needs nothing more.
        const current=session,deleted=leaving.current==='deleted'
        leaving.current='busy'
        const pause=async()=>{
          try{
            if(!deleted&&current.runtime)await api(`/sessions/${current.id}/actions`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'pause',request_id:crypto.randomUUID()})})
            else if(!deleted)await api(`/sessions/${current.id}/cancel`,{method:'POST'})
          }catch(e){setError(e.message)}
          finally{setSession(null);setAssessment(null);leaving.current=null;await load()}
        }
        pause()
      }
      return
    }
    const key=JSON.stringify(route)
    if(opening.current===key)return
    if(route.kind==='briefing'){
      if(preparation&&preparation.skill_id===route.skill&&(preparation.activity_id||null)===(route.activity||null))return
      opening.current=key
      start(route.skill,route.level,route.activity,{},{replace:true}).then(ok=>{opening.current='';if(!ok)navigate({kind:'page',view:lastPage.current},{replace:true})})
      return
    }
    if(session?.id===route.id&&(route.kind==='session'?!assessment:!!assessment))return
    opening.current=key
    openSession(route.id,{replace:true}).catch(e=>{setError(e.message);navigate({kind:'page',view:'home'},{replace:true})}).finally(()=>{opening.current=''})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[route,account,session?.id,!!assessment,preparation?.preview_id])
  const closeTo=(deleted=false)=>{if(session&&!assessment&&deleted)leaving.current='deleted';navigate({kind:'page',view:lastPage.current})}
  if(account===undefined)return <Loading/>
  if(!account)return <AuthScreen onAuthenticated={authenticated}/>
  if(privacyAccount!==account.id&&localStorage.getItem(`hikari-privacy-v1-${account.id}`)!=='accepted')return <main className="auth-page"><section className="auth-panel"><div className="auth-card"><h2>Before you start training</h2><p>Your transcript, AI responses, assessments and progress are saved in your local Hikari database. Organization documents are shared only within that organization.</p><p>The configured AI provider may receive your conversation and relevant excerpts from uploaded documents. Do not share passwords or confidential data without your organization’s permission. Microphone and camera access are optional browser permissions; pose analysis runs locally.</p><p>Scores are prototype estimates, not certified language proficiency or medical posture advice.</p><button className="h-primary" onClick={()=>{localStorage.setItem(`hikari-privacy-v1-${account.id}`,'accepted');setPrivacyAccount(account.id)}}>I understand — continue</button><button className="h-small" onClick={logout}>Sign out</button></div></section></main>
  if(session&&assessment)return <Assessment session={session} assessment={assessment} onRetry={async()=>{const {skill_id,difficulty,activity_id}=session;await start(skill_id,difficulty,activity_id)}} onDone={()=>navigate({kind:'page',view:'home'})} onPractiseMoment={id=>openSession(id).catch(e=>setError(e.message))}/>
  if(session)return <><Roleplay session={session} setSession={setSession} onComplete={complete} onCancel={async(deleted=false)=>closeTo(deleted)} health={health} userSettings={userSettings} onOpenSettings={()=>setSettingsModal(true)}/><SettingsModal isOpen={settingsModal} onClose={()=>setSettingsModal(false)} onChanged={load} advanced={!!account.is_admin}/></>
  if(preparation)return <><ScenarioPreparation briefing={preparation} documents={docs} onConfigure={options=>start(preparation.skill_id,preparation.difficulty,preparation.activity_id,{preview_id:preparation.preview_id,document_ids:preparation.document_ids,posture_enabled:preparation.posture_enabled,...options},{replace:true})} challenge={challenge} onChallenge={setChallenge} onBegin={beginSession} onCancel={()=>closeTo()} busy={starting}/></>
  return <div className="app-shell"><Sidebar view={view} setView={setView} health={health} user={dashboard?.user||account} onLogout={logout}/><div className="content">{view==='home'&&<HomePage data={dashboard} onStart={start} setView={setView} savedLessons={<SavedLessons lessons={history} skills={skills} onResume={resumeSession}/>}/>} {view==='path'&&<LearningPath request={api} onStart={start}/>} {view==='training'&&<TrainingPage activities={activities} onStart={start}/>} {view==='progress'&&<ProgressPage data={dashboard} history={history}/>} {view==='plan'&&<PlanPage data={dashboard} onStart={start}/>} {view==='resources'&&<ResourcesPage resources={resources} docs={docs} reload={load}/>} {view==='monitor'&&(account.is_admin?<Monitor/>:<HomePage data={dashboard} onStart={start} setView={setView} savedLessons={<SavedLessons lessons={history} skills={skills} onResume={resumeSession}/>}/>)} {view==='settings'&&<SettingsHub dashboard={dashboard} health={health} setView={setView} onChanged={load} isAdmin={!!account.is_admin}/>}{view==='settings'&&<GoalsPanel request={api} onChanged={load}/>}{view==='settings'&&<TeamPanel request={api}/>}{view==='settings'&&account.is_admin&&<Administration request={api}/>}</div><SettingsModal isOpen={settingsModal} onClose={()=>setSettingsModal(false)} onChanged={load} advanced={!!account.is_admin}/></div>
}
