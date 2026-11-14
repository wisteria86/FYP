import { useState } from 'react'
import { api } from '../ui/core'

export function AuthScreen({ onAuthenticated }) {
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
  return <main className="auth-page"><section className="auth-intro"><div className="auth-brand"><span aria-hidden="true">光</span> <strong>Hikari</strong></div><p>AI-powered workplace training</p><h1>Practise difficult conversations before they happen.</h1><span>Private progress, adaptive scenarios, and realistic voice roleplay in one training workspace.</span></section><section className="auth-panel"><div className="auth-card"><p className="eyebrow">{mode==='login'?'WELCOME BACK':'CREATE YOUR WORKSPACE'}</p><h2>{mode==='login'?'Sign in to Hikari':'Start training with Hikari'}</h2><p>Your progress and sessions stay connected to your account.</p><form onSubmit={submit}>{mode==='register'&&<><label>Full name<input name="name" value={form.name} onChange={update} autoComplete="name" required/></label><label>Organization<input name="organization_name" value={form.organization_name} onChange={update} autoComplete="organization" required/></label></>}<label>Email address<input name="email" type="email" value={form.email} onChange={update} autoComplete="email" required/></label><label>Password<input name="password" type="password" value={form.password} onChange={update} autoComplete={mode==='login'?'current-password':'new-password'} minLength={mode==='register'?10:1} required/></label>{mode==='register'&&<small>Use at least 10 characters with a letter and a number.</small>}{error&&<div className="auth-error">{error}</div>}<button className="h-primary" disabled={busy}>{busy?'Please wait…':mode==='login'?'Sign in':'Create account'}</button></form><button className="auth-switch" onClick={()=>{setMode(value=>value==='login'?'register':'login');setError('')}}>{mode==='login'?'New to Hikari? Create an account':'Already have an account? Sign in'}</button></div></section></main>
}
