import test from 'node:test'
import assert from 'node:assert/strict'
import {CaptureClock} from './captureClock.mjs'

test('paused audio is excluded from submitted duration',()=>{
 const clock=new CaptureClock(1000)
 clock.pause(3000)
 assert.equal(clock.elapsed(20000),2000)
 clock.resume(23000)
 assert.equal(clock.elapsed(25000),4000)
 clock.pause(26000)
 assert.equal(clock.elapsed(50000),5000)
})
test('repeated pause and resume cannot double count time',()=>{
 const clock=new CaptureClock(100)
 clock.pause(200);clock.pause(300)
 clock.resume(400);clock.resume(500)
 assert.equal(clock.elapsed(600),300)
})
test('review while paused retains only captured audio time',()=>{
 const clock=new CaptureClock(0)
 clock.pause(1500)
 assert.equal(clock.elapsed(80000),1500)
})
