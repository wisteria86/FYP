// The game tape: the whole conversation turn by turn, marked with what the evidence shows,
// with any line replayable and any of your moments open to a fresh try.
import { useEffect, useRef, useState } from 'react'
import { api } from '../ui/core'
import { Icon } from '../ui/Icon'
import { useFeedback } from '../ui/feedback'
import { Portrait } from './Portrait'
import { replayVoice } from './replayVoice.mjs'

const REACTED = { pleased: 'was pleased', encouraging: 'encouraged you', curious: 'wanted to know more', considering: 'thought it over', doubtful: 'pushed back', firm: 'held firm', puzzled: 'was puzzled' }
const MARK_ICON = { strong: 'checkCircle', correction: 'trendUp', missed: 'target', note: 'info' }
const clock = seconds => `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`

export function GameTape({ sessionId, onPractiseMoment }) {
  const [tape, setTape] = useState(null), [error, setError] = useState(''), [playing, setPlaying] = useState(null), [branching, setBranching] = useState(null)
  const voice = useRef(null)
  const { toast } = useFeedback()
  useEffect(() => {
    let live = true
    api(`/sessions/${sessionId}/game-tape`).then(result => { if (live) setTape(result) }).catch(e => { if (live) setError(e.message) })
    return () => { live = false; voice.current?.stop() }
  }, [sessionId])
  if (error) return null
  if (!tape) return <section className="game-tape loading" aria-busy="true"><p className="eyebrow">GAME TAPE</p><div className="hk-skeleton"><i/><i/><i/></div></section>
  const play = async item => {
    voice.current?.stop()
    if (playing === item.id) { setPlaying(null); return }
    setPlaying(item.id)
    voice.current = replayVoice(item.text)
    await voice.current.done
    setPlaying(current => current === item.id ? null : current)
  }
  const tryAgain = async item => {
    setBranching(item.id)
    try {
      const branch = await api(`/sessions/${sessionId}/branch`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ turn_id: item.id }) })
      voice.current?.stop()
      onPractiseMoment?.(branch.id)
    } catch (e) { toast(e.message, { tone: 'error' }) } finally { setBranching(null) }
  }
  const marked = tape.turns.filter(item => item.marks?.length).length
  return <section className="game-tape" aria-labelledby="game-tape-title">
    <header>
      <div><p className="eyebrow">GAME TAPE</p><h2 id="game-tape-title">Your conversation, turn by turn</h2>
        <p>Replay any line. Pick one of your moments to try it again from there.</p></div>
      <div className="tape-stats">
        <span><b>{tape.turns.filter(item => item.role === 'user').length}</b> turns</span>
        <span><b>{marked}</b> marked</span>
        {tape.rewinds > 0 && <span title="Turns you took back are kept on record, outside this assessment"><b>{tape.rewinds}</b> {tape.rewinds === 1 ? 'retry' : 'retries'}</span>}
        <button className="h-soft tape-print" onClick={() => window.print()}><Icon name="download"/> Save as PDF</button>
      </div>
    </header>
    {tape.rewinds > 0 && <p className="tape-honest"><Icon name="info"/> You used “Take back” or replayed a moment in this lesson. That's good practice, so it counts on your path as practice rather than as a first try on your own.</p>}
    <ol className="tape-list">
      {tape.turns.map(item => <li key={item.id} className={`tape-turn ${item.role}`}>
        <span className="tape-time">{clock(item.at || 0)}</span>
        <span className="tape-face">{item.role === 'user' ? <Icon name="user"/> : <Portrait name={item.speaker} decorative size={36}/>}</span>
        <div className="tape-body">
          <header><strong>{item.speaker}</strong>{item.reaction && item.reaction !== 'neutral' && <em className={`tape-reaction ${item.reaction}`}>{item.reaction_by || 'They'} {item.reaction_text || REACTED[item.reaction] || 'reacted'}</em>}</header>
          <p>{item.text}</p>
          {item.marks?.length > 0 && <ul className="tape-marks">{item.marks.map((mark, index) => <li key={index} className={mark.kind}><Icon name={MARK_ICON[mark.kind] || 'info'}/><span>{mark.text}</span></li>)}</ul>}
          <div className="tape-actions">
            <button className="tape-link" onClick={() => play(item)} aria-pressed={playing === item.id}><Icon name={playing === item.id ? 'stop' : 'play'}/>{playing === item.id ? 'Stop' : 'Replay'}</button>
            {item.role === 'user' && item.replayable && <button className="tape-link strong" disabled={branching !== null} onClick={() => tryAgain(item)}><Icon name="undo"/>{branching === item.id ? 'Setting up…' : 'Try this moment again'}</button>}
          </div>
        </div>
      </li>)}
    </ol>
    {tape.expert.length > 0 && <div className="tape-expert">
      <h3>What an expert might have said</h3>
      {tape.expert.map(item => <article key={item.objective}><small>{item.objective}</small><blockquote>“{item.model}”</blockquote>{item.lesson && <p>{item.lesson}</p>}
        <button className="tape-link" onClick={() => play({ id: `expert-${item.objective}`, text: item.model })}><Icon name={playing === `expert-${item.objective}` ? 'stop' : 'play'}/>{playing === `expert-${item.objective}` ? 'Stop' : 'Hear it'}</button></article>)}
    </div>}
  </section>
}
