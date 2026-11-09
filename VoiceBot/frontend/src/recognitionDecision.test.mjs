import test from 'node:test'
import assert from 'node:assert/strict'
import {finalRecognitionForm,recognitionProvenance,reviewedRecognition} from './recognitionDecision.mjs'
import {normalizeSessionAudio} from './sessionAudio.mjs'

test('accuracy mode never sends an unchecked live transcript as final',()=>{
 const form=new FormData(),live={text:'ten seeds'}
 assert.equal(finalRecognitionForm(form,normalizeSessionAudio({accurateFinal:true}),'session',live),null)
 assert.equal(form.get('final_pass'),'true')
 assert.equal(form.get('session_id'),'session')
 assert.equal(form.get('original_text'),'ten seeds')
})
test('fast mode can reuse live text; incomplete recognition still needs the recording',()=>{
 const form=new FormData(),live={text:'ten seats'}
 assert.equal(finalRecognitionForm(form,{accurateFinal:false},'session',live),live)
 assert.equal(form.has('final_pass'),false)
 assert.equal(finalRecognitionForm(new FormData(),{accurateFinal:false},'session',{}),null)
})
test('default voice turns reuse completed live recognition without another decode',()=>{
 const form=new FormData(),live={text:'Sam, explain the plan.',needs_retry:false}
 assert.equal(finalRecognitionForm(form,normalizeSessionAudio(),'session',live),live)
 assert.equal(form.has('final_pass'),false)
})
test('fast mode preserves uncertainty instead of bypassing transcript review',()=>{
 const live={text:'uncertain words',needs_retry:true}
 const result=finalRecognitionForm(new FormData(),normalizeSessionAudio(),'session',live)
 assert.equal(result.needs_retry,true)
})
test('recognition provenance preserves disagreement and original words',()=>{
 const provenance=recognitionProvenance({text:'no',original_text:'yes',final_pass:'whisper',needs_retry:true,disagreement:1})
 assert.equal(provenance.original_text,'yes');assert.equal(provenance.unreliable,true)
 assert.equal(provenance.final_pass,'whisper')
})
test('explicit learner review retains both acoustic hypotheses',()=>{
 const checked=reviewedRecognition({text:'ten seats',original_text:'ten seeds',needs_retry:true,final_pass:'whisper'})
 assert.equal(checked.unreliable,false);assert.equal(checked.confirmed_by_learner,true)
 assert.equal(checked.original_text,'ten seeds');assert.equal(checked.unreviewed_text,'ten seats')
})
