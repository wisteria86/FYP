// Original anime-style character portraits, drawn in code. Each character's look comes from their name and role.
// Big glossy eyes, a tapered face, locks of hair with cel shading. The head, neck and shoulders share one frame:
// the head turns about the top of the neck, so it never comes apart.
import { useEffect, useId, useMemo, useRef } from 'react'
import { portraitTraits, hash, REACTION_WORDS } from './portraitTraits.mjs'
import { createLife, levels, onFrame } from './portraitLife.mjs'
import './scene.css'

const shade = (hex, amount) => {
  const value = parseInt(hex.slice(1), 16)
  const channel = shift => Math.max(0, Math.min(255, Math.round(((value >> shift) & 255) * (1 + amount))))
  return `#${[16, 8, 0].map(shift => channel(shift).toString(16).padStart(2, '0')).join('')}`
}
const mix = (a, b, amount) => {
  const parts = hex => [16, 8, 0].map(shift => (parseInt(hex.slice(1), 16) >> shift) & 255)
  const [x, y] = [parts(a), parts(b)]
  return `#${x.map((v, i) => Math.round(v + (y[i] - v) * amount).toString(16).padStart(2, '0')).join('')}`
}

// Face frame: the head is centred at (100, CY). Anime faces carry the eyes low and large.
const CY = 88, EYE_Y = 102, EYE_X = 17, INK = '#2b1a24'

// One expression per reaction. Brows and mouth are drawn on a reference face and placed by the portrait.
// Eyes can open wider (ry, 5 is normal), have the upper lid lowered (lid, 0 to 1), smile shut, be pushed up
// from below (lower), or look aside (look).
const EXPRESSIONS = {
  neutral: {
    brows: ['M77 81 Q85 77.5 93 79.5', 'M123 81 Q115 77.5 107 79.5'],
    eyes: [{ ry: 5 }, { ry: 5 }],
    mouth: { d: 'M93 120 Q100 122.5 107 120' },
  },
  pleased: {
    brows: ['M77 77 Q85 72 93 75', 'M123 77 Q115 72 107 75'],
    eyes: [{ smile: true }, { smile: true }],
    mouth: { d: 'M88 116.5 Q100 119 112 116.5 Q110 130 100 130 Q90 130 88 116.5 Z', fill: true, tongue: true },
    cheeks: true,
  },
  encouraging: {
    brows: ['M77 78 Q85 73.5 93 75.5', 'M123 78 Q115 73.5 107 75.5'],
    eyes: [{ ry: 4.6, lower: true }, { ry: 4.6, lower: true }],
    mouth: { d: 'M90 118 Q100 126 110 118' },
    cheeks: true,
  },
  curious: {
    brows: ['M77 74 Q85 67.5 93 71.5', 'M123 74 Q115 67.5 107 71.5'],
    eyes: [{ ry: 6, look: [0, -0.6] }, { ry: 6, look: [0, -0.6] }],
    mouth: { d: 'M96 121 Q100 115.5 104 121 Q100 126 96 121 Z', fill: true },
  },
  considering: {
    brows: ['M77 80 Q85 79 93 79', 'M123 75 Q115 70.5 107 74'],
    eyes: [{ ry: 4.8, lid: 0.2, look: [2.4, -2.2] }, { ry: 4.8, lid: 0.2, look: [2.4, -2.2] }],
    mouth: { d: 'M93 121.5 Q101 121.5 108 118' },
  },
  doubtful: {
    brows: ['M77 79 Q85 79.5 93 82', 'M123 75 Q115 69 107 73'],
    eyes: [{ ry: 4.8, lid: 0.45 }, { ry: 5.3 }],
    mouth: { d: 'M91 122 Q97 119.5 103 121 Q107 120.5 110 117' },
  },
  firm: {
    brows: ['M77 77 Q85 78 93 82.5', 'M123 77 Q115 78 107 82.5'],
    eyes: [{ ry: 4.8, lid: 0.35 }, { ry: 4.8, lid: 0.35 }],
    mouth: { d: 'M92 121 Q100 120 108 121', width: 3.4 },
  },
  puzzled: {
    brows: ['M77 75 Q85 68.5 93 73', 'M123 81 Q115 79 107 81.5'],
    eyes: [{ ry: 5.8 }, { ry: 4.8, lid: 0.22 }],
    mouth: { d: 'M91 122 Q95.5 118 100 120.5 Q104.5 123 109 119' },
  },
}

