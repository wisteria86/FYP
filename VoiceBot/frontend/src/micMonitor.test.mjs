import test from 'node:test'
import assert from 'node:assert/strict'
import {monitorMicrophone} from './micMonitor.mjs'

function setup() {
  const connections=[], disconnected=[]
  const node=name=>({connect:other=>connections.push([name,other.name]),disconnect:()=>disconnected.push(name),name})
  const source=node('microphone'), silent={...node('silent'),gain:{value:1}}
  const analyser={...node('analyser'),getFloatTimeDomainData:array=>array.fill(.02)}
  const context={state:'running',destination:{name:'output'},createAnalyser:()=>analyser,createGain:()=>silent}
  return {context,source,silent,connections,disconnected}
}

test('microphone graph is rendered without echo even when animation frames never run',async()=>{
  const {context,source,silent,connections}=setup()
  globalThis.requestAnimationFrame=()=>{throw new Error('Must not depend on rendering')}
  const levels=[]
  const stop=monitorMicrophone(context,source,rms=>levels.push(rms))
  try {
    await new Promise(resolve=>setTimeout(resolve,180))
    assert.ok(levels.length>=1)
    assert.ok(Math.abs(levels[0]-.02)<.00001)
    assert.equal(silent.gain.value,0)
    assert.deepEqual(connections,[['microphone','analyser'],['analyser','silent'],['silent','output']])
  } finally {stop();delete globalThis.requestAnimationFrame}
})

test('stop releases graph and prevents late microphone updates',async()=>{
  const {context,source,disconnected}=setup()
  let calls=0
  const stop=monitorMicrophone(context,source,()=>calls++)
  stop();stop()
  await new Promise(resolve=>setTimeout(resolve,90))
  assert.equal(calls,0)
  assert.deepEqual(disconnected,['microphone','analyser','silent'])
})

test('suspended capture resumes and a failure is surfaced',async()=>{
  const {context,source}=setup()
  context.state='suspended'
  context.resume=async()=>{throw new Error('Audio permission lost')}
  const errors=[]
  const stop=monitorMicrophone(context,source,()=>{},error=>errors.push(error.message))
  try {
    await new Promise(resolve=>setTimeout(resolve,90))
    assert.deepEqual(errors,['Audio permission lost'])
  } finally {stop()}
})
