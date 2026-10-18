// Energy gate, not a speech classifier. Track quiet input without learning a
// learner's first loud words as noise; use speech contrast to reject trailing hum.
export class SpeechGate {
  constructor(){this.floor=.0003;this.peak=0;this.aboveSince=null}
  update(rms,now){
    const base=Math.max(.0006,this.floor*2.5)
    if(rms<base)this.floor=this.floor*.95+rms*.05
    this.peak*=.98
    const threshold=Math.max(.0006,this.floor*2.5,this.peak*.18)
    const above=rms>threshold
    if(above){if(this.aboveSince===null)this.aboveSince=now}
    else this.aboveSince=null
    const speech=above&&now-this.aboveSince>=100
    if(speech)this.peak=Math.max(rms,this.peak)
    return {threshold,noiseFloor:this.floor,speech}
  }
}