// The head: a round crown, full cheeks at eye level and a soft point at the chin.
function headPath(W, H) {
  const top = CY - H, chin = CY + H, L = 100 - W, R = 100 + W
  return `M${L} ${CY} C${L} ${CY - H * 0.58} ${100 - W * 0.58} ${top} 100 ${top} C${100 + W * 0.58} ${top} ${R} ${CY - H * 0.58} ${R} ${CY}` +
    ` C${R} ${CY + H * 0.36} ${R - W * 0.18} ${CY + H * 0.62} ${100 + W * 0.42} ${chin - H * 0.14}` +
    ` Q${100 + W * 0.16} ${chin} 100 ${chin} Q${100 - W * 0.16} ${chin} ${100 - W * 0.42} ${chin - H * 0.14}` +
    ` C${L + W * 0.18} ${CY + H * 0.62} ${L} ${CY + H * 0.36} ${L} ${CY} Z`
}

// The hair's outer edge over the crown, from the left side at height `y` over to the right side.
const outer = (W, H, grow, y) => {
  const L = 100 - W - grow, R = 100 + W + grow, top = CY - H - grow
  return `M${L} ${y} L${L} ${CY} C${L} ${CY - (H + grow) * 0.62} ${100 - (W + grow) * 0.6} ${top} 100 ${top}` +
    ` C${100 + (W + grow) * 0.6} ${top} ${R} ${CY - (H + grow) * 0.62} ${R} ${CY} L${R} ${y}`
}

// A run of locks: points alternate between roots on the hairline and tips that hang down.
// `lean` bends every lock sideways, for swept fringes.
function locks(points, lean = 0) {
  let d = ''
  for (let i = 1; i < points.length; i++) {
    const [ax, ay] = points[i - 1], [bx, by] = points[i]
    const down = by > ay
    const cx = (ax + bx) / 2 + lean * Math.abs(by - ay) * 0.35, cy = down ? ay + (by - ay) * 0.25 : by + (ay - by) * 0.25
    d += ` Q${cx.toFixed(1)} ${cy.toFixed(1)} ${bx} ${by}`
  }
  return d
}

