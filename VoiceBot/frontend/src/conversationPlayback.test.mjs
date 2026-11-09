import test from 'node:test'
import assert from 'node:assert/strict'
import {PlaybackGeneration,SpeechInterruptionGate} from './conversationPlayback.mjs'
test('interruption invalidates queued audio and acknowledgements',async()=>{
  const player=new PlaybackGeneration(),generation=player.capture();let acknowledged=false
  player.after(5,()=>{acknowledged=true});player.cancel()
  await new Promise(resolve=>setTimeout(resolve,15))
  assert.equal(player.current(generation),false);assert.equal(acknowledged,false)
})
test('automatic interruption needs sustained speech and echo cancellation',()=>{
  const gate=new SpeechInterruptionGate()
  assert.equal(gate.update(.99,0,true,false),false)
  assert.equal(gate.update(.99,100,true,true),false)
  assert.equal(gate.update(.99,300,true,true),false)
  assert.equal(gate.update(.99,500,true,true),true)
  assert.equal(gate.update(.99,600,true,true),false)
  assert.equal(gate.update(.2,700,true,true),false)
  assert.equal(gate.update(.99,1200,false,true),false)
})
