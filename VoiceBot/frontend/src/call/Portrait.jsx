// Original flat-style character portraits, drawn in code. Each character's look comes from their name and role.
// The head, neck and shoulders share one frame: the head turns about the top of the neck, so it never comes apart.
import { useMemo } from 'react'
import { portraitTraits, REACTION_WORDS } from './portraitTraits.mjs'
import './scene.css'

const shade = (hex, amount) => {
  const value = parseInt(hex.slice(1), 16)
  const channel = shift => Math.max(0, Math.min(255, Math.round(((value >> shift) & 255) * (1 + amount))))
  return `#${[16, 8, 0].map(shift => channel(shift).toString(16).padStart(2, '0')).join('')}`
}

// Face frame: the head is centred at (100, CY); eyes, brows and mouth sit at fixed heights inside it.
const CY = 86, EYE_Y = 93, EYE_X = 15, MOUTH_Y = 120
// A cubic whose two control points share one height peaks at `apex` when they sit at this height.
const peak = (base, apex) => (4 * apex - base) / 3
const mix = (a, b, amount) => {
  const parts = hex => [16, 8, 0].map(shift => (parseInt(hex.slice(1), 16) >> shift) & 255)
  const [x, y] = [parts(a), parts(b)]
  return `#${x.map((v, i) => Math.round(v + (y[i] - v) * amount).toString(16).padStart(2, '0')).join('')}`
}

// One expression per reaction. Brows are drawn from the outer end inward; eyes can open wider (ry),
// be partly covered by the upper lid (lid, 0 to 1), smile (curved shut) or look aside (look).
// The mouth is a line or a filled shape.
const EXPRESSIONS = {
  neutral: {
    brows: ['M77 81 Q85 77.5 93 79.5', 'M123 81 Q115 77.5 107 79.5'],
    eyes: [{ ry: 5 }, { ry: 5 }],
    mouth: { d: 'M91 120 Q100 123.5 109 120' },
  },
  pleased: {
    brows: ['M77 77 Q85 72 93 75', 'M123 77 Q115 72 107 75'],
    eyes: [{ smile: true }, { smile: true }],
    mouth: { d: 'M87 116.5 Q100 119.5 113 116.5 Q111 131 100 131 Q89 131 87 116.5 Z', fill: true, teeth: true },
    cheeks: true,
  },
  encouraging: {
    brows: ['M77 78 Q85 73.5 93 75.5', 'M123 78 Q115 73.5 107 75.5'],
    eyes: [{ ry: 4.6, lower: true }, { ry: 4.6, lower: true }],
    mouth: { d: 'M88 117 Q100 128 112 117' },
    cheeks: true,
  },
  curious: {
    brows: ['M77 74 Q85 67.5 93 71.5', 'M123 74 Q115 67.5 107 71.5'],
    eyes: [{ ry: 6.2, look: [0, -0.6] }, { ry: 6.2, look: [0, -0.6] }],
    mouth: { d: 'M95.5 121 Q100 114.5 104.5 121 Q100 126.5 95.5 121 Z', fill: true },
  },
  considering: {
    brows: ['M77 80 Q85 79 93 79', 'M123 75 Q115 70.5 107 74'],
    eyes: [{ ry: 4.8, lid: 0.18, look: [2.6, -2.6] }, { ry: 4.8, lid: 0.18, look: [2.6, -2.6] }],
    mouth: { d: 'M92 121.5 Q101 121.5 109 117.5' },
  },
  doubtful: {
    brows: ['M77 79 Q85 79.5 93 82', 'M123 75 Q115 69 107 73'],
    eyes: [{ ry: 4.8, lid: 0.5 }, { ry: 5.4 }],
    mouth: { d: 'M90 122 Q97 119.5 103 121 Q107 120.5 110 116.5' },
  },
  firm: {
    brows: ['M77 77 Q85 78 93 82.5', 'M123 77 Q115 78 107 82.5'],
    eyes: [{ ry: 4.8, lid: 0.38 }, { ry: 4.8, lid: 0.38 }],
    mouth: { d: 'M90 121 Q100 120 110 121', width: 3.8 },
  },
  puzzled: {
    brows: ['M77 75 Q85 68.5 93 73', 'M123 81 Q115 79 107 81.5'],
    eyes: [{ ry: 5.8 }, { ry: 4.8, lid: 0.22 }],
    mouth: { d: 'M90 122 Q95 117.5 100 120.5 Q105 123.5 110 118.5' },
  },
}