// Hair in two layers, as path data: what falls behind the head and shoulders, and what sits on top.
// The front layer always ends in locks along the forehead; its shape also casts the shadow on the face.
function hairShapes(style, W, H) {
  const L = 100 - W, R = 100 + W, top = CY - H, line = top + 15, brow = EYE_Y - 19
  const across = (tips, rootY = line, lean = 0) => {
    // Roots sit between the tips, so every lock is a point.
    const points = []
    tips.forEach(([x, y], i) => {
      if (i > 0) points.push([((tips[i - 1][0] + x) / 2).toFixed(1) * 1, rootY + (i % 2) * 3])
      points.push([x, y])
    })
    return locks(points, lean)
  }
  // A fringe of pointed locks, drawn right to left from the right temple.
  const fringe = (lean = 0, length = 0) => across([
    [R + 4, CY + 16], [R - W * 0.24 + lean * 3, brow + 4 + length], [100 + W * 0.3 + lean * 4, brow + length], [100 - W * 0.12 + lean * 4, brow + 3 + length],
    [L + W * 0.55 + lean * 3, brow + 1 + length], [L + W * 0.2, brow + 4 + length], [L - 4, CY + 16],
  ], line, lean)
  switch (style) {
    case 'long': return {
      back: `${outer(W, H, 7, 100)} L${R + 16} 168 L${R + 6} 160 L${R - 2} 172 L${L + 2} 172 L${L - 6} 160 L${L - 16} 168 Z`,
      front: `${outer(W, H, 4, CY + 42)} Q${R - 1} ${CY + 6} ${R - 7} ${brow}${across([
        [R - 7, brow], [100 + W * 0.42, brow + 5], [100 + 3, brow + 2], [100 - W * 0.3, brow + 6], [L + 7, brow],
      ], line, 0.3)} Q${L + 1} ${CY + 6} ${L - 4} ${CY + 42} Z`,
    }
    case 'bob': return {
      back: `${outer(W, H, 7, 100)} L${R + 8} 128 L${R + 2} 124 L${R - 4} 130 L${L + 4} 130 L${L - 2} 124 L${L - 8} 128 Z`,
      front: `${outer(W, H, 4, CY + 26)} L${R - 3} ${CY + 30} Q${R - 2} ${CY + 4} ${R - 8} ${brow + 2}` +
        `${across([[R - 8, brow + 2], [R - W * 0.45, brow + 6], [100, brow + 4], [L + W * 0.45, brow + 6], [L + 8, brow + 2]], brow - 4)}` +
        ` Q${L + 2} ${CY + 4} ${L + 3} ${CY + 30} Z`,
    }
    case 'side': return {
      back: `${outer(W, H, 5, CY + 8)} Z`,
      front: `${outer(W, H, 4, CY + 6)}${across([
        [R + 4, CY + 6], [R - W * 0.3, brow - 6], [100 + W * 0.1, brow - 2], [100 - W * 0.35, brow + 4], [L + 2, brow + 12], [L - 4, CY + 14],
      ], line - 2, -1)} Z`,
    }
    case 'bun': return {
      back: `M100 ${top - 20} a13 13 0 1 1 -0.1 0 Z`,
      front: `${outer(W, H, 3, CY + 26)}${across([
        [R + 3, CY + 26], [R - 2, brow + 4], [100 + W * 0.45, brow - 1], [100 + 4, brow - 5], [100 - W * 0.3, brow - 1], [L + W * 0.2, brow + 3], [L - 3, CY + 26],
      ], line, 0.2)} Z`,
    }
    case 'curly': {
      const bumps = Array.from({ length: 11 }, (_, i) => {
        const a = Math.PI * (1.02 + i * 0.096), rx = W + 9, ry = H + 9
        return `M${(100 + Math.cos(a) * rx).toFixed(1)} ${(CY + 4 + Math.sin(a) * ry).toFixed(1)} a9.5 9.5 0 1 1 0.1 0 Z`
      }).join(' ')
      return {
        back: `${outer(W, H, 9, CY + 2)} Q100 ${CY + 18} ${100 - W - 9} ${CY + 2} Z ${bumps}`,
        front: `${outer(W, H, 5, CY + 12)}${across([
          [R + 5, CY + 12], [R - 4, brow - 2], [100 + W * 0.42, brow - 7], [100 + 2, brow - 4], [100 - W * 0.42, brow - 7], [L + 4, brow - 2], [L - 5, CY + 12],
        ], line - 4, 0.6)} Z`,
      }
    }
    case 'buzz': {
      // Short and spiky, standing up from the crown.
      const spikes = [-0.8, -0.45, -0.1, 0.25, 0.6].map((x, i) => {
        const bx = 100 + x * W, by = top + 6 - Math.cos(x) * 4
        return ` M${bx - 9} ${by + 6} L${bx + 2 + i} ${by - 11} L${bx + 9} ${by + 6} Z`
      }).join('')
      return {
        back: null,
        front: `${outer(W, H, 3, CY + 2)}${across([
          [R + 3, CY + 2], [R - 6, line + 2], [100 + W * 0.3, line + 4], [100 - W * 0.15, line + 2], [L + 8, line + 5], [L - 3, CY + 2],
        ], line - 8, -0.5)} Z${spikes}`,
      }
    }
    case 'scarf': return { back: null, front: null }
    default: return {
      back: `${outer(W, H, 5, CY + 10)} Z`,
      front: `${outer(W, H, 4, CY + 16)}${fringe(0.4)} Z`,
    }
  }
}

