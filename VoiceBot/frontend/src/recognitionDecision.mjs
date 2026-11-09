export function finalRecognitionForm(form,preferences,sessionId,live){
  form.append('session_id',sessionId)
  if(preferences.accurateFinal){
    form.append('final_pass','true')
    form.append('original_text',live?.text||'')
  }
  return !preferences.accurateFinal&&live?.text?.trim()?live:null
}
export function recognitionProvenance(result){
  return {source:'speech',unreliable:Boolean(result.needs_retry),confidence:result.confidence,
    original_text:result.original_text,final_pass:result.final_pass,disagreement:result.disagreement}
}
export function reviewedRecognition(result){
  return {...recognitionProvenance(result),unreliable:false,confirmed_by_learner:true,unreviewed_text:result.text}
}
