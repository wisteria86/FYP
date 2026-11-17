import test from 'node:test'
import assert from 'node:assert/strict'
import { createLife, GAZE_LIMIT } from './call/portraitLife.mjs'

// Runs a life for `ms` milliseconds at 60 frames a second, with inputs that may change over time.
function run(life, ms, inputs, start = 0) {
  const poses = []
  for (let now = start; now < start + ms; now += 16) poses.push({ now, ...life.step(now, typeof inputs === 'function' ? inputs(now) : inputs) })
  return poses
}

test('the same character moves the same way every time', () => {
  assert.deepEqual(run(createLife(42), 3000, { state: 'idle' }), run(createLife(42), 3000, { state: 'idle' }))
  assert.notDeepEqual(run(createLife(42), 3000, { state: 'idle' }), run(createLife(7), 3000, { state: 'idle' }))
})

test('the eyes keep moving and blink every few seconds, sometimes twice', () => {
  const poses = run(createLife(3), 30000, { state: 'idle' })
  const blinks = poses.filter((pose, i) => pose.blink > 0.9 && !(poses[i - 1]?.blink > 0.9)).length
  assert.ok(blinks >= 5 && blinks <= 20, `blinks: ${blinks}`)
  const places = new Set(poses.map(pose => `${Math.round(pose.gazeX)},${Math.round(pose.gazeY)}`))
  assert.ok(places.size >= 4, 'looks at several places')
  for (const pose of poses) {
    assert.ok(Math.abs(pose.gazeX) <= GAZE_LIMIT + 1e-9 && Math.abs(pose.gazeY) <= GAZE_LIMIT + 1e-9)
    assert.ok(pose.blink >= 0 && pose.blink <= 1)
  }
})

test('thinking looks up and aside', () => {
  const poses = run(createLife(5), 4000, { state: 'thinking' }).slice(20)
  const up = poses.filter(pose => pose.gazeY < -1).length / poses.length
  assert.ok(up > 0.8, `share looking up: ${up}`)
})

test('listening looks at the speaker it is told to watch', () => {
  const poses = run(createLife(9), 6000, { state: 'listening', look: { x: 1, y: 0 } }).slice(20)
  const average = poses.reduce((sum, pose) => sum + pose.gazeX, 0) / poses.length
  assert.ok(average > 1.4, `average gaze: ${average}`)
})

test('a listener nods when the learner pauses after speaking', () => {
  let nodded = 0
  for (let seed = 1; seed <= 10; seed++) {
    // The learner speaks for 1.5 seconds, then stops.
    const poses = run(createLife(seed), 2600, now => ({ state: 'listening', heard: now < 1500 ? 0.4 : 0 }))
    if (poses.some(pose => pose.now > 1500 && pose.nod > 2)) nodded++
  }
  assert.ok(nodded >= 5, `nodded in ${nodded} of 10`)
  const still = run(createLife(1), 2600, { state: 'listening', heard: 0 })
  assert.ok(still.every(pose => pose.nod === 0), 'no nod without anything to nod at')
})

test('the mouth follows the voice, and makes its own syllables only without a voice signal', () => {
  const loud = run(createLife(2), 600, { state: 'speaking', voice: 0.8, driven: true }).at(-1)
  const quiet = run(createLife(2), 600, { state: 'speaking', voice: 0, driven: true })
  assert.ok(loud.mouthOpen > 0.7)
  assert.ok(quiet.every(pose => pose.mouthOpen < 0.05), 'a real silence keeps the mouth closed')
  const fallback = run(createLife(2), 2000, { state: 'speaking', voice: 0 }).slice(40)
  assert.ok(Math.max(...fallback.map(pose => pose.mouthOpen)) > 0.4, 'talks without a voice signal')
  const idle = run(createLife(2), 600, { state: 'idle' }).at(-1)
  assert.ok(idle.mouthOpen < 0.05)
})

test('a new reaction is noticed with a blink and a brow flick', () => {
  const life = createLife(11)
  run(life, 1000, { state: 'idle', reaction: 'neutral' })
  const after = run(life, 500, { state: 'idle', reaction: 'pleased' }, 1000)
  assert.ok(after.some(pose => pose.brow > 1.5))
  assert.ok(after.some(pose => pose.blink > 0.9))
})