function Clothes({ t, skin, shadow }) {
  const body = t.attireColour, dark = shade(body, -0.28), light = shade(body, 0.14)
  return <g transform="translate(0 -6)">
    {/* A slim neck runs from under the chin down beneath the collar, so the head is always joined to the body. */}
    <path d="M90.5 116 L89.5 152 Q100 160 110.5 152 L109.5 116 Z" fill={skin}/>
    <path d="M89.5 120 Q100 142 110.5 120 L110.5 116 L89.5 116 Z" fill={shadow}/>
    <path d="M6 212 L6 200 C7 174 28 158 68 151 Q85 147.5 100 156 Q115 147.5 132 151 C172 158 193 174 194 200 L194 212 Z" fill={body}/>
    <path d="M24 206 C26 186 34 174 46 167 M176 206 C174 186 166 174 154 167" fill="none" stroke={dark} strokeWidth="2" strokeLinecap="round" opacity=".5"/>
    <path d="M58 156 Q70 152 82 152" fill="none" stroke={light} strokeWidth="2.5" strokeLinecap="round" opacity=".6"/>
    {t.attire === 'blazer' && <>
      <path d="M85 150 Q100 159 115 150 L100 184 Z" fill="#fbf4ec"/>
      <path d="M85 150 L100 184 L90 194 L66 156 Z M115 150 L100 184 L110 194 L134 156 Z" fill={dark}/>
      <path d="M96.5 160 L100 157 L103.5 160 L101.8 178 L100 181 L98.2 178 Z" fill={shade(t.accent, -0.05)}/>
    </>}
    {t.attire === 'shirt' && <>
      <path d="M83 149 Q100 158 117 149 L119 156 L100 172 L81 156 Z" fill="#fbf4ec"/>
      <path d="M83 149 L100 164 L91 172 L78 155 Z M117 149 L100 164 L109 172 L122 155 Z" fill="#efe3d6"/>
      <path d="M100 168 V210" stroke={dark} strokeWidth="1.6"/>
    </>}
    {t.attire === 'sweater' && <path d="M83 150 Q100 162 117 150" fill="none" stroke={dark} strokeWidth="5" strokeLinecap="round"/>}
    {t.attire === 'cardigan' && <>
      <path d="M84 150 Q100 159 116 150 L100 178 Z" fill="#f3e6d5"/>
      <path d="M85 152 L96 210 M115 152 L104 210" stroke={dark} strokeWidth="3"/>
    </>}
  </g>
}

// One anime eye: white, a coloured iris with a dark rim, a glowing lower half and two highlights,
// under a heavy upper lash line that flicks out at the outer corner. `side` is -1 for the left eye.
function Eye({ x, side, eye, t, skin, id }) {
  const k = (eye.ry || 5) / 5, y = EYE_Y, w = 11, up = 13.5 * k, down = 10 * k
  const inner = x - side * w, outerX = x + side * w
  // The lash line is a filled crescent: thin at the inner corner, heavy toward the outer corner.
  const lash = `M${inner - side * 0.5} ${y - 0.5} C${inner + side * 3} ${y - up - 2} ${outerX - side * 7} ${y - up - 3.4} ${outerX + side * 2} ${y - 3.5}` +
    ` L${outerX - side * 0.2} ${y - 1.2} C${outerX - side * 6} ${y - up + 0.4} ${inner + side * 4} ${y - up + 0.2} ${inner + side * 0.8} ${y + 0.3} Z`
  if (eye.smile) return <g>
    <path d={`M${x - 10.5} ${y + 1} Q${x} ${y - 9.5} ${x + 10.5} ${y + 1}`} fill="none" stroke={INK} strokeWidth="3.4" strokeLinecap="round"/>
    <path d={`M${outerX - side * 0.5} ${y - 1} l${side * 3} -2`} stroke={INK} strokeWidth="2" strokeLinecap="round"/>
  </g>
  const white = `M${inner} ${y} C${inner + side * 2} ${y - up} ${outerX - side * 4} ${y - up - 1} ${outerX} ${y - 2} C${outerX - side * 1} ${y + down} ${inner + side * 3} ${y + down} ${inner} ${y} Z`
  const [dx, dy] = eye.look || [0, 0], iris = t.irisColour
  const lidDrop = (eye.lid || 0) * (up + down) * 0.85
  return <g>
    <clipPath id={id}><path d={white}/></clipPath>
    <path d={white} fill="#fffdfb"/>
    <g clipPath={`url(#${id})`}>
      <g transform={`translate(${dx} ${dy})`}><g className="pt-look">
        <ellipse cx={x} cy={y} rx="7.8" ry={11 * Math.min(k, 1.1)} fill={shade(iris, -0.5)}/>
        <ellipse cx={x} cy={y + 0.8} rx="6.4" ry={9.4 * Math.min(k, 1.1)} fill={iris}/>
        <ellipse cx={x} cy={y + 5.4} rx="4.8" ry="4.2" fill={mix(iris, '#ffffff', 0.5)} opacity=".8"/>
        <ellipse cx={x} cy={y} rx="2.9" ry="4.6" fill={shade(iris, -0.66)}/>
        <ellipse cx={x + 2.8} cy={y - 4.4} rx="3" ry="3.5" fill="#fff"/>
        <circle cx={x - 3} cy={y + 5.2} r="1.4" fill="#fff" opacity=".9"/>
      </g></g>
      {/* The upper lid casts a soft shadow across the top of the eye. */}
      <path d={`M${x - 12} ${y - up - 4} H${x + 12} V${y - up + 2.6} H${x - 12} Z`} fill={shade(iris, -0.5)} opacity=".28"/>
      {lidDrop > 0 && <path d={`M${x - 12} ${y - up - 4} H${x + 12} V${y - up + lidDrop} H${x - 12} Z`} fill={skin}/>}
      {eye.lower && <path d={`M${x - 12} ${y + down + 3} L${x - 12} ${y + 3.5} Q${x} ${y - 0.5} ${x + 12} ${y + 3.5} L${x + 12} ${y + down + 3} Z`} fill={skin}/>}
    </g>
    <g transform={`translate(0 ${lidDrop.toFixed(2)})`}>
      <path d={lash} fill={INK} stroke={INK} strokeWidth=".8" strokeLinejoin="round"/>
      <path d={`M${outerX + side * 1} ${y - 4} l${side * 3.6} -2.8`} stroke={INK} strokeWidth="2" strokeLinecap="round"/>
    </g>
    <path d={`M${x + side * 1} ${y + down - 0.4} Q${x + side * 5} ${y + down + 0.2} ${outerX - side * 1.5} ${y + down * 0.45}`} fill="none" stroke={INK} strokeWidth="1.3" strokeLinecap="round" opacity=".55"/>
  </g>
}

