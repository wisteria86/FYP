// Whole-prefix snapshots keep WebM headers intact; never queue stale decoding.
export class IncrementalTranscriber {
  constructor(decode, onPartial=()=>{}) {
    this.decode=decode;this.onPartial=onPartial;this.pending=null;this.latest=null;this.closed=false
    this.controller=new AbortController()
  }
  push(blob, coveredUntil) {
    if(this.closed||this.pending)return false
    this.pending=this.decode(blob,this.controller.signal).then(result=>{
      if(!this.closed){this.latest={result,coveredUntil};if(result.text)this.onPartial(result.text)}
    }).catch(()=>{}).finally(()=>{this.pending=null})
    return true
  }
  async finish(lastSpeech) {
    if(this.pending)await this.pending
    if(this.closed)return null
    this.closed=true
    const snapshot=this.latest
    // Leave a small trailing margin so the final phoneme is not clipped.
    return snapshot&&snapshot.coveredUntil>=lastSpeech+150&&snapshot.result.text&&!snapshot.result.needs_retry
      ?snapshot.result:null
  }
  cancel(){this.closed=true;this.latest=null;this.controller.abort()}
}
