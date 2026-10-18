import {loadRnnoise,RnnoiseWorkletNode} from '@sapphi-red/web-noise-suppressor'
import workletUrl from '@sapphi-red/web-noise-suppressor/rnnoiseWorklet.js?url'
import wasmUrl from '@sapphi-red/web-noise-suppressor/rnnoise.wasm?url'
import simdUrl from '@sapphi-red/web-noise-suppressor/rnnoise_simd.wasm?url'
import {connectCleanCapture} from './cleanCapture.mjs'

let binary
export async function createCleanCapture(context,stream){
  if(context.sampleRate!==48000)throw new Error('Noise reduction requires 48 kHz capture.')
  if(!context.audioWorklet)throw new Error('Noise reduction requires AudioWorklet support.')
  if(!binary)binary=loadRnnoise({url:wasmUrl,simdUrl}).catch(error=>{binary=null;throw error})
  const wasmBinary=await binary
  await context.audioWorklet.addModule(workletUrl)
  return connectCleanCapture(context,stream,()=>new RnnoiseWorkletNode(context,{wasmBinary,maxChannels:1}))
}
