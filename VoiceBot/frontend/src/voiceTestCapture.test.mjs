import test from 'node:test'
import assert from 'node:assert/strict'
import {record,release} from './voiceTestCapture.mjs'

class Recorder {
  static isTypeSupported(type){return type==='audio/webm;codecs=opus'}
  constructor(stream,options){this.stream=stream;this.mimeType=options.mimeType;this.state='inactive'}
  start(){this.state='recording'}
  stop(){this.ondataavailable({data:new Blob(['final audio'])});this.state='inactive';this.onstop()}
}
test('record waits for final data before exposing audio blob',async()=>{
  globalThis.MediaRecorder=Recorder
  const capture=record({})
  capture.recorder.start();capture.recorder.stop()
  const blob=await capture.done
  assert.equal(await blob.text(),'final audio')
  assert.equal(blob.type,'audio/webm;codecs=opus')
})
test('cleanup stops capture tracks, monitoring, recorder, denoiser, and context',async()=>{
  globalThis.MediaRecorder=Recorder
  const calls=[],capture=record({})
  capture.recorder.start()
  const run={recordings:[capture],stopMonitor:()=>calls.push('monitor'),clean:{destroy:()=>calls.push('denoise')},stream:{getTracks:()=>[{stop:()=>calls.push('track')}]},context:{close:async()=>calls.push('context')}}
  release(run)
  await capture.done
  assert.equal(capture.recorder.state,'inactive')
  assert.deepEqual(calls,['monitor','denoise','track','context'])
})
test('native recording errors reject instead of leaving recognition waiting',async()=>{
  globalThis.MediaRecorder=Recorder
  const capture=record({})
  capture.recorder.onerror({error:new Error('device removed')})
  await assert.rejects(capture.done,/device removed/)
})