// The crown of the head, grown outward by `grow`, from the left side at height `base` over to the right side.
// Hair and scarves start from this so they always cover the head's own outline.
const crownArc = (L, R, W, top, grow, base, H = CY - top) =>
  `M${L - grow} ${base} L${L - grow} ${CY} C${L - grow} ${CY - (H + grow) * 0.56} ${100 - (W + grow) * 0.56} ${top - grow} 100 ${top - grow}` +
  ` C${100 + (W + grow) * 0.56} ${top - grow} ${R + grow} ${CY - (H + grow) * 0.56} ${R + grow} ${CY} L${R + grow} ${base}`

// Hair, in two layers: what falls behind the head and shoulders, and what sits on top of the head.
function hairLayers(t, L, R, top) {
  const c = t.hairColour, W = t.faceWidth
  const arc = (grow, base) => crownArc(L, R, W, top, grow, base)
  // The cap hugs the crown and comes down to the temples, with its inner edge forming the hairline.
  const crown = (lift = 4, hairline = 64, base = 94) =>
    arc(lift, base) +
    ` C${R - 1} ${base - 16} ${R - 12} ${hairline} 100 ${hairline} C${L + 12} ${hairline} ${L + 1} ${base - 16} ${L - 2.5} ${base} Z`
  switch (t.hairStyle) {
    case 'scarf': return { back: null, front: null }
    case 'long': return {
      back: <path d={`${arc(7, 96)} C${R + 9} 128 ${R + 14} 150 ${R + 18} 176 L${L - 18} 176 C${L - 14} 150 ${L - 9} 128 ${L - 6} 96 Z`} fill={shade(c, -0.12)}/>,
      front: <path d={`${arc(4, 104)} C${R - 2} 84 ${R - 8} 68 103 62 Q100 66 97 62 C${L + 8} 68 ${L + 2} 84 ${L - 3} 104 Z`} fill={c}/>,
    }
    case 'bob': return {
      back: <path d={`${arc(7, 92)} L${R + 7} 126 Q${R} 134 ${R - 8} 128 L${L + 8} 128 Q${L} 134 ${L - 7} 126 Z`} fill={shade(c, -0.12)}/>,
      front: <path d={`${arc(4, 112)} L${R - 3} 110 C${R - 3} 92 ${R - 4} 78 ${R - 10} 72 Q100 76 ${L + 10} 70 C${L + 3} 78 ${L + 3} 92 ${L + 3} 110 Z`} fill={c}/>,
    }
    case 'curly': {
      const ring = [[-1.02, 0.08], [-0.98, -0.32], [-0.78, -0.66], [-0.42, -0.9], [0, -0.98], [0.42, -0.9], [0.78, -0.66], [0.98, -0.32], [1.02, 0.08]]
      const fringe = [[-0.8, -0.42], [-0.5, -0.6], [-0.17, -0.66], [0.17, -0.66], [0.5, -0.6], [0.8, -0.42]]
      return {
        back: <g fill={shade(c, -0.06)}>{ring.map(([x, y], i) => <circle key={i} cx={100 + x * (W + 4)} cy={CY + y * (CY - top + 4)} r={15}/>)}</g>,
        front: <g fill={c}><path d={crown(3, 66)}/>{fringe.map(([x, y], i) => <circle key={i} cx={100 + x * W} cy={CY + y * (CY - top)} r={8.5}/>)}</g>,
      }
    }
    case 'side': return {
      back: null,
      front: <path d={`${arc(3, 96)} C${R} 84 ${R - 4} 72 ${R - 10} 68 C${R - 22} 62 ${L + W * 0.55} 60 ${L + W * 0.5} 58 C${L + 10} 66 ${L + 2} 78 ${L - 2.5} 96 Z`} fill={c}/>,
    }
    case 'bun': return { back: <circle cx="100" cy={top - 7} r="15" fill={shade(c, -0.12)}/>, front: <path d={crown(4, 63)} fill={c}/> }
    case 'buzz': return { back: null, front: <path d={crown(1.5, 60, 90)} fill={mix(c, t.skin, 0.38)}/> }
    default: return { back: null, front: <path d={crown()} fill={c}/> }
  }
}

