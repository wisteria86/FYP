import test from 'node:test'
import assert from 'node:assert/strict'
import {frameLevels,accumulateLevels,levelSummary,emptyLevels,createInputLevel} from './inputLevel.mjs'

test('sampled near clipping and energy aggregate across frames',()=>{
 const total=emptyLevels()
 accumulateLevels(total,frameLevels(new Float32Array([0,1,-1,.5])))
 accumulateLevels(total,frameLevels(new Float32Array([0,0,0,0])))
 const result=levelSummary(total)
 assert.equal(result.peak,1)
 assert.equal(result.nearClippedPercent,25)
 assert.equal(result.rms,Math.sqrt(2.25/8))
 assert.deepEqual(levelSummary(emptyLevels()),{rms:0,peak:0,nearClippedPercent:0})
})
test('software gain precedes the mono output and releases its own resources',()=>{
 const edges=[],stopped=[]
 const source={connect:target=>edges.push(['input',target]),disconnect:()=>stopped.push('input')}
 const gain={gain:{value:1},connect:target=>edges.push(['gain',target]),disconnect:()=>stopped.push('gain')}
 const destination={stream:{getTracks:()=>[{stop:()=>stopped.push('output-track')}]}}
 const context={createMediaStreamSource:()=>source,createGain:()=>gain,createMediaStreamDestination:()=>destination}
 const capture=createInputLevel(context,{},-6)
 assert.ok(Math.abs(gain.gain.value-.501187)<.000001)
 assert.equal(destination.channelCount,1)
 assert.deepEqual(edges,[['input',gain],['gain',destination]])
 assert.equal(capture.stream,destination.stream)
 capture.destroy();capture.destroy()
 assert.deepEqual(stopped,['input','gain','output-track'])
 assert.throws(()=>createInputLevel(context,{},NaN))
 assert.throws(()=>createInputLevel(context,{},7))
})
