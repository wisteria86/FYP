import {test} from 'node:test'
import assert from 'node:assert/strict'
import {StreamingTranscriber} from './streamingTranscriber.mjs'

test('finish flushes PCM and disconnects before cleanup, without awaiting cleanup',async()=>{
  globalThis.WebSocket={OPEN:1}
  const events=[]
  const capture=new StreamingTranscriber('session')
  capture.ready=true
  capture.contextSampleRate=48000
  capture.sentSamples=9600
  capture.processedSamples=4800
  capture.source={disconnect:()=>events.push('source-disconnect')}
  capture.gain={disconnect:()=>{}}
  capture.node={disconnect:()=>events.push('node-disconnect'),port:{postMessage:()=>{
    events.push('flush')
    queueMicrotask(()=>capture.flushed())
  }}}
  capture.socket={readyState:1,send:()=>{
    events.push('finish-command')
    queueMicrotask(()=>capture.complete({text:'hello',latency_ms:42}))
  },close:()=>{}}
  const result=await capture.finish(()=>{
    events.push('cleanup')
    return new Promise(()=>{}) // Slow context closure must not block final text.
  })
  assert.equal(result.text,'hello')
  assert.ok(events.indexOf('flush')<events.indexOf('cleanup'))
  assert.ok(events.indexOf('node-disconnect')<events.indexOf('cleanup'))
  assert.ok(events.indexOf('cleanup')<events.indexOf('finish-command'))
  assert.equal(capture.timing.backend_finalize_ms,42)
  assert.equal(capture.timing.unacknowledged_audio_ms,100)
  assert.equal(capture.closed,true)
})

test('unavailable stream leaves capture cleanup to caller',async()=>{
  const capture=new StreamingTranscriber('session')
  let cleaned=false
  assert.equal(await capture.finish(()=>{cleaned=true}),null)
  assert.equal(cleaned,false)
})
