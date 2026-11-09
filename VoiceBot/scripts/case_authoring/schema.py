"""Compact authoring format for case packs.

Each lesson has its own people, facts, prompts and teaching notes. The builder only
fills the repetitive JSON shape, one stage per objective.
"""


def A(name, role, rel, want, attitude, speech, tactics, topics, need=''):
    return dict(name=name, role=role, rel=rel, want=want, attitude=attitude, speech=speech, tactics=tactics, topics=topics, need=need)


def O(goal, evidence, alt, opp, orient, good, miss, micro, model, step, sub, desc=None, signal=None, second=None, min_turns=1, driver=1):
    return dict(goal=goal, evidence=evidence, alt=alt, opp=opp, orient=orient, good=good, miss=miss, micro=micro, model=model, step=step, sub=sub,
                desc=desc, signal=signal, second=second, min_turns=min_turns, driver=driver)


def L(lid, arche, level, setting, situation, opening, role, you_are, task, done, ai, facts, objectives, closing, variants, examples=None, learner_can_finalize=False):
    return dict(lid=lid, arche=arche, level=level, setting=setting, situation=situation, opening=opening, role=role, you_are=you_are, task=task, done=done,
                ai=ai, facts=facts, objectives=objectives, closing=closing, variants=variants, examples=examples, finalize=learner_can_finalize)
