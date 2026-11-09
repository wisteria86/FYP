// Generation guards prevent stale network chunks from becoming audible after interruption.
export class PlaybackGeneration {
  constructor(){this.value=0;this.timers=new Set()}
  capture(){return this.value}
  current(value){return value===this.value}
  cancel(){this.value+=1;for(const timer of this.timers)clearTimeout(timer);this.timers.clear()}
  after(delay,callback){const generation=this.value;const timer=setTimeout(()=>{this.timers.delete(timer);if(this.current(generation))callback()},Math.max(0,delay));this.timers.add(timer);return timer}
}

export class SpeechInterruptionGate {
  constructor(){this.started=null;this.fired=false}
  update(probability,now,playing,echoCancelled){
    if(!playing||!echoCancelled||probability<.92){this.started=null;this.fired=false;return false}
    if(this.started===null)this.started=now
    if(!this.fired&&now-this.started>=350){this.fired=true;return true}
    return false
  }
}
