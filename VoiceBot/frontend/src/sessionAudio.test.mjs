import test from 'node:test'
import assert from 'node:assert/strict'
import {loadSessionAudio,saveSessionAudio,sessionAudioMode,normalizeSessionAudio} from './sessionAudio.mjs'
function storage(values={}){return {getItem:key=>values[key]??null,setItem:(key,value)=>{values[key]=value}}}
test('saved test choices become session processing preferences',()=>{
 const local=storage()
 saveSessionAudio(local,{mode:'rnnoise',deviceId:'headset',gainEnabled:true,gainDb:-12,liveRecognition:true})
 const value=loadSessionAudio(local)
 assert.equal(value.deviceId,'headset');assert.equal(value.gainDb,-12)
 assert.equal(sessionAudioMode(value).browser,false);assert.equal(sessionAudioMode(value).rnnoise,true)
 assert.equal(value.liveRecognition,true)
})
test('legacy capture preferences migrate without losing device or processing',()=>{
 const value=loadSessionAudio(storage({'hikari-mic-id':'microphone','hikari-noise-reduction':'true'}))
 assert.equal(value.mode,'combined');assert.equal(value.deviceId,'microphone')
 assert.equal(loadSessionAudio(storage({'hikari-noise-reduction':'false'})).mode,'browser')
})
test('corrupt preferences fall back and out-of-range gain is bounded',()=>{
 assert.equal(loadSessionAudio(storage({'hikari-session-audio-v1':'invalid'})).mode,'browser')
 assert.equal(normalizeSessionAudio({mode:'unknown'}).mode,'browser')
 assert.equal(sessionAudioMode({mode:'unknown'}).id,'browser')
 assert.equal(normalizeSessionAudio({gainDb:99}).gainDb,6)
 assert.equal(normalizeSessionAudio({gainDb:-99}).gainDb,-24)
})

test('session input defaults to manual and preserves an explicit automatic choice',()=>{
 const local=storage()
 assert.equal(loadSessionAudio(local).inputMode,'manual')
 saveSessionAudio(local,{inputMode:'auto'})
 assert.equal(loadSessionAudio(local).inputMode,'auto')
 saveSessionAudio(local,{...loadSessionAudio(local),inputMode:'manual'})
 assert.equal(loadSessionAudio(local).inputMode,'manual')
 assert.equal(normalizeSessionAudio({inputMode:'invalid'}).inputMode,'manual')
})

test('decoder preference defaults safely and survives saving',()=>{
 const local=storage()
 assert.equal(loadSessionAudio(local).decodingMethod,'greedy_search')
 saveSessionAudio(local,{decodingMethod:'modified_beam_search'})
 assert.equal(loadSessionAudio(local).decodingMethod,'modified_beam_search')
 assert.equal(normalizeSessionAudio({decodingMethod:'bad'}).decodingMethod,'greedy_search')
})

test('fresh installations avoid stacked suppression and malformed preferences are safe',()=>{
 assert.equal(loadSessionAudio(storage()).mode,'browser')
 for(const value of [null,[],42,'invalid'])assert.equal(normalizeSessionAudio(value).decodingMethod,'greedy_search')
})

test('old always-on final decoding migrates to fast recognition without changing microphone settings',()=>{
 const local=storage({'hikari-session-audio-v1':JSON.stringify({accurateFinal:true,deviceId:'headset',mode:'rnnoise',gainDb:-9,inputMode:'auto'})})
 const value=loadSessionAudio(local)
 assert.equal(value.accurateFinal,false)
 assert.equal(value.deviceId,'headset');assert.equal(value.mode,'browser')
 assert.equal(value.gainDb,-9);assert.equal(value.inputMode,'auto')
 assert.equal(value.recognitionPolicyVersion,3)
 saveSessionAudio(local,value)
 assert.equal(loadSessionAudio(local).accurateFinal,false)
})

test('a new explicit accuracy choice survives saving and reloading',()=>{
 const local=storage()
 assert.equal(loadSessionAudio(local).accurateFinal,false)
 saveSessionAudio(local,{...loadSessionAudio(local),accurateFinal:true})
 assert.equal(loadSessionAudio(local).accurateFinal,true)
 saveSessionAudio(local,{...loadSessionAudio(local),accurateFinal:false})
 assert.equal(loadSessionAudio(local).accurateFinal,false)
})

test('saved RNNoise modes move to browser suppression once and later choices persist',()=>{
 for(const mode of ['rnnoise','combined']){
  const local=storage({'hikari-session-audio-v1':JSON.stringify({recognitionPolicyVersion:2,accurateFinal:true,mode,deviceId:'headset',gainEnabled:true,gainDb:-12})})
  const value=loadSessionAudio(local)
  assert.equal(value.mode,'browser');assert.equal(value.accurateFinal,true)
  assert.equal(value.deviceId,'headset');assert.equal(value.gainEnabled,true);assert.equal(value.gainDb,-12)
  saveSessionAudio(local,{...value,mode})
  assert.equal(loadSessionAudio(local).mode,mode)
 }
 const none=storage({'hikari-session-audio-v1':JSON.stringify({recognitionPolicyVersion:2,mode:'none'})})
 assert.equal(loadSessionAudio(none).mode,'none')
})
