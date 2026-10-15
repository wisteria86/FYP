import test from 'node:test'
import assert from 'node:assert/strict'
import { IncrementalTranscriber } from './incrementalTranscriber.mjs'

test('one request at a time, safe final snapshot reused',async()=>{
  let resolve,calls=0
  const capture=new IncrementalTranscriber(()=>{calls++;return new Promise(r=>resolve=r)})
  assert.equal(capture.push('prefix',1200),true)
  assert.equal(capture.push('new prefix',1400),false)
  resolve({text:'Hello neighbour.',needs_retry:false})
  assert.equal((await capture.finish(1000)).text,'Hello neighbour.')
  assert.equal(calls,1)
  assert.equal(capture.push('late',1500),false)
})
test('stale, uncertain and failed partials fall back to full recording',async()=>{
  for(const [result,coverage] of [[{text:'Hello'},900],[{text:'Hello',needs_retry:true},1400],[{text:''},1400]]){
    const capture=new IncrementalTranscriber(async()=>result)
    capture.push('prefix',coverage)
    assert.equal(await capture.finish(1000),null)
  }
  const failed=new IncrementalTranscriber(async()=>{throw new Error('bad partial WebM')})
  failed.push('prefix',1400)
  assert.equal(await failed.finish(1000),null)
})
test('cancelled capture cannot publish late provisional text',async()=>{
  let resolve,published=0
  const capture=new IncrementalTranscriber(()=>new Promise(r=>resolve=r),()=>published++)
  capture.push('prefix',1400);capture.cancel();resolve({text:'late'})
  assert.equal(await capture.finish(1000),null)
  assert.equal(published,0)
})
