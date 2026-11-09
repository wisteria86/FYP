import {startSilero} from './sileroVad.mjs'
import {SpeechInterruptionGate} from './conversationPlayback.mjs'

export async function startBargeIn({constraints,isPlaying,onInterrupt,onUtterance,onUnavailable,startVad=startSilero,now=()=>performance.now()}){
  const stream=await navigator.mediaDevices.getUserMedia({audio:{...constraints,echoCancellation:true}})
  const context=new AudioContext()
  const gate=new SpeechInterruptionGate()
  const echoCancelled=stream.getAudioTracks()[0]?.getSettings().echoCancellation===true
  if(!echoCancelled){stream.getTracks().forEach(t=>t.stop());await context.close();onUnavailable('Automatic interruption needs browser echo cancellation. Use Interrupt.');return {stop(){}}}
  let recorder,chunks=[],capturing=false,disposed=false,started=0,ready=Promise.resolve()
  const record=()=>{
    recorder=new MediaRecorder(stream)
    chunks=[]
    started=now()
    // Never drop the container header: isolated later WebM chunks are not decodable.
    // Rotate quiet buffers; retain the current playback plus interrupted utterance.
    recorder.ondataavailable=event=>{
      if(event.data.size)chunks.push(event.data)
      const elapsed=now()-started
      if(recorder.state==='recording'&&((!capturing&&((!isPlaying()&&elapsed>1000)||elapsed>30000))||elapsed>60000))recorder.stop()
    }
    recorder.onstop=async()=>{
      if(disposed)return
      if(capturing){const blob=new Blob(chunks,{type:recorder.mimeType});capturing=false;try{await ready;if(!disposed)await onUtterance(blob,(now()-started)/1000)}catch(error){onUnavailable(error.message)}}
      if(!disposed)record()
    }
    recorder.start(100)
  }
  record()
  let vad
  try{vad=await startVad(context,stream,{
    onProbability(probability){if(!capturing&&recorder.state==='recording'&&gate.update(probability,now(),isPlaying(),echoCancelled)){capturing=true;ready=Promise.resolve(onInterrupt())}},
    onSpeech(){},onEnd(){if(capturing&&recorder.state==='recording')recorder.stop()}
  })}catch(error){disposed=true;recorder.stop();stream.getTracks().forEach(t=>t.stop());await context.close();throw error}
  return {stop(){disposed=true;vad.stop();if(recorder.state==='recording')recorder.stop();stream.getTracks().forEach(t=>t.stop());context.close()}}
}
