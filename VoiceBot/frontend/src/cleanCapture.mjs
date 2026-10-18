// Recording, live recognition, and activity detection share the cleaned signal.
export function connectCleanCapture(context,stream,makeDenoiser){
  const raw=context.createMediaStreamSource(stream)
  const denoiser=makeDenoiser()
  const destination=context.createMediaStreamDestination()
  // The RNNoise processor produces one channel. Do not record a stereo
  // destination with an unused channel and then downmix it on the backend.
  destination.channelCount=1
  destination.channelCountMode='explicit' 
  raw.connect(denoiser)
  denoiser.connect(destination)
  let destroyed=false
  return {source:denoiser,stream:destination.stream,destroy(){
    if(destroyed)return
    destroyed=true
    raw.disconnect();denoiser.disconnect();denoiser.destroy()
    destination.stream.getTracks().forEach(track=>track.stop())
  }}
}
