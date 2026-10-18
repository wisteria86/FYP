export function frameLevels(samples){
  let power=0,peak=0,nearClipped=0
  for(const sample of samples){const absolute=Math.abs(sample);power+=sample*sample;peak=Math.max(peak,absolute);if(absolute>=.99)nearClipped++}
  return {samples:samples.length,power,peak,nearClipped,rms:Math.sqrt(power/Math.max(1,samples.length))}
}
export function accumulateLevels(total,frame){
  total.samples+=frame.samples;total.power+=frame.power;total.peak=Math.max(total.peak,frame.peak);total.nearClipped+=frame.nearClipped
  return total
}
export function levelSummary(total){
  return {rms:Math.sqrt(total.power/Math.max(1,total.samples)),peak:total.peak,nearClippedPercent:100*total.nearClipped/Math.max(1,total.samples)}
}
export function emptyLevels(){return {samples:0,power:0,peak:0,nearClipped:0}}
export function createInputLevel(context,stream,db){
  if(!Number.isFinite(db)||db < -24||db > 6)throw new Error('Input gain must be between -24 and +6 dB')
  const source=context.createMediaStreamSource(stream),gain=context.createGain(),destination=context.createMediaStreamDestination()
  destination.channelCount=1;destination.channelCountMode='explicit'
  gain.gain.value=10**(db/20)
  source.connect(gain);gain.connect(destination)
  let destroyed=false
  return {stream:destination.stream,destroy(){if(destroyed)return;destroyed=true;source.disconnect();gain.disconnect();destination.stream.getTracks().forEach(track=>track.stop())}}
}
