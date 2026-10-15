"""Normalize model output before it can reach display or speech providers."""
import re


def public_reply(text):
    value = (text or '').strip()
    value = re.sub(r'<think>.*?</think>', '', value, flags=re.IGNORECASE | re.DOTALL).strip()
    if re.search(r'<think\b', value, flags=re.IGNORECASE):
        return ''
    return re.sub(r'</?think>', '', value, flags=re.IGNORECASE).strip()
def redundant_correction(reply, learner_text):
    """Reject corrections that merely quote the learner's already-correct words."""
    import re
    normalize=lambda value:' '.join(re.findall(r"[a-z]+(?:'[a-z]+)?",value.lower()))
    learner=normalize(learner_text)
    corrections=re.findall(r'a more natural way is:\s*["“]([^"”]+)["”]',reply,re.I)
    return any(normalize(correction) and normalize(correction) in learner for correction in corrections)

