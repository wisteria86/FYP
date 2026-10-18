import test from 'node:test'
import assert from 'node:assert/strict'
import {listMicrophones,microphoneConstraints} from './micDevices.mjs'

test('permission requested before listing and temporary stream always stopped',async()=>{
  const calls=[]
  const media={getUserMedia:async()=>{calls.push('permission');return {getTracks:()=>[{stop:()=>calls.push('stop')}] }},enumerateDevices:async()=>{calls.push('list');return [{kind:'audioinput',deviceId:'mic',label:'Headset'},{kind:'audioinput',deviceId:'mic'},{kind:'audioinput',deviceId:''},{kind:'videoinput',deviceId:'camera'}]}}
  const devices=await listMicrophones(media,true)
  assert.equal(devices.length,1)
  assert.deepEqual(calls,['permission','list','stop'])
})
test('passive refresh never prompts for permission',async()=>{
  const devices=await listMicrophones({enumerateDevices:async()=>[]})
  assert.deepEqual(devices,[])
})
test('device enumeration error releases temporary capture',async()=>{
  let stopped=false
  await assert.rejects(listMicrophones({getUserMedia:async()=>({getTracks:()=>[{stop:()=>{stopped=true}}]}),enumerateDevices:async()=>{throw new Error('device unavailable')}},true),/device unavailable/)
  assert.equal(stopped,true)
})
test('permission denial is surfaced',async()=>{
  await assert.rejects(listMicrophones({enumerateDevices:async()=>[],getUserMedia:async()=>{throw new Error('permission denied')}},true),/permission denied/)
})

test('capture requests noise suppression without gain boosting on all devices',()=>{
  const defaults=microphoneConstraints()
  assert.equal(defaults.autoGainControl,false)
  assert.equal(defaults.noiseSuppression,true)
  assert.equal(defaults.echoCancellation,true)
  assert.deepEqual(defaults.channelCount,{ideal:1})
  assert.equal('deviceId' in defaults,false)
  assert.deepEqual(microphoneConstraints('headset').deviceId,{exact:'headset'})
})
