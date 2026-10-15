"""Bounded scenario variation: objectives stay fixed; practice facts change.

No provider dependency, so fresh grounded attempts also work offline. Generated
facts are roleplay facts, never claims about an uploaded policy.
"""
import re

SETTINGS = ['a community event', 'a neighbourhood café', 'a local library', 'a weekend gathering']
NAMES = ['Alex', 'Sam', 'Maya', 'Robin']
WORKPLACE = {
 'communication': [('a customer onboarding report', 'a missing data export'), ('a website release', 'a failed accessibility check'), ('a stock reconciliation', 'an incomplete supplier file'), ('a training rollout', 'a scheduling conflict')],
 'active-listening': [('billing portal', 'duplicate charges'), ('delivery tracking', 'missing updates'), ('support system', 'unanswered tickets'), ('booking service', 'cancelled reservations')],
 'conflict-resolution': [('meeting room', 'a client briefing'), ('testing environment', 'a release check'), ('shared designer', 'an urgent review'), ('training space', 'a workshop')],
 'negotiation': [('training package', 'a lower price'), ('delivery contract', 'an earlier deadline'), ('support plan', 'extra coverage'), ('supplier order', 'flexible payment terms')],
 'interviews': [('customer success', 'resolving a dissatisfied customer'), ('project coordination', 'managing conflicting priorities'), ('operations', 'improving a process'), ('team leadership', 'handling a disagreement')],
 'presentations': [('a support pilot', 'renew funding'), ('a scheduling proposal', 'approve a trial'), ('a training review', 'choose next quarter priorities'), ('an inventory plan', 'approve additional resources')],
 'storytelling': [('a client recovery', 'trust'), ('a team improvement', 'collaboration'), ('a delivery challenge', 'reliability'), ('a process redesign', 'efficiency')],
 'critical-thinking': [('response times', 'customer satisfaction'), ('sales volume', 'repeat purchases'), ('course attendance', 'skill retention'), ('delivery speed', 'return rates')],
 'ai-literacy': [('a customer summary', 'personal contact details'), ('a performance review', 'employee information'), ('a sales forecast', 'unverified figures'), ('a support reply', 'an invented policy')],
 'social-engineering': [('IT support', 'a password'), ('a supplier', 'changed bank details'), ('a senior executive', 'bypassing access checks'), ('HR', 'private employee records')],
 'email-professionalism': [('a delayed delivery', 'a customer'), ('a changed appointment', 'a colleague'), ('an invoice question', 'a supplier'), ('a meeting follow-up', 'a manager')],
}

def vary(activity, attempt, focus, difficulty):
    index=attempt % 4
    language=activity.get('training_language')
    name=NAMES[index]
    if language:
        context=f"{activity['context']} This attempt takes place at {SETTINGS[index]}. Your partner is {name}."
        opening=re.sub(r'\bAlex\b', name, activity['opening_situation'])
        if activity.get('roleplay_mode')!='one_to_one':
            context=f"{activity['context']} This attempt takes place at {SETTINGS[index]}. Participants retain their assigned roles."
            opening=activity['opening_situation']
    else:
        first,second=WORKPLACE.get(activity['primary_skill_id'],[('a new workplace situation','a practical constraint')]*4)[index]
        contexts={
          'communication':f"Your {first} is delayed because of {second}. Explain the impact and propose a concrete next step.",
          'active-listening':f"A customer is unhappy with the {first} because of {second}. Clarify the facts before proposing a solution.",
          'conflict-resolution':f"A colleague needs the shared {first} for {second}, but your team already booked it. Resolve the disagreement fairly.",
          'negotiation':f"You are discussing a {first}. Your counterpart wants {second}; discover priorities and exchange concessions rather than agreeing immediately.",
          'interviews':f"You are interviewing for a role in {first}. Give a specific example of {second} using situation, action and result.",
          'presentations':f"Brief a decision-making panel about {first}. Your purpose is to {second}. Use evidence, acknowledge limitations and request a decision.",
          'storytelling':f"Tell a professional story about {first}. Make its relevance to {second} clear without inventing achievements.",
          'critical-thinking':f"A report says {first} improved, while another says {second} declined. Test assumptions and recommend what evidence to gather.",
          'ai-literacy':f"A colleague wants to publish AI-generated {first} containing {second}. Explain verification, privacy and disclosure precautions.",
          'social-engineering':f"An unsolicited caller claiming to be {first} urgently requests {second}. Verify through an approved channel and report suspicious conduct.",
          'email-professionalism':f"Compose a professional email about {first} to {second}. Include a clear subject, polite explanation, requested action and closing.",
        }
        context=contexts.get(activity['primary_skill_id'],activity['context'])
        opening=f"Let's discuss {first}. {activity['opening_situation']}" if activity['primary_skill_id'] not in contexts else f"We need to discuss {first}. How would you handle this situation?"
        # Administrator-authored cases must not be replaced by a seeded case.
        if activity['id']!='activity-'+activity['primary_skill_id']:
            context=activity['context']+f" This practice is led by a new colleague at {SETTINGS[index]}."
            opening=activity['opening_situation']
    context+=f" Practice focus: {focus}."
    if difficulty=='advanced':context+=' Expect a follow-up challenge and justify trade-offs with evidence.'
    elif difficulty=='beginner':context+=' Your partner should use short questions and offer a model only when needed.'
    return {'situation':context,'opening':opening,'variant':index}
