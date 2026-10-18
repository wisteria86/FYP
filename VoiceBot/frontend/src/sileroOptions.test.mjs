import test from 'node:test'
import assert from 'node:assert/strict'
import {sileroOptions} from './sileroOptions.mjs'

test('Silero uses the processed capture and never changes shared stream ownership',async()=>{
  const stream={getTracks(){throw new Error('VAD must not stop shared tracks')}}
  const context={},events=[]
  const options=sileroOptions(context,stream,{onProbability:p=>events.push(p),onSpeech:()=>events.push('speech'),onEnd:()=>events.push('end')})
  assert.equal(options.audioContext,context)
  assert.equal(await options.getStream(),stream)
  assert.equal(await options.resumeStream(),stream)
  await options.pauseStream(stream)
  assert.equal(options.redemptionMs,1500)
  assert.equal(options.preSpeechPadMs,400)
  assert.equal(options.minSpeechMs,200)
  assert.equal(options.positiveSpeechThreshold,.35)
  assert.equal(options.negativeSpeechThreshold,.15)
  assert.equal(options.submitUserSpeechOnPause,false)
  assert.equal(options.startOnLoad,false)
  assert.equal(options.model,'v5')
  options.onFrameProcessed({isSpeech:.9});options.onSpeechRealStart();options.onSpeechEnd()
  assert.deepEqual(events,[.9,'speech','end'])
  const ort={env:{wasm:{}}};options.ortConfig(ort)
  assert.equal(ort.env.wasm.numThreads,1)
})
