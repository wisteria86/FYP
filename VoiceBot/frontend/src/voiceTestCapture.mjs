export function record(stream){
  const mime=['audio/webm;codecs=opus','audio/webm','audio/mp4'].find(value=>MediaRecorder.isTypeSupported(value))
  const recorder=mime?new MediaRecorder(stream,{mimeType:mime}):new MediaRecorder(stream)
  const parts=[]
  const done=new Promise((resolve,reject)=>{
    recorder.ondataavailable=event=>{if(event.data.size)parts.push(event.data)}
    recorder.onstop=()=>resolve(new Blob(parts,{type:recorder.mimeType}))
    recorder.onerror=event=>reject(event.error||new Error('Recording failed'))
  })
  // Observe errors immediately, even if recording fails before Stop is clicked.
  done.catch(()=>{})
  return {recorder,done}
}
export function release(run){
  clearTimeout(run.timer);run.stopMonitor?.()
  run.recordings?.forEach(item=>{if(item.recorder.state!=='inactive')item.recorder.stop()})
  run.clean?.destroy();run.levelGraph?.destroy();run.stream?.getTracks().forEach(track=>track.stop())
  run.context?.close().catch(()=>{})
}

