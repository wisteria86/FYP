class PCMCapture extends AudioWorkletProcessor {
  constructor(){super();this.frames=new Float32Array(4096);this.used=0
    this.port.onmessage=()=>{if(this.used)this.port.postMessage(this.frames.slice(0,this.used));this.used=0;this.port.postMessage({flushed:true})}
  }
  process(inputs){
    const samples=inputs[0]?.[0]
    if(samples)for(const value of samples){
      this.frames[this.used++]=value
      if(this.used===this.frames.length){this.port.postMessage(this.frames);this.frames=new Float32Array(4096);this.used=0}
    }
    return true
  }
}
registerProcessor('hikari-pcm-capture',PCMCapture)
