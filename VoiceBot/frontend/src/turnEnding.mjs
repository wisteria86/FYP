export const turnDetection={positiveThreshold:.35,negativeThreshold:.15,silenceMs:1500}
// Lesson answer targets are coaching guidance, not recording cutoffs.
// Stay below the speech transport's 90-second input bound.
export function captureLimitReason(elapsed,speechSeen,automatic){
  if(elapsed>=80000)return 'capture_limit'
  if(automatic&&!speechSeen&&elapsed>=20000)return 'no_speech'
  return null
}
