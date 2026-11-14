import { useState } from 'react'
import { microphoneConstraints } from '../micDevices.mjs'
import { Settings } from '../pages/Settings'
import { api } from '../ui/core'

export function SettingsHub({ dashboard, health, setView, onChanged, isAdmin=false }) {
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
      <article className="h-card"><h2>Audio & Microphone</h2><p>{mic}</p><button className="h-soft" onClick={testMic}>Test Microphone</button><small>Voice engine: {health.engine||'loading'} · Recognition: {health.stt_runtime?.model||'loading'}</small>{isAdmin&&<button className="h-soft" onClick={()=>setView('monitor')}>Open testing monitor</button>}</article>
      <article className="h-card"><h2>Camera & Permissions</h2><p>{camera}</p><button className="h-soft" onClick={testCamera}>Test Camera</button><small>Camera analysis is optional and limited to posture indicators.</small></article>
    </section>
    <Settings onChanged={onChanged} embedded advanced={isAdmin}/>
  </main>
}
