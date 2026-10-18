import test from 'node:test'
import assert from 'node:assert/strict'
import {captureModes,captureMode,compareWords} from './voiceComparison.mjs'
import {microphoneConstraints} from './micDevices.mjs'

test('comparison modes isolate browser processing and RNNoise',()=>{
  assert.equal(captureModes.length,3)
  for(const mode of captureModes){
    const constraints=microphoneConstraints('mic',{noiseSuppression:mode.browser})
    assert.equal(constraints.noiseSuppression,mode.id==='browser')
    assert.equal(constraints.autoGainControl,false)
    assert.equal(constraints.echoCancellation,true)
    assert.equal(mode.rnnoise,mode.id==='rnnoise')
  }
  assert.equal(microphoneConstraints().noiseSuppression,true)
  assert.throws(()=>captureMode('invalid'))
})
test('word comparison ignores punctuation and case, counts recognition errors',()=>{
  assert.deepEqual(compareWords('Hello, Hikari!','hello hikari'),{errors:0,words:2,wer:0})
  assert.equal(compareWords('I like tea','I like coffee').errors,1)
  assert.equal(compareWords('I like tea','I tea').errors,1)
  assert.equal(compareWords('I like tea','I really like tea').errors,1)
  assert.equal(compareWords('Hello','').wer,100)
  assert.equal(compareWords('','hello'),null)
})
