// Chooses how a character looks from their name and role, so the same character always looks the same.
// Pure and dependency-free so it can be tested in Node.

export const SKIN = ['#f6d7c3', '#eec1a1', '#d9a07a', '#b97a55', '#8d5a3b', '#6a4029']
export const HAIR_COLOUR = ['#2b1d2a', '#3a2620', '#5e3624', '#8a4630', '#b9814e', '#1f2238', '#5d6170', '#6e2a3c']
export const IRIS = ['#7a4426', '#9a6a2e', '#3f7058', '#3f6290', '#8a3050', '#5f4c8a']
export const ACCENT = ['#a8133a', '#c9a227', '#3d5a80', '#5d7f63']
export const HAIR_STYLE = ['short', 'side', 'bun', 'long', 'curly', 'bob', 'buzz', 'scarf']
export const ATTIRE = ['blazer', 'sweater', 'shirt', 'cardigan']
export const ATTIRE_COLOUR = ['#5a1828', '#7a2335', '#2f3a4a', '#3c4b3f', '#6b4a3a', '#4a3550', '#8a5a44', '#24343f']
export const BACKDROP = ['#f6dcd2', '#f2e4d0', '#ead8e2', '#dfe7dc', '#f3dccb', '#e5ddee']
export const SCARF_COLOUR = ['#8a2a3d', '#3e4f6a', '#6b5a3a', '#4f6b5a', '#7a4a66']

// FNV-1a: a stable 32-bit hash of a string.
export function hash(text) {
  let value = 0x811c9dc5
  for (const char of String(text)) {
    value ^= char.codePointAt(0)
    value = Math.imul(value, 0x01000193) >>> 0
  }
  return value >>> 0
}

// mulberry32: a small seeded random generator.
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

export function portraitTraits(name = '', role = '') {
  const random = generator(hash(String(name).trim().toLowerCase()))
  const pick = list => list[Math.floor(random() * list.length)]
  const hairStyle = pick(HAIR_STYLE)
  const formal = /manager|director|lead|chair|interview|supplier|representative|officer|hr|legal|finance|client/i.test(role)
  return {
    skin: pick(SKIN),
    hairColour: pick(HAIR_COLOUR),
    hairStyle,
    attire: formal ? (random() < 0.7 ? 'blazer' : 'shirt') : pick(ATTIRE),
    attireColour: pick(ATTIRE_COLOUR),
    backdrop: pick(BACKDROP),
    scarfColour: pick(SCARF_COLOUR),
    faceWidth: 37 + Math.round(random() * 4),
    faceHeight: 45 + Math.round(random() * 4),
    glasses: random() < 0.28,
    earrings: hairStyle !== 'scarf' && random() < 0.3,
    blinkDelay: Math.round(random() * 3000),
    irisColour: pick(IRIS),
    accent: pick(ACCENT),
  }
}

// What to call each reaction in words, for screen readers and captions.
export const REACTION_WORDS = {
  pleased: 'looks pleased', encouraging: 'looks encouraging', curious: 'looks curious', considering: 'is thinking it over',
  doubtful: 'looks doubtful', firm: 'looks firm', puzzled: 'looks puzzled', neutral: 'is listening',
}
