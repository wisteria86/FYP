import { useId, useState } from 'react'

const W = 640, H = 240, LEFT = 40, RIGHT = 16, TOP = 16, BOTTOM = 34
const plotW = W - LEFT - RIGHT, plotH = H - TOP - BOTTOM
const day = value => new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })

// Score per completed lesson over time, with dated axis, gridlines and a readable value for the focused point.
export function ProgressChart({ points = [] }) {
  const gradient = useId().replace(/:/g, '')
  const [active, setActive] = useState(null)
  const data = points.filter(item => item.overall != null).map(item => ({ value: Math.max(0, Math.min(100, Number(item.overall))), date: item.completed_at }))
  if (!data.length) return <div className="h-chart-empty hk-chart-empty">
    <svg viewBox="0 0 120 60" aria-hidden="true"><path d="M8 50 L36 34 L58 40 L84 18 L112 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="2 7"/><circle cx="84" cy="18" r="5" fill="currentColor"/></svg>
    <p>Your chart starts after your first completed lesson.</p>
  </div>
  const x = index => LEFT + (data.length === 1 ? plotW / 2 : index * plotW / (data.length - 1))
  const y = value => TOP + plotH - value / 100 * plotH
  const line = data.map((item, index) => `${index ? 'L' : 'M'}${x(index).toFixed(1)} ${y(item.value).toFixed(1)}`).join(' ')
  const area = `${line} L${x(data.length - 1).toFixed(1)} ${TOP + plotH} L${x(0).toFixed(1)} ${TOP + plotH} Z`
  const step = Math.max(1, Math.ceil(data.length / 6))
  const ticks = data.map((item, index) => ({ ...item, index })).filter(item => item.index % step === 0 || item.index === data.length - 1)
  const shown = active == null ? data.length - 1 : active
  const latest = data[shown]
  const change = data.length > 1 ? Math.round(data[data.length - 1].value - data[0].value) : null
  return <figure className="hk-chart">
    <figcaption>
      <span><b>{Math.round(latest.value)}%</b> {active == null ? 'latest' : day(latest.date)}</span>
      {change != null && <span className={change >= 0 ? 'up' : 'down'}>{change >= 0 ? '+' : ''}{change} points since your first lesson</span>}
    </figcaption>
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Scores for ${data.length} completed ${data.length === 1 ? 'lesson' : 'lessons'}, latest ${Math.round(data[data.length - 1].value)} percent`} onMouseLeave={() => setActive(null)}>
      <defs><linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#d45060" stopOpacity=".28"/><stop offset="1" stopColor="#d45060" stopOpacity="0"/></linearGradient></defs>
      {[0, 25, 50, 75, 100].map(value => <g key={value} className="grid"><line x1={LEFT} x2={W - RIGHT} y1={y(value)} y2={y(value)}/><text x={LEFT - 8} y={y(value) + 4} textAnchor="end">{value}</text></g>)}
      {ticks.map(item => <text key={item.index} className="tick" x={x(item.index)} y={H - 10} textAnchor="middle">{day(item.date)}</text>)}
      <path d={area} fill={`url(#${gradient})`} className="area"/>
      <path d={line} className="line"/>
      {active != null && <line className="guide" x1={x(active)} x2={x(active)} y1={TOP} y2={TOP + plotH}/>}
      {data.map((item, index) => <circle key={index} className={index === shown ? 'point on' : 'point'} cx={x(index)} cy={y(item.value)} r={index === shown ? 6 : 4.5}
        tabIndex={0} onMouseEnter={() => setActive(index)} onFocus={() => setActive(index)} onBlur={() => setActive(null)}>
        <title>{`${day(item.date)}: ${Math.round(item.value)}%`}</title>
      </circle>)}
    </svg>
  </figure>
}