function Clothes({ t, skinDark }) {
  const body = t.attireColour, dark = shade(body, -0.28), light = shade(body, 0.12)
  return <g transform="translate(0 -6)">
    {/* The neck runs from under the chin down beneath the collar, so the head is always joined to the body. */}
    <path d="M85 118 L84 150 Q100 160 116 150 L115 118 Z" fill={skinDark}/>
    <path d="M6 212 L6 200 C7 174 28 158 68 151 Q85 147.5 100 156 Q115 147.5 132 151 C172 158 193 174 194 200 L194 212 Z" fill={body}/>
    <path d="M30 206 C31 186 36 176 44 170" fill="none" stroke={light} strokeWidth="2.5" strokeLinecap="round" opacity=".5"/>
    {t.attire === 'blazer' && <>
      <path d="M84 150 Q100 159 116 150 L100 184 Z" fill="#fbf4ec"/>
      <path d="M84 150 L100 184 L90 194 L66 156 Z M116 150 L100 184 L110 194 L134 156 Z" fill={dark}/>
    </>}
    {t.attire === 'shirt' && <>
      <path d="M83 149 Q100 158 117 149 L119 156 L100 172 L81 156 Z" fill="#fbf4ec"/>
      <path d="M83 149 L100 164 L91 172 L78 155 Z M117 149 L100 164 L109 172 L122 155 Z" fill="#f1e6da"/>
      <path d="M100 168 V210" stroke={dark} strokeWidth="1.6"/>
    </>}
    {t.attire === 'sweater' && <path d="M82 150 Q100 162 118 150" fill="none" stroke={dark} strokeWidth="5" strokeLinecap="round"/>}
    {t.attire === 'cardigan' && <>
      <path d="M84 150 Q100 159 116 150 L100 178 Z" fill="#f3e6d5"/>
      <path d="M85 152 L96 210 M115 152 L104 210" stroke={dark} strokeWidth="3"/>
    </>}
  </g>
}

function Eye({ x, eye, skin, look }) {
  const dark = '#2a1a1a', [dx, dy] = eye.look || look || [0, 0]
  if (eye.smile) return <path d={`M${x - 5.5} ${EYE_Y + 1.5} Q${x} ${EYE_Y - 5.5} ${x + 5.5} ${EYE_Y + 1.5}`} fill="none" stroke={dark} strokeWidth="2.8" strokeLinecap="round"/>
  const ry = eye.ry || 5, rx = 4.1, lidTop = EYE_Y - ry - 1, lidY = EYE_Y - ry + (eye.lid || 0) * ry * 2
  return <g>
    <ellipse cx={x} cy={EYE_Y} rx={rx} ry={ry} fill={dark}/>
    <circle cx={x + 1.4 + dx * 0.5} cy={EYE_Y - ry * 0.35 + dy * 0.5} r="1.35" fill="#fff"/>
    {eye.lid > 0 && <>
      <path d={`M${x - rx - 1.5} ${lidTop} H${x + rx + 1.5} V${lidY} H${x - rx - 1.5} Z`} fill={skin}/>
      <path d={`M${x - rx - 1} ${lidY + 0.4} Q${x} ${lidY - 0.8} ${x + rx + 1} ${lidY + 0.4}`} fill="none" stroke={dark} strokeWidth="1.8" strokeLinecap="round"/>
    </>}
    {eye.lower && <path d={`M${x - rx - 1.5} ${EYE_Y + ry + 1.5} Q${x} ${EYE_Y + 1} ${x + rx + 1.5} ${EYE_Y + ry + 1.5} Z`} fill={skin}/>}
  </g>
}

