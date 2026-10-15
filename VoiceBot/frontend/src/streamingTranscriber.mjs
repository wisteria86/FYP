export class StreamingTranscriber {
  constructor(sessionId,onPartial=()=>{}){
    this.sessionId=sessionId;this.onPartial=onPartial;this.closed=false;this.ready=false
    this.controller=new AbortController();this.result=null
  }
  async start(context,source){
    try{
      const url=new URL(`/api/sessions/${this.sessionId}/speech-stream`,window.location.href)
      url.protocol=url.protocol==='https:'?'wss:':'ws:'
      this.socket=new WebSocket(url)
      const connected=new Promise((resolve,reject)=>{
        const timeout=setTimeout(()=>reject(new Error('Streaming connection timed out')),3000)
        this.socket.onopen=()=>this.socket.send(JSON.stringify({sample_rate:context.sampleRate}))
        this.socket.onerror=()=>{clearTimeout(timeout);reject(new Error('Streaming connection failed'))}
        this.socket.onclose=()=>{clearTimeout(timeout);resolve(false);this.ready=false;this.complete?.(null)}
        this.socket.onmessage=({data})=>{
          if(this.closed)return
          const event=JSON.parse(data)
          if(event.type==='ready'){clearTimeout(timeout);this.ready=true;resolve(true)}
          if(event.type==='partial')this.onPartial(event.text)
          if(event.type==='final'){this.result=event;this.complete?.(event)}
          if(event.type==='error'){clearTimeout(timeout);resolve(false);this.ready=false;this.complete?.(null)}
        }
      })
      if(!await connected){this.cancel();return false}
      await context.audioWorklet.addModule(new URL('./pcmCapture.worklet.js',import.meta.url))
      if(this.closed)return false
      this.node=new AudioWorkletNode(context,'hikari-pcm-capture')
      this.source=source;this.gain=context.createGain();this.gain.gain.value=0
      source.connect(this.node);this.node.connect(this.gain);this.gain.connect(context.destination)
      this.node.port.onmessage=({data})=>{
        if(data.flushed){this.flushed?.();return}
        if(!this.closed&&this.socket.readyState===WebSocket.OPEN&&this.ready){
          if(this.socket.bufferedAmount>256000){this.cancel();return}
          this.socket.send(data.buffer)
        }
      }
      return true
    }catch{this.cancel();return false}
  }
  async finish(){
    if(this.closed||!this.ready)return null
    try{
      await new Promise(resolve=>{this.flushed=resolve;this.node.port.postMessage('flush');setTimeout(resolve,150)})
      this.disconnect()
      if(this.closed||!this.ready||this.socket.readyState!==WebSocket.OPEN)return null
      const result=await new Promise(resolve=>{
        this.complete=resolve
        this.socket.send(JSON.stringify({type:'finish'}))
        this.finalTimeout=setTimeout(()=>resolve(null),10000)
      })
      return result
    }catch{return null}finally{this.cancel()}
  }
  disconnect(){
    try{if(this.node)this.source.disconnect(this.node)}catch{}
    this.node?.disconnect();this.gain?.disconnect()
  }
  cancel(){
    this.closed=true;this.ready=false;clearTimeout(this.finalTimeout)
    this.disconnect();this.socket?.close();this.complete?.(null)
  }
}
