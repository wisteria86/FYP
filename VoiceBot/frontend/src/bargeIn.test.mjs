import test from 'node:test'
import assert from 'node:assert/strict'
import {startBargeIn} from './bargeIn.mjs'

test('interrupted recording retains its container header after extended playback',async()=>{
  const originals=Object.fromEntries(['navigator','AudioContext','MediaRecorder'].map(k=>[k,Object.getOwnPropertyDescriptor(globalThis,k)]))
  let callbacks,recorder,time=0,playing=true,heard,interrupted=0
  const track={getSettings:()=>({echoCancellation:true}),stop(){}}
  const stream={getAudioTracks:()=>[track],getTracks:()=>[track]}
  class Recorder{
    constructor(){recorder=this;this.mimeType='audio/webm';this.state='inactive'}
    start(){this.state='recording'}
    stop(){this.state='inactive';this.stopped=this.onstop()}
    chunk(text){this.ondataavailable({data:new Blob([text])})}
  }
  Object.defineProperty(globalThis,'navigator',{configurable:true,value:{mediaDevices:{getUserMedia:async()=>stream}}})
  Object.defineProperty(globalThis,'AudioContext',{configurable:true,value:class{async close(){}}})
  Object.defineProperty(globalThis,'MediaRecorder',{configurable:true,value:Recorder})
  let monitor
  try{
    monitor=await startBargeIn({constraints:{},isPlaying:()=>playing,now:()=>time,
      startVad:async(context,source,cb)=>{callbacks=cb;return {stop(){}}},
      onInterrupt:()=>{interrupted++;playing=false},onUtterance:async blob=>{heard=await blob.text()},onUnavailable:assert.fail})
    recorder.chunk('HEADER|')
    for(let i=0;i<15;i++){time+=100;recorder.chunk(`frame${i}|`)}
    callbacks.onProbability(.99);time+=400;callbacks.onProbability(.99)
    recorder.chunk('learner words');callbacks.onEnd();await recorder.stopped
    assert.equal(interrupted,1)
    assert.ok(heard.startsWith('HEADER|'))
    assert.ok(heard.endsWith('learner words'))
  }finally{
    monitor?.stop()
    for(const [key,descriptor] of Object.entries(originals)){if(descriptor)Object.defineProperty(globalThis,key,descriptor);else delete globalThis[key]}
  }
})