export function Portrait({ name = '', role = '', state = 'idle', reaction = 'neutral', size = 160, className = '', decorative = false }) {
  const t = useMemo(() => portraitTraits(name, role), [name, role])
  const face = EXPRESSIONS[reaction] || EXPRESSIONS.neutral
  const W = t.faceWidth, H = t.faceHeight, L = 100 - W, R = 100 + W, top = CY - H, chin = CY + H
  const skinDark = shade(t.skin, -0.14), skinDeep = shade(t.skin, -0.24)
  const scarf = t.hairStyle === 'scarf'
  const hair = hairLayers(t, L, R, top)
  const clip = `pt-clip-${t.blinkDelay}-${W}-${H}`
  const head = `M${L} ${CY} C${L} ${CY - H * 0.56} ${100 - W * 0.56} ${top} 100 ${top} C${100 + W * 0.56} ${top} ${R} ${CY - H * 0.56} ${R} ${CY}` +
    ` C${R} ${CY + H * 0.48} ${100 + W * 0.52} ${chin} 100 ${chin} C${100 - W * 0.52} ${chin} ${L} ${CY + H * 0.48} ${L} ${CY} Z`
  const label = decorative ? undefined : `${name}${role ? `, ${role}` : ''}, ${REACTION_WORDS[reaction] || REACTION_WORDS.neutral}`
  return <svg className={`portrait ${className}`.trim()} data-state={state} data-reaction={reaction} viewBox="0 0 200 200" width={size} height={size}
    role={decorative ? undefined : 'img'} aria-label={label} aria-hidden={decorative ? 'true' : undefined} style={{ '--blink-delay': `${t.blinkDelay}ms` }}>
    <defs><clipPath id={clip}><circle cx="100" cy="100" r="100"/></clipPath></defs>
    <g clipPath={`url(#${clip})`}>
      <rect width="200" height="200" fill={t.backdrop}/>
      <circle className="pt-halo" cx="100" cy="92" r="80" fill="#fff" opacity=".35"/>
      <g className="pt-figure">
        {/* Back layers turn with the head so long hair and scarves stay attached to it. */}
        <g className="pt-tilt">
          {scarf && <path d={`${crownArc(L, R, W, top, 11, 96)} C${R + 14} 124 ${R + 20} 146 ${R + 30} 168 L${L - 30} 168 C${L - 20} 146 ${L - 14} 124 ${L - 12} 96 Z`} fill={t.scarfColour}/>}
          {hair.back}
        </g>
        <Clothes t={t} skinDark={skinDark}/>
        <g className="pt-tilt">
          {/* A scarf falls from around the face over the shoulders, wrapping under the chin. */}
          {scarf && <path d={`M${L - 4} 98 C${L - 10} 136 ${L - 28} 158 ${L - 44} 206 L${R + 44} 206 C${R + 28} 158 ${R + 10} 136 ${R + 4} 98 Q${R} ${chin + 16} 100 ${chin + 15} Q${L} ${chin + 16} ${L - 4} 98 Z`} fill={shade(t.scarfColour, -0.08)}/>}
          {!scarf && <><ellipse cx={L + 1} cy={EYE_Y + 2} rx="6.5" ry="9.5" fill={skinDark}/><ellipse cx={R - 1} cy={EYE_Y + 2} rx="6.5" ry="9.5" fill={skinDark}/></>}
          {t.earrings && <><circle cx={L} cy={EYE_Y + 13} r="2.8" fill="#d9a441"/><circle cx={R} cy={EYE_Y + 13} r="2.8" fill="#d9a441"/></>}
          <path d={head} fill={t.skin}/>
          {scarf && <path d={`${crownArc(L, R, W, top, 5, 106)} L${R + 1} 106 C${R} 84 ${R - 8} 66 100 64 C${L + 8} 66 ${L} 84 ${L - 1} 106 Z`} fill={t.scarfColour}/>}
          {scarf && <path d={`M${L + 1} 102 C${L + 1} 82 ${L + 10} 67 100 66 C${R - 10} 67 ${R - 1} 82 ${R - 1} 102`} fill="none" stroke={shade(t.scarfColour, -0.22)} strokeWidth="2.4" strokeLinecap="round"/>}
          {hair.front}
          <g className={`pt-cheeks${face.cheeks ? ' on' : ''}`}><ellipse cx={100 - 23} cy="109" rx="7" ry="5" fill="#e8857a"/><ellipse cx={100 + 23} cy="109" rx="7" ry="5" fill="#e8857a"/></g>
          <g className="pt-look"><g className="pt-eyes">
            <Eye x={100 - EYE_X} eye={face.eyes[0]} skin={t.skin}/>
            <Eye x={100 + EYE_X} eye={face.eyes[1]} skin={t.skin}/>
          </g></g>
          <g className="pt-brows" fill="none" stroke={shade(t.hairColour, 0.05)} strokeWidth="3.8" strokeLinecap="round">
            <path className="pt-brow" d={face.brows[0]}/><path className="pt-brow" d={face.brows[1]}/>
          </g>
          <path d="M100 98 Q96 107.5 99 110 Q101.5 111 104 109.5" fill="none" stroke={skinDeep} strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round"/>
          <g className="pt-mouth">
            {face.mouth.fill
              ? <g className="pt-lips"><path d={face.mouth.d} fill="#6a2430"/>{face.mouth.teeth && <path d="M90 118 Q100 120.6 110 118 L109.4 121 Q100 123 90.6 121 Z" fill="#fff"/>}</g>
              : <path className="pt-lips" d={face.mouth.d} fill="none" stroke="#7a2f35" strokeWidth={face.mouth.width || 3.2} strokeLinecap="round" strokeLinejoin="round"/>}
            <ellipse className="pt-open" cx="100" cy={MOUTH_Y + 1} rx="7.5" ry="6" fill="#5a1f27"/>
          </g>
          {t.glasses && <g fill="#ffffff26" stroke="#2a1a1a" strokeWidth="2.3"><rect x={100 - EYE_X - 10} y={EYE_Y - 8} width="20" height="16" rx="6"/><rect x={100 + EYE_X - 10} y={EYE_Y - 8} width="20" height="16" rx="6"/><path d={`M${100 - 5} ${EYE_Y - 1} Q100 ${EYE_Y - 4} ${100 + 5} ${EYE_Y - 1}`} fill="none"/></g>}
        </g>
      </g>
    </g>
  </svg>
}
