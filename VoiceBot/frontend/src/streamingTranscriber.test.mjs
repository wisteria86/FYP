import test from 'node:test'
import assert from 'node:assert/strict'
import {StreamingTranscriber} from './streamingTranscriber.mjs'

function setup(events=['ready']){
  globalThis.window={location:{href:'http://localhost:8000/'}}
  class Socket{
    static OPEN=1
    constructor(){this.readyState=1;this.bufferedAmount=0;this.sent=[];queueMicrotask(()=>this.onopen())}
    send(data){
      this.sent.push(data)
      if(typeof data==='string'){
        const command=JSON.parse(data)
        if(command.sample_rate)queueMicrotask(()=>events.forEach(type=>this.onmessage({data:JSON.stringify({type,text:'provisional',final:false})})))
        if(command.type==='finish')queueMicrotask(()=>this.onmessage({data:JSON.stringify({type:'final',text:'Final words.',final:true})}))
      }
    }
    close(){this.readyState=3;this.onclose?.()}
  }
  globalThis.WebSocket=Socket
  globalThis.AudioWorkletNode=class{
    constructor(){this.port={postMessage:()=>queueMicrotask(()=>this.port.onmessage({data:{flushed:true}}))}}
    connect(){}disconnect(){}
  }
  const context={sampleRate:48000,audioWorklet:{addModule:async()=>{}},createGain:()=>({gain:{value:1},connect(){},disconnect(){}})}
  return {context,source:{connect(){},disconnect(){}}}
}
test('streaming partials cannot substitute for a finalized transcript',async()=>{
  const {context,source}=setup(['ready','partial']);let partial
  const capture=new StreamingTranscriber('session',text=>partial=text)
  assert.equal(await capture.start(context,source),true)
  assert.equal(partial,'provisional')
  const result=await capture.finish()
  assert.equal(result.text,'Final words.');assert.equal(result.final,true)
  assert.equal(capture.closed,true)
})
test('cancelled streams cannot publish late partials',async()=>{
  const {context,source}=setup();let calls=0
  const capture=new StreamingTranscriber('session',()=>calls++)
  await capture.start(context,source);capture.cancel()
  capture.socket.onmessage({data:JSON.stringify({type:'partial',text:'late'})})
  assert.equal(calls,0);assert.equal(await capture.finish(),null)
})
test('connection failure permits recorded-audio fallback',async()=>{
  const {context,source}=setup(['error'])
  // An error during setup must resolve the readiness wait as well.
  const capture=new StreamingTranscriber('session')
  const started=capture.start(context,source)
  queueMicrotask(()=>capture.socket.close())
  assert.equal(await started,false)
})
test('hangup during PCM flush returns safely without sending a final request',async()=>{
  const {context,source}=setup()
  const capture=new StreamingTranscriber('session')
  await capture.start(context,source)
  const finishing=capture.finish();capture.cancel()
  assert.equal(await finishing,null)
  assert.equal(capture.socket.sent.some(item=>typeof item==='string'&&JSON.parse(item).type==='finish'),false)
})
