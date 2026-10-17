// Capture decisions must not depend on requestAnimationFrame: browsers pause it
// in hidden/occluded windows. Keep the graph rendered without microphone echo.
export function monitorMicrophone(context, source, onSamples, onError = () => {}) {
  const analyser = context.createAnalyser()
  analyser.fftSize = 1024
  analyser.smoothingTimeConstant = .35
  const silent = context.createGain()
  silent.gain.value = 0
  source.connect(analyser)
  analyser.connect(silent)
  silent.connect(context.destination)
  const samples = new Float32Array(analyser.fftSize)
  let stopped = false, resuming = false
  const timer = setInterval(() => {
    if (stopped) return
    if (context.state === 'closed') { onError(new Error('Microphone audio context closed. Rejoin the call.')); return }
    if (context.state === 'suspended' && !resuming) {
      resuming = true
      context.resume().catch(onError).finally(() => { resuming = false })
      return
    }
    try {
      analyser.getFloatTimeDomainData(samples)
      onSamples(Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length))
    } catch (error) { onError(error) }
  }, 50)
  return () => {
    if (stopped) return
    stopped = true
    clearInterval(timer)
    try { source.disconnect(analyser) } catch {}
    analyser.disconnect()
    silent.disconnect()
  }
}
