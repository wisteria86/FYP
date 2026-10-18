import {sileroOptions} from './sileroOptions.mjs'

export async function startSilero(context,stream,callbacks){
  const {MicVAD}=await import('@ricky0123/vad-web')
  const vad=await MicVAD.new(sileroOptions(context,stream,callbacks))
  try{await vad.start()}catch(error){await vad.destroy().catch(()=>{});throw error}
  let stopped=false
  console.info('[Hikari VAD]',{engine:'Silero v5',silence_ms:1500,min_speech_ms:200})
  return {get error(){return vad.errored},stop(){
    if(stopped)return
    stopped=true
    return vad.destroy().catch(error=>console.warn('[Hikari VAD cleanup]',error))
  }}
}
