// Avoid browser gain boosting quiet background hiss. Browsers may ignore
// unsupported constraints; log getSettings() on the actual capture track.
export function microphoneConstraints(deviceId='',{noiseSuppression=true}={}){
  return {echoCancellation:true,noiseSuppression,autoGainControl:false,
    channelCount:{ideal:1},...(deviceId?{deviceId:{exact:deviceId}}:{})}
}

export async function listMicrophones(mediaDevices,requestAccess=false){
  if(!mediaDevices?.enumerateDevices)throw new Error('Microphone access requires localhost or HTTPS and a supported browser.')
  let stream
  try{
    if(requestAccess)stream=await mediaDevices.getUserMedia({audio:microphoneConstraints()})
    const devices=await mediaDevices.enumerateDevices()
    const seen=new Set()
    return devices.filter(device=>{
      if(device.kind!=='audioinput'||!device.deviceId||seen.has(device.deviceId))return false
      seen.add(device.deviceId);return true
    })
  }finally{stream?.getTracks().forEach(track=>track.stop())}
}
