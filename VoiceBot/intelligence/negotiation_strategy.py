"""Decide the counterpart's negotiating position in code; the model only phrases it.

The model never receives a reservation limit, so it cannot leak one. Concessions
shrink, need a reason or a trade, and react to the actual offer.
"""
import math
import re
from intelligence.conversation_direction import numeric_text

RATIONALE = re.compile(r'\b(because|since|given|benchmark|budget|last time|previous|prior|earlier package|based on|compared|cost|afford)\b', re.I)
CONDITION = re.compile(r'\b(if (?:you|we|i)|in exchange|in return|provided|as long as|on condition)\b', re.I)
ACCEPT = re.compile(r"\b(i accept|we accept|i agree|we agree|agreed|i confirm|we confirm|confirmed|it'?s a deal|we have a deal|deal\b|let'?s do (?:it|that)|i'?ll take it|we'?ll take it)\b", re.I)
VAGUE_YES = re.compile(r"^(?:yes|yeah|yep|sure|okay|ok|fine|alright|sounds good|that works|right)(?:[, ]+(?:i can|we can|i am|we are|i would|we would|please))?[.! ]*$", re.I)
WALK_AWAY = re.compile(r"\b(walk away|no deal|not going ahead|can'?t accept|cannot accept|won'?t accept|go with (?:the |our )?(?:other|alternative)|use (?:the |our )?(?:other|alternative)|pass on this|not interested)\b", re.I)
ALTERNATIVE = re.compile(r'\b(alternative|other supplier|another supplier|competitor|other vendor|someone else)\b', re.I)


def parse_terms(text):
    """Extract only figures the learner said. Partial terms remain partial."""
    numeric = numeric_text(text)
    terms = {}
    seats = re.search(r'\b(\d+)\s+(?:seats?|seeds?|people|licen[cs]es?)\b', numeric)
    if seats:
        terms['seats'] = int(seats.group(1))
    days = re.search(r'\b(\d+)[ -]+(?:\w+[ -]+)?days?\b', numeric)
    if days:
        terms['delivery_days'] = int(days.group(1))
    months = re.search(r'\b(\d+)[ -]+(?:\w+[ -]+)?months?\b', numeric)
    if months:
        terms['support_months'] = int(months.group(1))
    price_pattern = r'(?:usd\s*|\$)(\d+(?:\.\d+)?)|\b(\d{4,}(?:\.\d+)?)\b'
    # Prefer the figure being put forward over a benchmark mentioned earlier in the sentence.
    proposed = re.search(r"\b(?:offer|pay|do|propose|take|accept|go (?:to|up to)|at|for|confirm(?::)?)\b[^.?!]*?(?:" + price_pattern + ')', _after_benchmark(numeric))
    if proposed:
        terms['price'] = float(proposed.group(1) or proposed.group(2))
    else:
        prices = [float(p) for pair in re.findall(price_pattern, numeric) for p in pair if p]
        if prices:
            terms['price'] = prices[-1]
    return terms


def _after_benchmark(numeric):
    """Hide figures described as what something sold for or what a rival charges."""
    return re.sub(r'\b(?:sold|was|were|cost|costs|priced|charged|benchmark)\b[^.,;]*?(?:usd\s*|\$)?\d[\d.]*', ' ', numeric)


def floor_for(case, terms):
    """The seller's true minimum for a given package; never sent to the model."""
    rules = case.get('feasibility', {})
    public = case['public']
    days = terms.get('delivery_days', public['delivery_days'])
    support = terms.get('support_months', public['support_months'])
    floor = case['seller']['minimum']
    if days < public['delivery_days']:
        floor += rules.get('rush_cost', 1000)
    if days >= rules.get('maximum_delivery_days', 45):
        floor -= rules.get('late_delivery_saving', 0)
    floor += max(0, support - public['support_months']) * rules.get('extra_support_month_cost', 500)
    return floor


def new_state(case):
    return {'ask': case['public']['list_price'], 'pending': None, 'last_offer': None, 'moves': 0, 'holds': 0, 'final': False}


def package(case, terms):
    public = case['public']
    return (f"{terms.get('seats', public['seats'])} seats, delivery in {terms.get('delivery_days', public['delivery_days'])} days "
            f"and {terms.get('support_months', public['support_months'])} months of support")


def _step(gap, challenge, moves):
    share = {'beginner': .5, 'intermediate': .4, 'advanced': .3}.get(challenge, .4)
    return max(100, math.ceil(gap * share / 50) * 50) if gap > 0 else 0


def _result(action, purpose, fallback, authorised=(), words=40, ledger=None):
    return {'action': action, 'purpose': purpose, 'fallback': fallback, 'authorised': list(authorised), 'max_words': words, 'ledger': ledger}


