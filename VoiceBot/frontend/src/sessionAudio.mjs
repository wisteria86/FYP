import {captureModes} from './voiceComparison.mjs'
export const sessionAudioModes=[...captureModes,{id:'combined',name:'Browser + RNNoise',browser:true,rnnoise:true}]
export const sessionAudioKey='hikari-session-audio-v1'
export function normalizeSessionAudio(value={}){
  if(!value||typeof value!=='object'||Array.isArray(value))value={}
  return {decodingMethod:value.decodingMethod==='modified_beam_search'?'modified_beam_search':'greedy_search',inputMode:value.inputMode==='auto'?'auto':'manual',deviceId:typeof value.deviceId==='string'?value.deviceId:'',
    mode:sessionAudioModes.some(mode=>mode.id===value.mode)?value.mode:'rnnoise',
    gainEnabled:value.gainEnabled===true,
    gainDb:Number.isFinite(value.gainDb)?Math.max(-24,Math.min(6,value.gainDb)):-6,
    liveRecognition:value.liveRecognition!==false}
}
export function loadSessionAudio(storage){
  try{
    const saved=storage.getItem(sessionAudioKey)
    if(saved)return normalizeSessionAudio(JSON.parse(saved)||{})
    return normalizeSessionAudio({deviceId:storage.getItem('hikari-mic-id')||'',mode:storage.getItem('hikari-noise-reduction')==='true'?'combined':'browser'})
  }catch{return normalizeSessionAudio()}
}
export function saveSessionAudio(storage,value){
  const preferences=normalizeSessionAudio(value)
  storage.setItem(sessionAudioKey,JSON.stringify(preferences))
  if(typeof window!=='undefined')window.dispatchEvent(new Event('hikari-session-audio-changed'))
  return preferences
}
export function sessionAudioMode(value){return sessionAudioModes.find(mode=>mode.id===value.mode)||sessionAudioModes[1]}
