"""Bounded vocabulary and acoustic-decoder disagreement, never LLM rewriting."""
import re
from intelligence.conversation_direction import numeric_text


def session_vocabulary(definition):
    names=[p['name'] for p in definition.get('participants',[]) if p.get('kind','ai')=='ai']
    text=' '.join(fact for fact in definition.get('facts',[]) if not re.search(
        r'\b(no established|not been confirmed|do not|never|unknown)\b',fact,re.I))
    stop=set('this that with from have will would could should their there they them when where what which because about before after been were does into than then these those your only must agreed confirmed'.split())
    words=[w for w in re.findall(r'\b[a-zA-Z][a-zA-Z-]{3,24}\b',text) if w.casefold() not in stop]
    return ', '.join(dict.fromkeys(names+words))[:500]


def compare_transcripts(original, result):
    final=result.get('text','').strip()
    a=re.findall(r"[\w']+",original.casefold())
    b=re.findall(r"[\w']+",final.casefold())
    previous=list(range(len(b)+1))
    for i,word in enumerate(a,1):
        row=[i]
        for j,other in enumerate(b,1):
            row.append(min(row[-1]+1,previous[j]+1,previous[j-1]+(word!=other)))
        previous=row
    distance=previous[-1]
    # Confidence is decoder likelihood, not a calibrated probability of correctness.
    low=result.get('confidence') is not None and result['confidence']<.35
    material=bool(a and b and distance>=3 and distance/max(len(a),len(b))>.45)
    numbers=lambda text:re.findall(r'\b\d+(?:\.\d+)?\b',numeric_text(text))
    number_change=bool(a and b and numbers(original)!=numbers(final))
    negations=lambda words:{w for w in words if w in {'not','never','no','cannot',"don't","can't","won't","isn't","didn't"}}
    negation_change=bool(a and b and negations(a)!=negations(b))
    uncertain=low or material or number_change or negation_change or not final
    return {**result,'text':final,'original_text':original,
            'final_pass':'whisper','needs_retry':uncertain,
            'disagreement':round(distance/max(1,len(a),len(b)),3) if a else None,
            'retry_reason':'The recognizers disagree or the recording is uncertain. Check and edit the transcript before sending.' if uncertain else None}
