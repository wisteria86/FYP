"""Transparent prototype rubrics: observations, never unsupported mastery claims.

Pattern observations are not clinically/educationally calibrated measurements.
They provide reproducible evidence and conservative fallback when AI is offline.
"""
import re
import math

PATTERNS = {
 'anchoring':[r'\b(?:offer|budget|price|start|propose)\b',r'\b\d+\b'],
 'counteroffers':[r'\b(?:instead|counter|offer|could|propose)\b'],
 'concessions':[r'\b(?:if|provided|exchange|concession|in return)\b'],
 'objection handling':[r'\b(?:understand|concern|because|alternative)\b'],
 'subject clarity':[r'\bsubject\b'], 'tone':[r'\b(?:dear|hello|please|thank|regards)\b'],
 'requested action':[r'\b(?:please|could|request|confirm|reply|send)\b'],
 'clarity': [r'\bbecause\b',r'\b(?:first|next|will|result)\b'],
 'professionalism': [r'\b(?:please|thank|appreciate|understand)\b',r'\b(?:can|could|would|will)\b'],
 'conciseness': [r'\b(?:in short|main|priority|next|will)\b'],
 'acknowledgement': [r'\b(?:understand|hear|appreciate|sorry|concern)\b'],
 'clarifying questions': [r'\b(?:could you|can you|which|what|when|how)\b'],
 'summarising': [r'\b(?:so you|to confirm|if i understand|in other words|summary)\b'],
 'empathy': [r'\b(?:understand|appreciate|sorry|frustrat|concern)'],
 'de-escalation': [r'\b(?:calm|together|understand|fair|let us|let.s)\b'],
 'problem solving': [r'\b(?:could|option|solution|next|will|propose)\b'],
 'discovery': [r'\b(?:priority|important|need|why|what|which)\b'],
 'trade-offs': [r'\b(?:if|instead|reduce|scope|trade|in exchange|provided)\b'],
 'closing': [r'\b(?:agree|confirm|deal|next|will|deadline)\b'],
 'relevance': [r'\b(?:because|for example|experience|role|task)\b'],
 'STAR evidence': [r'\b(?:situation|task|when|project)\b',r'\b(?:i did|i led|i created|i worked|i developed)\b',r'\b(?:result|improved|achieved|percent|completed)\b'],
 'confidence': [r'\b(?:i can|i will|i have|i achieved|i recommend)\b'],
 'structure': [r'\b(?:first|second|finally|next|in conclusion)\b'],
 'audience focus': [r'\b(?:you|your|audience|question|benefit)\b'],
 'narrative': [r'\b(?:when|before|then|after|finally)\b'],
 'evidence': [r'\b(?:because|data|evidence|example|result|measured)\b'],
 'impact': [r'\b(?:result|impact|improved|reduced|saved|achieved)\b'],
 'analysis': [r'\b(?:because|compare|assumption|alternative|risk)\b'],
 'judgement': [r'\b(?:recommend|decide|choose|therefore|best)\b'],
 'verification': [r'\b(?:verify|check|source|confirm|official|independent)\b'],
 'privacy': [r'\b(?:private|personal|confidential|consent|sensitive|redact)\b'],
 'transparency': [r'\b(?:disclose|explain|ai generated|limitations|uncertain)\b'],
 'risk recognition': [r'\b(?:suspicious|phishing|urgent|password|manipulation|risk)\b'],
 'reporting': [r'\b(?:report|security|manager|incident|escalate)\b'],
}
OBJECTIVES = {
 'email-professionalism':['subject clarity','tone','requested action'],
 'communication':['clarity','impact','closing'], 'active-listening':['acknowledgement','clarifying questions','summarising'],
 'conflict-resolution':['de-escalation','empathy','problem solving'], 'negotiation':['discovery','trade-offs','closing'],
 'interviews':['relevance','STAR evidence','confidence'], 'presentations':['structure','evidence','audience focus'],
 'storytelling':['narrative','evidence','impact'], 'critical-thinking':['analysis','evidence','judgement'],
 'ai-literacy':['verification','privacy','transparency'], 'social-engineering':['risk recognition','verification','reporting'],
}

def distinct_turns(turns):
    seen=set(); result=[]
    for text in turns:
        key=' '.join(re.findall(r"[a-z]+(?:'[a-z]+)?",text.lower()))
        if len(key.split())>=2 and key not in seen:
            seen.add(key); result.append(text)
    return result

def workplace_targets(skill_id, objectives):
    keys=OBJECTIVES.get(skill_id,[])
    result=[]
    for index,objective in enumerate(objectives):
        key=keys[index] if index<len(keys) else ''
        patterns=PATTERNS.get(key,[])
        if not patterns:
            words=[w for w in re.findall(r'[a-z]+',objective.lower()) if len(w)>4]
            patterns=[r'\b'+re.escape(w)+r'\w*\b' for w in words[:3]]
        result.append({'name':objective,'patterns':patterns,'required_hits':min(2,len(patterns)) or 1})
    return result

def observe(target, turns):
    patterns=target.get('patterns',[])
    matched=[pattern for pattern in patterns if any(re.search(pattern,text,re.I) or
             re.search(pattern.replace(r'[^?]*\?',''),text,re.I) for text in turns)]
    required=target.get('required_hits',1)
    evidence=[text[:240] for text in turns if any(re.search(p,text,re.I) or re.search(p.replace(r'[^?]*\?',''),text,re.I) for p in patterns)]
    return {'name':target['name'],'met':len(matched)>=required,'evidence':evidence[:2]}

def valid_scores(values, allowed):
    return {key:round(float(value),1) for key,value in values.items() if key in allowed
            and isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and 0<=value<=100}

def fallback_scores(session, turns, subskills, progress):
    turns=distinct_turns(turns)
    criteria=progress['criteria']; ratio=sum(c['met'] for c in criteria)/max(1,len(criteria))
    scores={}; observations={}
    if session.get('training_language')=='English':
        vocabulary=(session.get('learning_design') or {}).get('vocabulary',[])
        text=' '.join(turns).lower()
        used=sum(bool(re.search(r'\b'+re.escape(w)+r'\b',text)) for w in vocabulary)
        scores={'comprehension':round(ratio*80,1),'vocabulary':round(used/max(1,len(vocabulary))*80,1),
                'practice_completion':round(min(1,len(turns)/max(1,progress['minimum_turns']))*80,1)}
        observations={key:'Conservative transcript-only estimate; no pronunciation or calibrated language-level claim.' for key in scores}
    else:
        for name in subskills:
            patterns=PATTERNS.get(name,[])
            if not patterns: continue
            observation=observe({'name':name,'patterns':patterns,'required_hits':len(patterns)},turns)
            hits=sum(any(re.search(p,t,re.I) for t in turns) for p in patterns)
            key=name.lower().replace(' ','_')
            scores[key]=round(hits/len(patterns)*80,1)
            observations[key]='Observed: '+' / '.join(observation['evidence']) if observation['evidence'] else 'No supporting learner evidence yet.'
        if not scores: scores={'objective_demonstration':round(ratio*80,1)}
    if not turns: scores={key:0 for key in scores}
    return scores,observations
