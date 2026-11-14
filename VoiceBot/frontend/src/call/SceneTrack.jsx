// A slim live track across the top of the call: the scene's steps, and your objectives ticking off as you meet them.
import { useEffect, useRef, useState } from 'react'
import { Icon } from '../ui/Icon'

const remember = (key, fallback) => { try { return localStorage.getItem(key) ?? fallback } catch { return fallback } }
const store = (key, value) => { try { localStorage.setItem(key, value) } catch { /* private window */ } }

export function SceneTrack({ runtime }) {
  const definition = runtime?.definition || {}
  const objectives = Object.fromEntries((definition.objectives || []).map(item => [item.id, item.description]))
  const met = new Set((runtime?.progress?.criteria || []).filter(item => item.met).map(item => item.id))
  const beats = (definition.beats || []).filter(beat => beat.objectives?.length)
  const current = Math.min(runtime?.scene?.beat ?? 0, Math.max(beats.length - 1, 0))
  const finished = !!runtime?.scene?.finished || !!runtime?.completed
  const [collapsed, setCollapsed] = useState(() => remember('hikari-track-collapsed', '0') === '1')
  const [taskOpen, setTaskOpen] = useState(false)
  const [fresh, setFresh] = useState(() => new Set())
  const seen = useRef(null)

  // A small light-burst when an objective is newly met (not for ones already met when the call opened).
  useEffect(() => {
    if (seen.current === null) { seen.current = new Set(met); return }
    const added = [...met].filter(id => !seen.current.has(id))
    seen.current = new Set(met)
    if (!added.length) return
    setFresh(new Set(added))
    const timer = setTimeout(() => setFresh(new Set()), 1800)
    return () => clearTimeout(timer)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [[...met].sort().join('|')])

  const toggle = () => { const next = !collapsed; setCollapsed(next); store('hikari-track-collapsed', next ? '1' : '0') }
  const goals = beats.length ? beats[current].objectives : (definition.objectives || []).map(item => item.id)
  const total = (definition.objectives || []).length
  const brief = definition.brief

  return <section className={`scene-track ${collapsed ? 'collapsed' : ''}`} aria-label="Lesson progress">
    <div className="track-row">
      {brief && <button className="track-task" aria-expanded={taskOpen} aria-controls="track-brief" onClick={() => setTaskOpen(value => !value)}><Icon name="target"/>Your task</button>}
      {beats.length > 1 && <ol className="track-steps">
        {beats.map((beat, index) => {
          const done = finished || index < current
          const label = objectives[beat.objectives[0]] || `Step ${index + 1}`
          return <li key={beat.id} className={done ? 'done' : index === current ? 'current' : 'next'} aria-current={!done && index === current ? 'step' : undefined} title={label}>
            <span className="track-dot">{done ? <Icon name="check"/> : index + 1}</span><span className="track-label">{label}</span>
          </li>
        })}
      </ol>}
      <span className="track-count" aria-live="polite">{met.size}/{total} objectives</span>
      <button className="track-toggle" onClick={toggle} aria-expanded={!collapsed} aria-label={collapsed ? 'Show lesson progress' : 'Hide lesson progress'}><Icon name="chevronDown"/></button>
    </div>
    {!collapsed && goals.length > 0 && <ul className="track-goals">
      {goals.map(id => <li key={id} className={`${met.has(id) ? 'met' : ''} ${fresh.has(id) ? 'just-met' : ''}`}>
        <span className="goal-mark">{met.has(id) ? <Icon name="check"/> : null}</span>{objectives[id] || id}
      </li>)}
    </ul>}
    {taskOpen && brief && <div className="track-brief" id="track-brief">
      <p><strong>{brief.you_are}</strong> {brief.situation}</p><p>{brief.task}</p><p><strong>You're done when:</strong> {brief.done_looks_like}</p>
    </div>}
  </section>
}
