

export function SourceEvidence({sources=[]}) {
  return sources.length?<details className="source-evidence"><summary>Policy sources ({sources.length})</summary>{sources.map((source,index)=><blockquote key={`${source.document_id||source.name}-${index}`}><strong>{source.name}</strong><p>{source.excerpt||source.text}</p></blockquote>)}</details>:null
}
