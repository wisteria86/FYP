import {FilesetResolver, PoseLandmarker} from '@mediapipe/tasks-vision'

let detector
let initialization
const initialize=()=>initialization??=(async()=>{
  const files=await FilesetResolver.forVisionTasks('/vision')
  detector=await PoseLandmarker.createFromOptions(files,{
    baseOptions:{modelAssetPath:'/vision/pose_landmarker_lite.task',delegate:'CPU'},
    runningMode:'VIDEO',numPoses:1,minPoseDetectionConfidence:.5,minPosePresenceConfidence:.5,
  })
})()
self.onmessage=async({data})=>{
  const {bitmap,timestamp}=data
  try{
    await initialize()
    const result=detector.detectForVideo(bitmap,timestamp)
    self.postMessage({landmarks:result.landmarks[0]||[]})
  }catch(error){self.postMessage({error:error.message})}
  finally{bitmap.close()}
}
