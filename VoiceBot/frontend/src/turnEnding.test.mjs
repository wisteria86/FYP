import test from 'node:test'
import assert from 'node:assert/strict'
import {captureLimitReason,turnDetection} from './turnEnding.mjs'

test('lesson-length answers do not stop a speaking learner',()=>{
 for(const duration of [12000,18000,30000,79999])assert.equal(captureLimitReason(duration,true,true),null)
})
test('manual turn ending does not rotate quiet capture before the safety limit',()=>{
 assert.equal(captureLimitReason(30000,false,false),null)
 assert.equal(captureLimitReason(80000,false,false),'capture_limit')
})
test('automatic idle rotation waits longer and respects the transport bound',()=>{
 assert.equal(captureLimitReason(8000,false,true),null)
 assert.equal(captureLimitReason(20000,false,true),'no_speech')
 assert.equal(captureLimitReason(80000,true,true),'capture_limit')
 assert.equal(turnDetection.silenceMs,1500)
})
