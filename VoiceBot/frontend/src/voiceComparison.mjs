export const captureModes=[
  {id:'browser',name:'Browser suppression only',browser:true,rnnoise:false},
  {id:'rnnoise',name:'RNNoise only',browser:false,rnnoise:true},
  {id:'none',name:'No noise suppression',browser:false,rnnoise:false},
]
export function captureMode(id){
  const mode=captureModes.find(item=>item.id===id)
  if(!mode)throw new Error('Unknown capture mode')
  return mode
}
export function compareWords(expected,actual){
  const words=value=>(value.toLowerCase().match(/[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu)||[]).map(word=>word.replaceAll('’',"'"))
  const reference=words(expected),heard=words(actual)
  if(!reference.length)return null
  let row=Array.from({length:heard.length+1},(_,index)=>index)
  for(let i=1;i<=reference.length;i++){
    const next=[i]
    for(let j=1;j<=heard.length;j++)next[j]=Math.min(next[j-1]+1,row[j]+1,row[j-1]+(reference[i-1]===heard[j-1]?0:1))
    row=next
  }
  return {errors:row[heard.length],words:reference.length,wer:Math.round(row[heard.length]/reference.length*100)}
}