def decide(case, neg, text, challenge='intermediate', responding_to=''):
    """Return the counterpart's decision for this turn, or None when no bargaining applies."""
    terms = parse_terms(text)
    public = case['public']
    rules = case.get('feasibility', {})

    if WALK_AWAY.search(text) and 'price' not in terms:
        return _result('respect_no_deal',
            'They may be walking away. Respect that without pressure. Do not offer anything new. Ask, in one short sentence, what would have had to be different, or accept their decision.',
            "I respect that. What would have had to be different for this to work?", words=25)

    pending_terms = neg.get('pending') or {}
    same_terms = all(terms.get(key) in (None, pending_terms.get(key)) for key in ('price', 'seats', 'delivery_days', 'support_months'))
    if pending_terms and same_terms and not CONDITION.search(text) and (ACCEPT.search(text) or VAGUE_YES.match(text.strip())):
        pending = neg['pending']
        figures = [pending['price'], pending['seats'], pending['delivery_days'], pending['support_months']]
        if ACCEPT.search(text):
            line = f"Good. To confirm: USD {pending['price']:,.0f} for {package(case, pending)}."
            return {**_result('accept', '', line, figures, 30, ledger={'kind': 'accept'}), 'exact': True}
        line = f"Just so we're both clear, are you confirming USD {pending['price']:,.0f} for {package(case, pending)}?"
        return {**_result('clarify', '', line, figures, 28), 'exact': True}

    about_terms = neg['moves'] or neg['last_offer'] is not None or re.search(r'\b(usd|\d{4,}|package|offer|price|trade|terms|\bor\b)', responding_to, re.I)
    if pending_terms and not same_terms and ACCEPT.search(text) and 'price' in terms and terms['price'] != pending_terms.get('price') and not CONDITION.search(text) and re.search(r'\b(i accept|we accept|to confirm)\b', text, re.I):
        said, standing = terms['price'], pending_terms['price']
        return {**_result('clarify', '', f"I offered USD {standing:,.0f} for {package(case, pending_terms)}, not USD {said:,.0f}. Are you accepting USD {standing:,.0f}?", [said, standing, pending_terms['seats'], pending_terms['delivery_days'], pending_terms['support_months']], 30), 'exact': True}

    if VAGUE_YES.match(text.strip()) and 'price' not in terms and about_terms:
        ask = neg['ask']
        return _result('clarify', f'A vague yes is not agreement. Ask what they are saying yes to, and whether they want the current position of USD {ask:,.0f} or something different.',
            f"Do you mean you'd accept USD {ask:,.0f}, or did you want to change something?", [ask], 25)

    if 'seats' in terms and terms['seats'] != public['seats']:
        return _result('clarify', f"This case is about {public['seats']} seats. Ask whether they really want {terms['seats']} seats, because that would need a separate quote.",
            f"Do you mean {terms['seats']} seats? This quote covers {public['seats']} seats, so a different number would need a separate quote.", [terms['seats'], public['seats']], 28)

    if ALTERNATIVE.search(text):
        return _result('compare',
            'They mentioned an alternative. Do not lower your price because of it. Compare like with like: ask how its delivery time and support compare with your package, and what matters most to them.',
            'That is useful to know. How does its delivery and support compare with what we are offering?', [], 35)

    if 'price' not in terms:
        changes = {key: terms[key] for key in ('delivery_days', 'support_months') if key in terms}
        if not changes:
            return None
        candidate = {**public, **changes}
        adjusted = max(floor_for(case, candidate), neg['ask'] + floor_for(case, candidate) - floor_for(case, public))
        limit_days = rules.get('minimum_delivery_days', 21), rules.get('maximum_delivery_days', 45)
        if not limit_days[0] <= candidate['delivery_days'] <= limit_days[1]:
            return _result('clarify', f'Delivery can only be between {limit_days[0]} and {limit_days[1]} days. Say so and ask what they would like instead.',
                f'We can only deliver between {limit_days[0]} and {limit_days[1]} days. What would work within that?', limit_days, 25)
        return _result('price_trade', f'Respond to their proposed change. For {package(case, candidate)}, your position is USD {adjusted:,.0f}. Say that plainly and ask whether it works.',
            f"For {package(case, candidate)}, I could do USD {adjusted:,.0f}. Would that work for you?", [adjusted, candidate['delivery_days'], candidate['support_months'], candidate['seats']], 32)

    offer = {**{key: public[key] for key in ('seats', 'delivery_days', 'support_months')}, **terms}
    price = offer['price']
    floor = floor_for(case, offer)
    adjust = floor - floor_for(case, public)
    ask_here = max(floor, neg['ask'] + adjust)
    moved_up = neg['last_offer'] is not None and price > neg['last_offer']
    # A reason earns one move. Repeating the same number with "because" earns nothing.
    has_reason = bool(RATIONALE.search(text)) and (neg['last_offer'] is None or moved_up or neg['moves'] == 0)
    has_trade = (bool(CONDITION.search(text)) or adjust < 0) and (neg['last_offer'] is None or moved_up or neg.get('last_adjust') != adjust)
    label = package(case, offer)
    ledger = {'kind': 'offer', 'terms': offer}

    def pending(offer_terms):
        return {**offer_terms}

    if price >= ask_here or (price >= floor and neg['moves'] >= 2 and (has_reason or has_trade or moved_up) and price >= ask_here - _step(ask_here - floor, challenge, neg['moves'])):
        return {**_result('confirm_terms', '',
            f"USD {price:,.0f} could work for {label}. Are you confirming those terms?", [price, offer['seats'], offer['delivery_days'], offer['support_months']], 30, ledger), 'exact': True, 'pending': pending(offer), 'last_offer': price}

    if not (has_reason or has_trade or moved_up):
        if neg['final'] and neg['holds'] >= 1:
            return {**_result('impasse', f'You cannot go below USD {ask_here:,.0f} for {label}, and you have already said so. Do not move. Say calmly that a deal may not be possible, and that it is fine if they decide not to go ahead.',
                f"I can't go lower than USD {ask_here:,.0f} for {label}. If that doesn't work, it may be fair to say we can't reach a deal.", [ask_here, offer['seats'], offer['delivery_days'], offer['support_months']], 35, ledger), 'last_offer': price, 'holds': neg['holds'] + 1}
        anchored = price < public['list_price'] * .7
        purpose = (f'Their USD {price:,.0f} is far below the list price and they gave no reason. Do not move. Point to the earlier package at USD 11,000 and ask how they reached their number.'
                   if anchored else f'They offered USD {price:,.0f} with no reason or trade. Do not move yet. Ask how they got to that number, or what they could offer in return.')
        return {**_result('hold', purpose, f"How did you get to USD {price:,.0f}? What could you offer me in return for a lower price?", [price, 11000], 30, ledger), 'last_offer': price, 'holds': neg['holds'] + 1}

    gap = ask_here - floor
    if gap <= 0:
        saving = rules.get('late_delivery_saving', 0)
        hint = ' A later delivery date would help you, so you may mention that.' if saving and offer['delivery_days'] < rules.get('maximum_delivery_days', 45) else ''
        fallback = f"I can't go lower than USD {ask_here:,.0f} for {label}. If that doesn't work, it may be fair to say we can't reach a deal."
        if neg['final'] and neg['holds'] >= 1:
            return {**_result('impasse', f'You cannot go below USD {ask_here:,.0f} for {label}, and you have already said so. Do not move. Say calmly that a deal may not be possible, and that it is fine if they decide not to go ahead.{hint}',
                fallback, [ask_here, offer['seats'], offer['delivery_days'], offer['support_months']], 35, ledger), 'last_offer': price, 'holds': neg['holds'] + 1}
        return {**_result('final_position', f'USD {ask_here:,.0f} for {label} is as far as you can go. Say that clearly, without describing it as a limit or minimum, and explain it is about what the package costs you to deliver.{hint}',
            f"USD {ask_here:,.0f} for {label} is as far as I can go.", [ask_here, offer['seats'], offer['delivery_days'], offer['support_months']], 35, ledger), 'last_offer': price, 'final': True, 'holds': neg['holds'] + 1}

    new_here = max(floor, ask_here - _step(gap, challenge, neg['moves']))
    if price >= new_here:
        return {**_result('confirm_terms', '',
            f"USD {price:,.0f} could work for {label}. Are you confirming those terms?", [price, offer['seats'], offer['delivery_days'], offer['support_months']], 30, ledger), 'exact': True, 'pending': pending(offer), 'last_offer': price}
    reason = 'because they gave a reason' if has_reason else 'because they offered a trade' if has_trade else 'because they moved'
    follow_up = ('What could you do in return?', 'What could you be flexible on?', 'What can you give me on delivery or support?')[neg['moves'] % 3]
    return {**_result('counter', f"Your position: not USD {price:,.0f}, but you can do USD {new_here:,.0f} for {label}. You are moving {reason}, so connect your figure to what was just said and ask for something in return. Do not call any figure a limit or minimum.",
        f"I can't do USD {price:,.0f}, but I could do USD {new_here:,.0f} for {label}. {follow_up}", [price, new_here, offer['seats'], offer['delivery_days'], offer['support_months']], 40, ledger),
        'ask': new_here - adjust, 'moves': neg['moves'] + 1, 'last_offer': price, 'last_adjust': adjust, 'pending': pending({**offer, 'price': new_here})}


def apply(neg, decision):
    """Update the bargaining state from a decision (a pure helper for the runtime)."""
    for key in ('ask', 'moves', 'last_offer', 'last_adjust', 'holds', 'final', 'pending'):
        if key in decision:
            neg[key] = decision[key]
    return neg
