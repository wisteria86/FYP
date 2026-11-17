// What makes a portrait feel alive: where it looks, when it blinks, how its head drifts, when it nods,
// and how its brows and mouth move with speech. Pure and seeded, so it can be tested in Node.
// The portrait reads a pose from step() every frame and writes it to CSS variables.

// Loudness shared by the call: `voice` is the character's own voice, `heard` is the learner's microphone.
// `driven` is true while a real voice signal is available, so silences in it stay silent.
export const levels = { voice: 0, heard: 0, driven: false }

function generator(seed) {
  let state = seed >>> 0
  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let t = state
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const clamp = (value, low, high) => Math.min(high, Math.max(low, value))
// Moves `from` toward `to`, covering about 63% of the gap every `tau` milliseconds.
const approach = (from, to, dt, tau) => from + (to - from) * (1 - Math.exp(-dt / tau))

export const GAZE_LIMIT = 3.2

export function createLife(seed = 1) {
  const random = generator(seed)
  const between = (low, high) => low + random() * (high - low)
  // Each character drifts at their own pace.
  const phase = [0, 1, 2, 3].map(() => random() * Math.PI * 2)
  const pace = [0, 1, 2, 3].map(() => between(0.7, 1.3))

  let last = null
  let gaze = { x: 0, y: 0 }, target = { x: 0, y: 0 }, nextFixation = 0
  let blinkAt = between(800, 3000), blinkStart = -1, doubleBlink = false
  let nodStart = -1, lastNod = -1e9, heardFor = 0, quietFor = 0
  let browStart = -1, lastBrow = -1e9
  let open = 0, slowVoice = 0, silentFor = 0
  let lastState = null, lastReaction = null

  const blink = now => { if (blinkStart < 0 || now - blinkStart > 180) { blinkStart = now; doubleBlink = random() < 0.15 } }
  const lift = now => { if (now - lastBrow > 900) { browStart = now; lastBrow = now } }

  // Picks the next place to look. `attention` is where whoever matters is: {0,0} is the learner (the camera).
  function fixate(now, state, attention) {
    const a = { x: attention.x * 2.6, y: attention.y * 2 }
    let next, hold
    if (state === 'thinking') {
      // People look up and aside while they work out what to say.
      const side = random() < 0.5 ? -1 : 1
      next = { x: side * between(1.6, 2.8), y: between(-2.6, -1.6) }; hold = between(700, 1600)
    } else if (state === 'listening') {
      // Stay on the speaker, with small movements between their eyes and mouth.
      next = { x: a.x + between(-0.5, 0.5), y: a.y + between(-0.3, 0.6) }; hold = between(900, 2600)
      if (random() < 0.1) { next = { x: between(-2, 2), y: between(-1, 1) }; hold = between(300, 600) }
    } else if (state === 'speaking') {
      // Mostly hold the listener's eye, glancing away now and then to think.
      next = random() < 0.25 ? { x: between(-2.4, 2.4), y: between(-1.8, 0.4) } : { x: a.x + between(-0.4, 0.4), y: a.y + between(-0.3, 0.3) }
      hold = between(600, 2200)
    } else {
      // Idle: look around the room, coming back to the learner.
      next = random() < 0.45 ? { x: a.x + between(-0.5, 0.5), y: a.y + between(-0.4, 0.4) } : { x: between(-2.8, 2.8), y: between(-1.6, 1.2) }
      hold = between(800, 3200)
    }
    next.x = clamp(next.x, -GAZE_LIMIT, GAZE_LIMIT); next.y = clamp(next.y, -GAZE_LIMIT, GAZE_LIMIT)
    // A large eye movement often comes with a blink.
    if (Math.hypot(next.x - gaze.x, next.y - gaze.y) > 2.2 && random() < 0.4) blink(now)
    target = next; nextFixation = now + hold
  }

  function step(now, input = {}) {
    const state = input.state || 'idle', attention = input.look || { x: 0, y: 0 }
    const voice = clamp(input.voice || 0, 0, 1), heard = clamp(input.heard || 0, 0, 1)
    const dt = last === null ? 16 : clamp(now - last, 0, 100)
    last = now

    // A change of state or reaction is noticed: a fresh look, and for a reaction, a blink and a brow flick.
    if (state !== lastState) { fixate(now, state, attention); lastState = state }
    if (input.reaction !== lastReaction) { if (lastReaction !== null) { blink(now); lift(now) } lastReaction = input.reaction }
    if (now >= nextFixation) fixate(now, state, attention)
    // Saccades are fast; the eyes settle on a new point within about a tenth of a second.
    gaze = { x: approach(gaze.x, target.x, dt, 35), y: approach(gaze.y, target.y, dt, 35) }

    // Blinks every two to six seconds, sometimes twice in a row.
    if (now >= blinkAt) { blink(now); blinkAt = now + between(2000, 6000) }
    let closed = 0
    if (blinkStart >= 0) {
      const t = now - blinkStart, one = x => (x < 0 || x > 170 ? 0 : x < 60 ? x / 60 : 1 - (x - 60) / 110)
      closed = Math.max(one(t), doubleBlink ? one(t - 220) : 0)
      if (t > (doubleBlink ? 400 : 180)) blinkStart = -1
    }

    // Listening: nod when the learner pauses after speaking for a while, and sometimes while they speak.
    if (state === 'listening') {
      if (heard > 0.12) { heardFor += dt; quietFor = 0; if (heard > 0.55) lift(now) } else quietFor += dt
      const pause = heardFor > 700 && quietFor > 250
      const along = heardFor > 2500 && random() < dt / 4000
      if ((pause || along) && now - lastNod > 2200 && nodStart < 0) {
        if (pause ? random() < 0.75 : true) { nodStart = now; lastNod = now }
        if (pause) heardFor = 0
      }
      if (quietFor > 1500) heardFor = 0
    } else { heardFor = 0; quietFor = 0 }
    let nod = 0
    if (nodStart >= 0) {
      const t = (now - nodStart) / 650
      nod = t >= 1 ? 0 : Math.sin(t * Math.PI) * 3.2 * (1 - t * 0.3)
      if (t >= 1) nodStart = -1
    }

    // Speaking: the mouth follows the voice. Without a voice signal it makes its own syllables.
    let mouthOpen = 0, mouthWide = 0.5
    if (state === 'speaking') {
      silentFor = voice > 0.03 ? 0 : silentFor + dt
      const drive = !input.driven && silentFor > 450 ? Math.max(0, Math.sin(now / 95 + Math.sin(now / 310) * 2)) * 0.7 + 0.1 : voice
      open = approach(open, drive, dt, drive > open ? 25 : 60)
      slowVoice = approach(slowVoice, drive, dt, 500)
      mouthOpen = clamp(open * 1.15, 0, 1)
      mouthWide = clamp(0.5 + (drive - slowVoice) * 1.6, 0, 1)
      // Stressed words lift the brows.
      if (drive - slowVoice > 0.22) lift(now)
    } else { open = approach(open, 0, dt, 60); slowVoice = 0; silentFor = 0; mouthOpen = clamp(open, 0, 1) }

    let brow = 0
    if (browStart >= 0) {
      const t = (now - browStart) / 420
      brow = t >= 1 ? 0 : Math.sin(t * Math.PI) * 2.4
      if (t >= 1) browStart = -1
    }

    // The head drifts slowly, turns a little toward what it is looking at, and bobs with speech.
    const s = now / 1000
    const drift = (i, size) => Math.sin(s * 0.37 * pace[i] + phase[i]) * size + Math.sin(s * 0.91 * pace[i] + phase[i] * 2) * size * 0.4
    const headX = drift(0, 1.1) + gaze.x * 0.35
    const headY = drift(1, 0.7) - (state === 'speaking' ? open * 1.1 : 0)
    const turn = drift(2, 1.4) + gaze.x * 0.6 + (state === 'thinking' ? 1.5 : 0)

    return { gazeX: gaze.x, gazeY: gaze.y, blink: closed, headX, headY, turn, nod, brow, mouthOpen, mouthWide }
  }

  return { step }
}

// One animation frame loop shared by every living portrait on the page, paused while the tab is hidden.
const subscribers = new Set()
let frame = 0
function tick(now) {
  frame = 0
  if (typeof document !== 'undefined' && document.hidden) return
  for (const run of subscribers) run(now)
  if (subscribers.size) frame = requestAnimationFrame(tick)
}
export function onFrame(run) {
  subscribers.add(run)
  if (!frame && typeof requestAnimationFrame !== 'undefined') frame = requestAnimationFrame(tick)
  return () => { subscribers.delete(run) }
}
if (typeof document !== 'undefined') document.addEventListener('visibilitychange', () => { if (!document.hidden && subscribers.size && !frame) frame = requestAnimationFrame(tick) })
