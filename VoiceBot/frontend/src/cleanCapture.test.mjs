import test from 'node:test'
import assert from 'node:assert/strict'
import {connectCleanCapture} from './cleanCapture.mjs'

test('recording and recognition share cleaned audio without local playback',()=>{
  const edges=[],calls=[]
  const raw={connect:node=>edges.push(['raw',node]),disconnect:()=>calls.push('raw-disconnect')}
  const denoiser={connect:node=>edges.push(['denoiser',node]),disconnect:()=>calls.push('denoiser-disconnect'),destroy:()=>calls.push('destroy')}
  const original={getTracks:()=>[{stop:()=>calls.push('raw-stop')}]}
  const cleaned={getTracks:()=>[{stop:()=>calls.push('cleaned-stop')}]}
  const destination={stream:cleaned}
  const context={createMediaStreamSource:stream=>{assert.equal(stream,original);return raw},createMediaStreamDestination:()=>destination}
  const capture=connectCleanCapture(context,original,()=>denoiser)
  assert.equal(capture.source,denoiser)
  assert.equal(capture.stream,cleaned)
  assert.equal(destination.channelCount,1)
  assert.equal(destination.channelCountMode,'explicit')
  assert.deepEqual(edges,[['raw',denoiser],['denoiser',destination]])
  capture.destroy();capture.destroy()
  assert.deepEqual(calls,['raw-disconnect','denoiser-disconnect','destroy','cleaned-stop'])
})
