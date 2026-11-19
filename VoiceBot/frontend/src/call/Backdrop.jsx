// Soft illustrated settings drawn behind the characters, chosen from the lesson's archetype.
const SCENE_FOR = {
  meeting: 'meeting', panel: 'meeting', knowledge: 'meeting', negotiation: 'boardroom',
  colleague: 'office', social: 'cafe', service: 'counter', customer: 'counter', interview: 'interview',
}
export const sceneFor = archetype => SCENE_FOR[archetype] || 'meeting'

const Window = ({ x, y, w, h, panes = 3 }) => <g>
  <rect x={x} y={y} width={w} height={h} rx="10" fill="url(#bd-sky)"/>
  {[0.18, 0.34, 0.5, 0.66, 0.8].map((p, i) => <rect key={i} x={x + w * p - 26} y={y + h * (0.42 + (i % 3) * 0.12)} width={52 + (i % 2) * 18} height={h} fill="#e7b7aa" opacity={0.35 + (i % 3) * 0.12}/>)}
  {Array.from({ length: panes - 1 }, (_, i) => <rect key={i} x={x + (w / panes) * (i + 1) - 4} y={y} width="8" height={h} fill="#fdf6ef"/>)}
  <rect x={x - 8} y={y - 8} width={w + 16} height={h + 16} rx="14" fill="none" stroke="#fdf6ef" strokeWidth="16"/>
</g>

const Plant = ({ x, y, s = 1 }) => <g transform={`translate(${x} ${y}) scale(${s})`}>
  {[[-40, -150, -8], [-10, -190, 4], [30, -160, 14], [-60, -100, -20], [50, -110, 24]].map(([dx, dy, r], i) => <ellipse key={i} cx={dx * 0.6} cy={dy * 0.6} rx="22" ry="58" fill={i % 2 ? '#9fb79c' : '#88a585'} transform={`rotate(${r * 2} ${dx * 0.6} ${dy * 0.6})`}/>)}
  <path d="M-34 0 L34 0 L26 70 L-26 70 Z" fill="#c98f74"/>
</g>

const Lamp = ({ x, y }) => <g>
  <path d={`M${x} 0 V${y - 30}`} stroke="#b88a78" strokeWidth="3"/>
  <circle cx={x} cy={y + 10} r="90" fill="#ffe9c9" opacity=".35"/>
  <path d={`M${x - 34} ${y} Q${x} ${y - 52} ${x + 34} ${y} Z`} fill="#a8133a" opacity=".85"/>
</g>

