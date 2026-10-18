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
 assert.equal(loadSessionAudio(storage({'hikari-session-audio-v1':'invalid'})).mode,'rnnoise')
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
