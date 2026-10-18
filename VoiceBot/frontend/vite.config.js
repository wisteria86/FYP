import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import {readFileSync} from 'node:fs'
import {fileURLToPath} from 'node:url'

function localSileroAssets(command){
  const locations=new Map([
    ...['silero_vad_v5.onnx','vad.worklet.bundle.min.js'].map(name=>[name,`@ricky0123/vad-web/dist/${name}`]),
    ...['ort-wasm-simd-threaded.wasm','ort-wasm-simd-threaded.mjs'].map(name=>[name,`onnxruntime-web/dist/${name}`]),
  ].map(([name,path])=>[name,fileURLToPath(new URL(`./node_modules/${path}`,import.meta.url))]))
  return {name:'local-silero-assets',
    buildStart(){if(command==='build')for(const [name,path] of locations)this.emitFile({type:'asset',fileName:`vad/${name}`,source:readFileSync(path)})},
    configureServer(server){server.middlewares.use((req,res,next)=>{
      const name=req.url?.split('?')[0]?.replace(/^\/vad\//,'')
      if(!req.url?.startsWith('/vad/')||!locations.has(name))return next()
      res.setHeader('Content-Type',name.endsWith('.wasm')?'application/wasm':name.endsWith('.onnx')?'application/octet-stream':'application/javascript')
      res.end(readFileSync(locations.get(name)))
    })},
  }
}

export default defineConfig(({command})=>({
  plugins: [react(),localSileroAssets(command)],
  server: {
    port: 5173,
    proxy: {
      // Forward /api/* to the FastAPI backend so CORS isn't an issue in dev
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
}))