const SCENES = {
  meeting: <>
    <Window x={150} y={110} w={480} h={320}/>
    <g opacity=".9"><rect x="790" y="150" width="230" height="150" rx="8" fill="#fdf6ef"/><circle cx="860" cy="225" r="40" fill="#e8a99d"/><rect x="900" y="185" width="90" height="80" rx="6" fill="#d6b49f"/></g>
    <Plant x={1080} y={520}/>
    <path d="M0 610 Q600 560 1200 610 V700 H0 Z" fill="#c99d89"/>
  </>,
  boardroom: <>
    <Window x={120} y={100} w={620} h={330} panes={4}/>
    <rect x="840" y="150" width="200" height="120" rx="8" fill="#fdf6ef"/><path d="M860 240 L900 205 L940 225 L990 175 L1020 190" fill="none" stroke="#a8133a" strokeWidth="6" strokeLinecap="round" opacity=".6"/>
    <path d="M0 600 Q600 545 1200 600 V700 H0 Z" fill="#8f5a4c"/>
    <path d="M0 600 Q600 545 1200 600" fill="none" stroke="#b07a69" strokeWidth="8"/>
  </>,
  office: <>
    <rect x="0" y="0" width="1200" height="120" fill="#efdccf"/>
    <Lamp x={300} y={150}/><Lamp x={900} y={150}/>
    {[120, 470, 820].map(x => <g key={x}><rect x={x} y="380" width="260" height="20" rx="6" fill="#c99d89"/><rect x={x + 70} y="300" width="120" height="74" rx="8" fill="#5a3a3f" opacity=".75"/><rect x={x + 120} y="374" width="20" height="8" fill="#5a3a3f" opacity=".75"/></g>)}
    <Plant x={1100} y={540} s={0.9}/>
    <path d="M0 620 Q600 590 1200 620 V700 H0 Z" fill="#d8b8a6"/>
  </>,
  cafe: <>
    <Lamp x={260} y={130}/><Lamp x={600} y={110}/><Lamp x={940} y={130}/>
    <rect x="760" y="210" width="300" height="170" rx="10" fill="#4f3a36"/><g fill="#fdf0e2" opacity=".85">{[0, 1, 2, 3].map(i => <rect key={i} x="790" y={240 + i * 32} width={150 + (i % 2) * 70} height="10" rx="5"/>)}</g>
    <g>{[0, 1, 2].map(row => <g key={row}><rect x="120" y={230 + row * 70} width="400" height="10" rx="4" fill="#c99d89"/>{[0, 1, 2, 3, 4].map(i => <path key={i} d={`M${150 + i * 72} ${222 + row * 70} h30 v-24 h-30 z`} fill={['#fdf6ef', '#e8a99d', '#d6b49f'][(i + row) % 3]}/>)}</g>)}</g>
    <path d="M0 560 H1200 V700 H0 Z" fill="#b5826c"/><path d="M0 560 H1200" stroke="#d6a88f" strokeWidth="10"/>
  </>,
  counter: <>
    {[0, 1, 2].map(row => <g key={row}><rect x="80" y={160 + row * 120} width="1040" height="12" rx="4" fill="#c99d89"/>{Array.from({ length: 12 }, (_, i) => <rect key={i} x={100 + i * 84} y={100 + row * 120} width={58 - (i % 3) * 8} height={60 - (i % 2) * 14} rx="6" y2="0" fill={['#e8a99d', '#d6b49f', '#fdf6ef', '#b9c9b5'][(i + row) % 4]} transform={`translate(0 ${(i % 2) * 14})`}/>)}</g>)}
    <path d="M0 540 H1200 V700 H0 Z" fill="#a8133a" opacity=".8"/><path d="M0 540 H1200" stroke="#d45060" strokeWidth="12" opacity=".7"/>
  </>,
  interview: <>
    <g><rect x="140" y="110" width="420" height="320" rx="10" fill="url(#bd-sky)"/>{Array.from({ length: 11 }, (_, i) => <rect key={i} x="140" y={118 + i * 29} width="420" height="14" fill="#fdf6ef" opacity=".9"/>)}</g>
    <g><rect x="760" y="130" width="300" height="360" rx="8" fill="#c99d89"/>{[0, 1, 2].map(row => <g key={row}>{Array.from({ length: 8 }, (_, i) => <rect key={i} x={780 + i * 33} y={150 + row * 112} width="24" height={78 + (i % 3) * 8} transform={`translate(0 ${12 - (i % 3) * 8})`} fill={['#7a2335', '#d6b49f', '#fdf6ef', '#4a3550', '#b9c9b5'][(i + row) % 5]}/>)}<rect x="770" y={250 + row * 112} width="280" height="8" fill="#a77a66"/></g>)}</g>
    <path d="M0 610 Q600 575 1200 610 V700 H0 Z" fill="#8f5a4c"/>
  </>,
}

// Wallpapers from wallhaven.cc, shrunk to 1600px. Artists and links are in backdrops/CREDITS.md.
const PICTURES = import.meta.glob('./backdrops/*.jpg', { eager: true, import: 'default' })
const pictureFor = scene => PICTURES[`./backdrops/${scene}.jpg`]

export function Backdrop({ archetype, className = '' }) {
  const scene = sceneFor(archetype)
  const picture = pictureFor(scene)
  // The drawn scene stays underneath, so the stage is never blank while the picture loads or if it fails.
  return <div className={`scene-backdrop ${className}`.trim()} data-scene={scene} aria-hidden="true">
    <DrawnScene scene={scene}/>
    {picture && <img className="scene-picture" src={picture} alt="" decoding="async" onError={event => { event.currentTarget.hidden = true }}/>}
    <div className="scene-wash"/>
  </div>
}

function DrawnScene({ scene }) {
  return <svg className="scene-drawn" viewBox="0 0 1200 700" preserveAspectRatio="xMidYMid slice">
    <defs>
      <linearGradient id="bd-wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#f7ebe2"/><stop offset="1" stopColor="#efdccf"/></linearGradient>
      <linearGradient id="bd-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fde8da"/><stop offset="1" stopColor="#f5cbbd"/></linearGradient>
      <radialGradient id="bd-light" cx=".5" cy=".42" r=".55"><stop offset="0" stopColor="#fff6ec" stopOpacity=".85"/><stop offset="1" stopColor="#fff6ec" stopOpacity="0"/></radialGradient>
    </defs>
    <rect width="1200" height="700" fill="url(#bd-wall)"/>
    {SCENES[scene]}
    <rect width="1200" height="700" fill="url(#bd-light)"/>
  </svg>
}