// Runs the life engine for a portrait and writes its pose to CSS variables, without re-rendering.
function useLife(ref, alive, name, inputs) {
  const latest = useRef(inputs)
  latest.current = inputs
  useEffect(() => {
    const svg = ref.current
    if (!alive || !svg) return
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
    const life = createLife(hash(String(name).trim().toLowerCase()) || 1)
    const set = (key, value) => svg.style.setProperty(key, value.toFixed(3))
    svg.classList.add('alive')
    const stop = onFrame(now => {
      const { state, reaction, look } = latest.current
      const pose = life.step(now, { state, reaction, look, voice: state === 'speaking' ? levels.voice : 0, driven: levels.driven, heard: state === 'listening' ? levels.heard : 0 })
      set('--gx', pose.gazeX); set('--gy', pose.gazeY); set('--blink', pose.blink)
      set('--hx', pose.headX); set('--hy', pose.headY + pose.nod); set('--turn', pose.turn)
      set('--brow', pose.brow); set('--mo', pose.mouthOpen); set('--mw', pose.mouthWide)
    })
    return () => { stop(); svg.classList.remove('alive') }
  }, [alive, name, ref])
}

export function Portrait({ name = '', role = '', state = 'idle', reaction = 'neutral', size = 160, className = '', decorative = false, alive = false, look }) {
  const t = useMemo(() => portraitTraits(name, role), [name, role])
  const svgRef = useRef(null)
  useLife(svgRef, alive, name, { state, reaction, look })
  const uid = `pt${useId().replace(/[^a-zA-Z0-9]/g, '')}`
  const face = EXPRESSIONS[reaction] || EXPRESSIONS.neutral
  const W = t.faceWidth, H = t.faceHeight, L = 100 - W, R = 100 + W, top = CY - H, chin = CY + H
  const skin = t.skin, skinShadow = mix(shade(skin, -0.16), '#b0485a', 0.12), hair = t.hairColour
  const scarf = t.hairStyle === 'scarf'
  const shapes = useMemo(() => hairShapes(t.hairStyle, W, H), [t.hairStyle, W, H])
  const head = headPath(W, H)
  const label = decorative ? undefined : `${name}${role ? `, ${role}` : ''}, ${REACTION_WORDS[reaction] || REACTION_WORDS.neutral}`
  return <svg ref={svgRef} className={`portrait ${className}`.trim()} data-state={state} data-reaction={reaction} viewBox="0 0 200 200" width={size} height={size}
    role={decorative ? undefined : 'img'} aria-label={label} aria-hidden={decorative ? 'true' : undefined} style={{ '--blink-delay': `${t.blinkDelay}ms` }}>
    <defs>
      <clipPath id={`${uid}-frame`}><circle cx="100" cy="100" r="100"/></clipPath>
      <clipPath id={`${uid}-face`}><path d={head}/></clipPath>
      {shapes.front && <clipPath id={`${uid}-hair`}><path d={shapes.front}/></clipPath>}
      <radialGradient id={`${uid}-bg`} cx="50%" cy="38%" r="70%"><stop offset="0" stopColor="#fff" stopOpacity=".75"/><stop offset="1" stopColor={t.backdrop} stopOpacity="0"/></radialGradient>
    </defs>
    <g clipPath={`url(#${uid}-frame)`}>
      <rect width="200" height="200" fill={t.backdrop}/>
      <circle className="pt-halo" cx="100" cy="90" r="86" fill={`url(#${uid}-bg)`}/>
      <g className="pt-figure">
        {/* Back layers turn with the head so long hair and scarves stay attached to it. */}
        <g className="pt-tilt">
          {scarf && <path d={`${outer(W, H, 11, 96)} C${R + 14} 124 ${R + 20} 146 ${R + 30} 168 L${L - 30} 168 C${L - 20} 146 ${L - 14} 124 ${L - 11} 96 Z`} fill={t.scarfColour}/>}
          {shapes.back && <path d={shapes.back} fill={shade(hair, -0.22)}/>}
        </g>
        <Clothes t={t} skin={skin} shadow={skinShadow}/>
        <g className="pt-tilt">
          {scarf && <path d={`M${L - 4} 98 C${L - 10} 136 ${L - 28} 158 ${L - 44} 206 L${R + 44} 206 C${R + 28} 158 ${R + 10} 136 ${R + 4} 98 Q${R} ${chin + 16} 100 ${chin + 15} Q${L} ${chin + 16} ${L - 4} 98 Z`} fill={shade(t.scarfColour, -0.08)}/>}
          {!scarf && <><path d={`M${L + 2} ${EYE_Y - 8} q-8 2 -6 12 q2 7 7 6 Z`} fill={skinShadow}/><path d={`M${R - 2} ${EYE_Y - 8} q8 2 6 12 q-2 7 -7 6 Z`} fill={skinShadow}/></>}
          {t.earrings && <><circle cx={L - 1} cy={EYE_Y + 11} r="2.4" fill="#e0b04f"/><circle cx={R + 1} cy={EYE_Y + 11} r="2.4" fill="#e0b04f"/></>}
          <path d={head} fill={skin}/>
          {/* Cel shading: the hair casts a shadow on the forehead, and the jaw is shaded on one side. */}
          <g clipPath={`url(#${uid}-face)`}>
            {shapes.front && <path d={shapes.front} transform="translate(1.5 4)" fill={skinShadow}/>}
            {scarf && <path d={`M${L - 6} 60 Q100 ${top + 26} ${R + 6} 60 V${top + 30} Q100 ${top + 34} ${L - 6} ${top + 30} Z`} fill={skinShadow}/>}
            <path d={`M${R - 6} ${CY + 4} C${R - 4} ${CY + 26} ${100 + W * 0.3} ${chin - 6} 100 ${chin + 2} L${R + 4} ${chin + 4} L${R + 4} ${CY} Z`} fill={skinShadow} opacity=".55"/>
          </g>
          {scarf && <>
            <path d={`${outer(W, H, 5, 108)} L${R + 1} 108 C${R} 84 ${R - 8} 64 100 62 C${L + 8} 64 ${L} 84 ${L - 1} 108 Z`} fill={t.scarfColour}/>
            <path d={`M${L + 1} 104 C${L + 1} 82 ${L + 10} 65 100 64 C${R - 10} 65 ${R - 1} 82 ${R - 1} 104`} fill="none" stroke={shade(t.scarfColour, -0.25)} strokeWidth="2.2" strokeLinecap="round"/>
            <path d={`M${L - 2} 80 Q${L + 6} ${top + 4} 100 ${top - 1}`} fill="none" stroke={mix(t.scarfColour, '#ffffff', 0.3)} strokeWidth="3" strokeLinecap="round" opacity=".7"/>
          </>}
          {shapes.front && <>
            <path d={shapes.front} fill={hair}/>
            {/* A shine band across the crown, and darker strands between locks. */}
            <g clipPath={`url(#${uid}-hair)`}>
              {[[-0.62, -0.3], [-0.22, 0.12], [0.2, 0.55]].map(([a, b], i) => {
                const at = u => [100 + u * W * 1.05, top + 13 - Math.cos(u * 1.2) * 8]
                const [x1, y1] = at(a), [x2, y2] = at(b), [xm, ym] = at((a + b) / 2)
                return <path key={i} d={`M${x1} ${y1} Q${xm} ${ym - 3.4} ${x2} ${y2} Q${xm} ${ym + 1} ${x1} ${y1} Z`} fill={mix(hair, '#ffffff', 0.4)} opacity=".6"/>
              })}
              <path d={`M${100 - W * 0.4} ${top + 4} Q${100 - W * 0.5} ${top + 20} ${100 - W * 0.62} ${EYE_Y - 18} M${100 + W * 0.25} ${top + 4} Q${100 + W * 0.3} ${top + 22} ${100 + W * 0.2} ${EYE_Y - 16}`} fill="none" stroke={shade(hair, -0.3)} strokeWidth="1.6" strokeLinecap="round" opacity=".7"/>
            </g>
          </>}
          <g className={`pt-cheeks${face.cheeks ? ' on' : ''}`}>
            <ellipse cx={100 - 24} cy="113" rx="8" ry="4.2" fill="#f08a8f"/><ellipse cx={100 + 24} cy="113" rx="8" ry="4.2" fill="#f08a8f"/>
            <path d="M71 115 l2.5 -4 M75 115 l2.5 -4 M79 115 l2.5 -4 M119 115 l2.5 -4 M123 115 l2.5 -4 M127 115 l2.5 -4" stroke="#d9606b" strokeWidth="1.1" strokeLinecap="round"/>
          </g>
          <g className="pt-eyes">
            <Eye x={100 - EYE_X} side={-1} eye={face.eyes[0]} t={t} skin={skin} id={`${uid}-el`}/>
            <Eye x={100 + EYE_X} side={1} eye={face.eyes[1]} t={t} skin={skin} id={`${uid}-er`}/>
          </g>
          <g className="pt-brows" fill="none" stroke={mix(shade(hair, -0.35), INK, 0.45)} strokeWidth="2.8" strokeLinecap="round">
            <g transform="translate(-3 3)"><path className="pt-brow" d={face.brows[0]}/></g>
            <g transform="translate(3 3)"><path className="pt-brow" d={face.brows[1]}/></g>
          </g>
          <path d="M100.5 109 L99 113.2 L101.6 113.4" fill="none" stroke={shade(skin, -0.28)} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          <g className="pt-mouth" transform="translate(100 123) scale(.72) translate(-100 -120)">
            {face.mouth.fill
              ? <g className="pt-lips"><path d={face.mouth.d} fill="#7a2434"/>{face.mouth.tongue && <path d="M93 126.5 Q100 121.5 107 126.5 Q104 129.6 100 129.6 Q96 129.6 93 126.5 Z" fill="#e8737e"/>}</g>
              : <path className="pt-lips" d={face.mouth.d} fill="none" stroke="#7a2f3a" strokeWidth={face.mouth.width || 3} strokeLinecap="round" strokeLinejoin="round"/>}
            <ellipse className="pt-open" cx="100" cy="121" rx="7" ry="6.5" fill="#6a1f2c"/>
          </g>
          {t.glasses && <g fill="#ffffff1f" stroke="#3a2630" strokeWidth="2"><rect x={100 - EYE_X - 12} y={EYE_Y - 10} width="24" height="19" rx="7"/><rect x={100 + EYE_X - 12} y={EYE_Y - 10} width="24" height="19" rx="7"/><path d={`M${100 - 5} ${EYE_Y - 3} Q100 ${EYE_Y - 6} ${100 + 5} ${EYE_Y - 3}`} fill="none"/></g>}
        </g>
      </g>
    </g>
  </svg>
}
