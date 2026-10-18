export class CaptureClock {
  constructor(now){this.started=now;this.pausedAt=null;this.pausedMs=0}
  pause(now){if(this.pausedAt===null)this.pausedAt=now}
  resume(now){if(this.pausedAt!==null){this.pausedMs+=now-this.pausedAt;this.pausedAt=null}}
  elapsed(now){return Math.max(0,(this.pausedAt??now)-this.started-this.pausedMs)}
}
