import { useEffect, useState } from 'react'

export const API = '/api'

export const api = async (path, options = {}) => {
  let response
  try{response = await fetch(`${API}${path}`, {credentials:'same-origin',...options})}
  catch{throw new Error('Hikari can\'t reach the server. Check that the app is still running and your connection is working, then try again.')}
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error=new Error(data.error?.message||data.detail||'Something went wrong')
    error.status=response.status
    throw error
  }
  return data
}

import { Icon } from './Icon'
export { Icon }

export function ScoreRing({ score, size = 116 }) {
  const r = 45, c = 2 * Math.PI * r
  return <div className="score-ring" style={{ width: size, height: size }}>
    <svg viewBox="0 0 110 110"><circle className="ring-base" cx="55" cy="55" r={r}/><circle className="ring-value" cx="55" cy="55" r={r} strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)}/></svg>
    <div><strong>{Math.round(score)}</strong><small>/100</small></div>
  </div>
}

export const prettyHours = minutes => minutes >= 60 ? `${(minutes/60).toFixed(1)} hours` : `${Math.round(minutes)} min`

// Numbers count up once. Text values, and people who prefer reduced motion, see the final value.

export function useCountUp(value,duration=800){
  const text=String(value),match=text.match(/^(\d+(?:\.\d+)?)(.*)$/)
  const target=match?Number(match[1]):0,[shown,setShown]=useState(target)
  useEffect(()=>{
    if(!match||!target||window.matchMedia?.('(prefers-reduced-motion: reduce)').matches){setShown(target);return}
    let frame,start
    const step=time=>{start??=time;const progress=Math.min((time-start)/duration,1);setShown(target*(1-(1-progress)**3));if(progress<1)frame=requestAnimationFrame(step)}
    frame=requestAnimationFrame(step)
    return()=>cancelAnimationFrame(frame)
  },[target,duration,!!match])
  if(!match)return text
  const decimals=match[1].includes('.')?match[1].split('.')[1].length:0
  return `${shown.toFixed(decimals)}${match[2]}`
}

export function StatCard({ icon, label, value, detail }) {
  const shown=useCountUp(value)
  return <article className="h-stat"><span><Icon name={icon}/></span><div><small>{label}</small><strong>{shown}</strong>{detail&&<em>{detail}</em>}</div></article>
}

export const fmt = (value, unit='ms') => value == null ? '—' : `${Math.round(value)}${unit}`

export function Sparkline({ values, max=100 }) {
  if (!values.length) return <div className="spark-empty">Collecting samples…</div>
  const points=values.map((v,i)=>`${i/(Math.max(values.length-1,1))*100},${38-Math.min(v/max,1)*34}`).join(' ')
  return <svg className="spark" viewBox="0 0 100 40" preserveAspectRatio="none"><polyline points={points}/></svg>
}

export function Loading(){return <div className="loading"><span>光</span><p>Preparing your training space…</p></div>}
