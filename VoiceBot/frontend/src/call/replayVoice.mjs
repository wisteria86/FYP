// Replays one line in the same voice as the call, using the streaming speech endpoint.
// Falls back to the browser's own voice if the speech engine is not available.
export function replayVoice(text) {
  const controller = new AbortController()
  let context = null
  let stopped = false
  const done = (async () => {
    try {
      const response = await fetch('/api/tts/stream', {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: String(text).slice(0, 1000) }),
      })
      if (!response.ok || !response.body) throw new Error('voice unavailable')
      const AudioContext = window.AudioContext || window.webkitAudioContext
      context = new AudioContext()
      const reader = response.body.getReader(), decoder = new TextDecoder()
      let pending = '', tail = context.currentTime + 0.05, last = null
      for (;;) {
        const { value, done: finished } = await reader.read()
        if (finished || stopped) break
        pending += decoder.decode(value, { stream: true })
        const lines = pending.split('\n')
        pending = lines.pop()
        for (const line of lines) {
          if (!line.trim()) continue
          const message = JSON.parse(line)
          if (message.type !== 'audio' || !message.audio_b64) continue
          const bytes = Uint8Array.from(atob(message.audio_b64), char => char.charCodeAt(0))
          const buffer = await context.decodeAudioData(bytes.buffer.slice(0))
          const source = context.createBufferSource()
          source.buffer = buffer
          source.connect(context.destination)
          const at = Math.max(context.currentTime + 0.02, tail)
          source.start(at)
          tail = at + buffer.duration
          last = source
        }
      }
      if (last && !stopped) await new Promise(resolve => { last.onended = resolve })
    } catch (error) {
      if (stopped || error.name === 'AbortError') return
      if ('speechSynthesis' in window) {
        await new Promise(resolve => {
          const utterance = new SpeechSynthesisUtterance(text)
          utterance.onend = resolve
          utterance.onerror = resolve
          window.speechSynthesis.speak(utterance)
        })
      }
    } finally {
      context?.close?.().catch(() => {})
    }
  })()
  return {
    done,
    stop() { stopped = true; controller.abort(); context?.close?.().catch(() => {}); if ('speechSynthesis' in window) window.speechSynthesis.cancel() },
  }
}
