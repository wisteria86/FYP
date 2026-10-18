import {turnDetection} from './turnEnding.mjs'
// Use the existing processed stream and context; VAD must not acquire another
// microphone, stop shared tracks, or send its segmented audio to recognition.
export function sileroOptions(context,stream,callbacks){
  return {model:'v5',audioContext:context,startOnLoad:false,processorType:'AudioWorklet',
    baseAssetPath:'/vad/',onnxWASMBasePath:'/vad/',
    positiveSpeechThreshold:turnDetection.positiveThreshold,negativeSpeechThreshold:turnDetection.negativeThreshold,
    redemptionMs:turnDetection.silenceMs,preSpeechPadMs:400,minSpeechMs:200,submitUserSpeechOnPause:false,
    getStream:async()=>stream,pauseStream:async()=>{},resumeStream:async()=>stream,
    ortConfig:ort=>{ort.env.wasm.numThreads=1;ort.env.wasm.proxy=false},
    onFrameProcessed:probabilities=>callbacks.onProbability(probabilities.isSpeech),
    onSpeechRealStart:()=>callbacks.onSpeech(),onSpeechEnd:()=>callbacks.onEnd()}
}
