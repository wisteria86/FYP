import test from 'node:test'
import assert from 'node:assert/strict'
import {SpeechGate} from './speechGate.mjs'

test('brief clicks do not count as speech',()=>{
  const gate=new SpeechGate()
  assert.equal(gate.update(.2,0).speech,false)
  assert.equal(gate.update(.0001,50).speech,false)
})
test('quiet sustained voice is detected without initial calibration delay',()=>{
  const gate=new SpeechGate()
  gate.update(.002,0)
  assert.equal(gate.update(.002,100).speech,true)
})
test('trailing hum below speech level does not keep extending the turn',()=>{
  const gate=new SpeechGate()
  for(let t=0;t<=1000;t+=50)gate.update(.1,t)
  for(let t=1050;t<=1600;t+=50)assert.equal(gate.update(.008,t).speech,false)
})
test('threshold remains finite and positive for silence',()=>{
  const gate=new SpeechGate()
  for(let t=0;t<8000;t+=50){const d=gate.update(0,t);assert.equal(d.speech,false);assert.ok(d.threshold>=.0006)}
})

test('a single click does not hide the following quiet voice',()=>{
  const gate=new SpeechGate()
  gate.update(1,0);gate.update(0,50)
  gate.update(.002,100)
  assert.equal(gate.update(.002,200).speech,true)
})
