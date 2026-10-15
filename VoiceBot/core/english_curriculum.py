"""Thirty conversation-first English lessons for the Hikari prototype."""

ENGLISH_CURRICULUM = [
    (1, "First Greetings", "beginner", "Meet a friendly neighbour and practise hello, goodbye, and polite responses.", "Neighbour", ["Use a natural greeting", "Say your name", "Close the conversation politely"], "Hi! I don't think we've met before. I'm Alex. What's your name?"),
    (2, "Introduce Yourself", "beginner", "Introduce yourself to a new classmate using simple complete sentences.", "Classmate", ["Share where you are from", "Describe what you do", "Ask one question back"], "Hello, I'm Maya. I'm new here. Could you tell me a little about yourself?"),
    (3, "Family and Friends", "beginner", "Talk about people close to you and describe simple relationships.", "New friend", ["Use family vocabulary", "Use he, she, and they correctly", "Ask about another person"], "You mentioned your family earlier. Who do you live with?"),
    (4, "Your Daily Routine", "beginner", "Describe a normal day using present-simple sentences and time expressions.", "Language partner", ["Sequence three daily actions", "Use time expressions", "Ask about the other person's routine"], "What does a normal weekday look like for you?"),
    (5, "Likes and Dislikes", "beginner", "Discuss food, hobbies, and entertainment preferences.", "Friend", ["Say what you like and dislike", "Give a simple reason", "Find one shared interest"], "I'm choosing something for us to do this weekend. What do you enjoy?"),
    (6, "Ordering Food", "beginner", "Order a meal, ask about an item, and respond to a server.", "Server", ["Order politely", "Ask one menu question", "Confirm the order"], "Good evening! Here is the menu. What would you like to order?"),
    (7, "Shopping for Essentials", "beginner", "Ask for an item, size, colour, and price in a shop.", "Shop assistant", ["Explain what you need", "Ask about price or size", "Accept or decline politely"], "Welcome! What are you looking for today?"),
    (8, "Finding Your Way", "beginner", "Ask for and follow simple directions around town.", "Local resident", ["Ask for a destination", "Check one direction", "Repeat the route to confirm"], "Hi there. You look a little lost. Where are you trying to go?"),
    (9, "Making an Appointment", "beginner", "Arrange a suitable day and time by phone.", "Receptionist", ["State the reason for calling", "Suggest or accept a time", "Confirm the appointment details"], "Good morning, City Clinic. How can I help you?"),
    (10, "Beginner Conversation Checkpoint", "beginner", "Combine greetings, questions, descriptions, and clarification in a short social conversation.", "Conversation partner", ["Keep the exchange going", "Ask for clarification when needed", "Use complete simple sentences"], "Hello! Let's get to know each other. How has your day been so far?"),
    (11, "Tell a Past Story", "intermediate", "Tell a clear story about a memorable day using past tenses.", "Friend", ["Set the time and place", "Sequence events clearly", "Explain how the story ended"], "Tell me about a day you still remember clearly. What happened?"),
    (12, "Plans and Invitations", "intermediate", "Make plans, invite someone, and negotiate a convenient time.", "Friend", ["Make an invitation", "Discuss future plans", "Agree on practical details"], "Would you like to do something together this weekend?"),
    (13, "Explain a Problem", "intermediate", "Describe a practical problem and ask for the right kind of help.", "Support agent", ["State the problem precisely", "Explain what you already tried", "Confirm the proposed solution"], "Thanks for contacting support. What problem are you experiencing?"),
    (14, "Give Clear Instructions", "intermediate", "Guide another person through a familiar process step by step.", "New coworker", ["Use sequence markers", "Check understanding", "Correct a misunderstanding politely"], "I'm new to this process. Could you walk me through it?"),
    (15, "Express and Support an Opinion", "intermediate", "Give an opinion, support it, and respond to a different view.", "Discussion partner", ["State a clear opinion", "Give two reasons or examples", "Acknowledge another view"], "Do you think working from home is better than working in an office?"),
    (16, "Workplace Small Talk", "intermediate", "Start and sustain appropriate informal conversation with colleagues.", "Coworker", ["Open naturally", "Use follow-up questions", "Move to work talk smoothly"], "Morning! How was your weekend?"),
    (17, "Give a Work Update", "intermediate", "Report progress, explain a blocker, and name the next step.", "Team lead", ["Lead with current status", "Explain the blocker without blame", "Commit to a next step"], "Can you give me a quick update on your task?"),
    (18, "Active Listening in English", "intermediate", "Show understanding, paraphrase, and ask useful follow-up questions.", "Concerned colleague", ["Acknowledge the speaker", "Paraphrase the main concern", "Ask a relevant follow-up"], "I'm worried that the new schedule is going to overload our team."),
    (19, "Handle a Customer Concern", "intermediate", "Respond empathetically and guide a customer toward a solution.", "Customer", ["Acknowledge emotion", "Clarify the issue", "Offer a concrete next action"], "My order is late again, and nobody has explained what is happening."),
    (20, "Intermediate Conversation Checkpoint", "intermediate", "Solve a shared planning problem while speaking clearly with two AI participants.", "Project coordinator", ["Contribute a useful idea", "Respond to both speakers", "Reach a shared decision"], "We need to choose a plan today. What should our first priority be?"),
    (21, "Interview: Tell Me About Yourself", "advanced", "Deliver a focused professional introduction and handle follow-up questions.", "Hiring manager", ["Give a relevant professional summary", "Connect experience to the role", "Answer follow-up questions directly"], "Welcome. To begin, could you tell us about yourself and why this role interests you?"),
    (22, "Interview: Evidence and Impact", "advanced", "Use the STAR structure while two interviewers probe for evidence.", "Lead interviewer", ["Structure the example", "Explain your own actions", "Quantify the result"], "Tell us about a difficult problem you solved and the impact of your work."),
    (23, "Persuasive Proposal", "advanced", "Present a recommendation to a decision-maker with support from an AI teammate.", "Decision-maker", ["State the recommendation early", "Use evidence", "Answer an objection collaboratively"], "You have five minutes to convince me that this proposal is worth funding."),
    (24, "Negotiate Priorities", "advanced", "Negotiate scope and timing against two AI stakeholders.", "Client director", ["Discover underlying priorities", "Offer a fair trade-off", "Confirm the agreement"], "We need the full project two weeks earlier and cannot increase the budget."),
    (25, "Disagree Constructively", "advanced", "Challenge an idea without damaging the working relationship.", "Project manager", ["Acknowledge common ground", "Explain the concern with evidence", "Offer an alternative"], "The team has agreed on my approach, so I don't see a reason to reopen the decision."),
    (26, "Give and Receive Feedback", "advanced", "Exchange specific feedback and agree on a change with an AI teammate present.", "Coworker", ["Use specific observations", "Explain impact", "Agree on one improvement"], "You asked for feedback on yesterday's client meeting. Are you ready to discuss it?"),
    (27, "Resolve Team Conflict", "advanced", "Mediate a disagreement between two AI colleagues in a round-robin conversation.", "Colleague A", ["Let each side be heard", "Identify shared interests", "Propose a fair next step"], "We cannot continue like this. Sam keeps changing the plan after we agree on it."),
    (28, "Lead a Difficult Meeting", "advanced", "Chair a meeting in which an AI team challenges your decision.", "Operations lead", ["Set a clear agenda", "Manage competing voices", "Close with owners and actions"], "Before we accept this decision, the team has several serious concerns."),
    (29, "Cross-Cultural Collaboration", "advanced", "Clarify tone, assumptions, and expectations with an international project team.", "Regional partner", ["Avoid idioms and ambiguity", "Check shared understanding", "Agree communication norms"], "Our teams interpreted the last message very differently. How should we prevent that happening again?"),
    (30, "English Speaking Capstone", "advanced", "Lead a complete multi-party workplace conversation from opening to decision.", "Executive sponsor", ["Speak clearly and confidently", "Respond to multiple viewpoints", "Summarise the final decision and next steps"], "We are ready for your recommendation. Please lead us through the issue and what you think we should do."),
]


def roleplay_mode(sequence: int) -> str:
    if sequence in {23, 26}:
        return "learner_with_ai_team"
    if sequence in {22, 24, 28}:
        return "ai_team_vs_learner"
    if sequence in {20, 27, 29, 30}:
        return "round_robin"
    return "one_to_one"


def participants(sequence: int, counterpart: str) -> list[dict[str, str]]:
    mode = roleplay_mode(sequence)
    if mode == "learner_with_ai_team":
        return [
            {"type": "learner", "role": "Learner", "team": "learner"},
            {"type": "ai", "role": "AI teammate", "displayName": "AI Teammate", "team": "learner"},
            {"type": "ai", "role": counterpart, "displayName": counterpart, "team": "opponent"},
        ]
    if mode == "ai_team_vs_learner":
        return [
            {"type": "learner", "role": "Learner", "team": "learner"},
            {"type": "ai", "role": counterpart, "displayName": counterpart, "team": "opponent"},
            {"type": "ai", "role": "Second stakeholder", "displayName": "Second Stakeholder", "team": "opponent"},
        ]
    if mode == "round_robin":
        return [
            {"type": "learner", "role": "Learner", "team": "learner"},
            {"type": "ai", "role": counterpart, "displayName": counterpart, "team": "participant"},
            {"type": "ai", "role": "Second participant", "displayName": "Second Participant", "team": "participant"},
        ]
    return [
        {"type": "learner", "role": "Learner", "team": "learner"},
        {"type": "ai", "role": counterpart, "displayName": counterpart, "team": "opponent"},
    ]


# Teaching content is deliberately separate from the scenario copy.  A scenario
# makes speaking engaging; these targets make it a lesson that can be mastered.
_LEARNING_TARGETS = {
    1: ("Greetings and introductions", ["Hello, my name is …", "Nice to meet you.", "Goodbye. See you soon."], ["hello", "name", "meet", "goodbye"], [("use a greeting", [r"\b(?:hello|hi|hey|good (?:morning|afternoon|evening))\b"]), ("introduce yourself", [r"\b(?:my name is|i am|i'm)\s+[a-z]"]), ("close politely", [r"\b(?:goodbye|bye|see you|nice meeting)\b"])]),
    2: ("Complete self-introductions", ["I'm from …", "I work/study …", "What about you?"], ["from", "live", "work", "study"], [("say where you are from", [r"\b(?:i'm|i am) from\b", r"\bi live in\b"]), ("describe what you do", [r"\b(?:i work|i study|i'm a|i am a)\b"]), ("ask a question back", [r"\b(?:what|where|how|do|are)\b[^?]*\?"])]),
    3: ("Family vocabulary and pronouns", ["I live with my …", "He/She works …", "What about your family?"], ["family", "parents", "brother", "sister"], [("name a family relationship", [r"\b(?:family|parent|mother|father|brother|sister|wife|husband|friend)s?\b"]), ("use a person pronoun", [r"\b(?:he|she|they)\b"]), ("ask about the other person", [r"\b(?:who|what|how many|do you)\b[^?]*\?"])]),
    4: ("Present simple and time expressions", ["I usually wake up at …", "Then I …", "What time do you …?"], ["usually", "morning", "then", "evening"], [("describe a routine", [r"\bi (?:usually|normally|always|often|sometimes)\b"]), ("use a time expression", [r"\b(?:at \d|in the morning|in the evening|after|before|then)\b"]), ("ask about a routine", [r"\b(?:what time|when|how often|do you)\b[^?]*\?"])]),
    5: ("Preferences with reasons", ["I like … because …", "I don't really enjoy …", "Do you like …?"], ["like", "enjoy", "prefer", "because"], [("state a preference", [r"\b(?:i like|i love|i enjoy|i prefer|i don't like|i dislike)\b"]), ("give a reason", [r"\bbecause\b"]), ("ask about a preference", [r"\b(?:do you like|what do you|which do you)\b[^?]*\?"])]),
    6: ("Polite food ordering", ["I'd like …, please.", "What do you recommend?", "Yes, that's correct."], ["menu", "order", "please", "recommend"], [("order politely", [r"\b(?:i'd like|i would like|could i have|may i have)\b"]), ("ask about the menu", [r"\b(?:what|which|does|is there|do you)\b[^?]*\?"]), ("confirm the order", [r"\b(?:that's correct|yes,? please|that is all|sounds good)\b"])]),
    7: ("Shopping questions and polite decisions", ["I'm looking for …", "Do you have this in …?", "I'll take it / No, thank you."], ["size", "colour", "price", "looking"], [("explain what you need", [r"\b(?:i'm looking for|i need|do you have)\b"]), ("ask about price or size", [r"\b(?:price|cost|how much|size|colour|color)\b"]), ("accept or decline", [r"\b(?:i'll take|i will take|no thank you|not today|that's all)\b"])]),
    8: ("Directions and confirmation", ["How do I get to …?", "Do I turn left?", "So I go straight, then …"], ["left", "right", "straight", "near"], [("ask for directions", [r"\b(?:how (?:do|can) i get|where is|could you tell me)\b"]), ("check a direction", [r"\b(?:left|right|straight|next to|across)\b"]), ("repeat the route", [r"\b(?:so i|first|then|after that)\b"])]),
    9: ("Appointments and confirmation", ["I'm calling to …", "Is Tuesday at three available?", "So that's Tuesday at three."], ["appointment", "available", "schedule", "confirm"], [("state the reason", [r"\b(?:i'm calling|i need|i'd like|appointment)\b"]), ("agree on a time", [r"\b(?:monday|tuesday|wednesday|thursday|friday|morning|afternoon|at \d)\b"]), ("confirm details", [r"\b(?:so that's|let me confirm|see you|that works)\b"])]),
    10: ("Sustaining a beginner conversation", ["Could you say that again?", "That sounds …", "What about you?"], ["again", "mean", "interesting", "because"], [("give a complete answer", [r"\b(?:i am|i'm|i was|i like|i think|my)\b"]), ("ask or clarify", [r"\b(?:what about you|could you|what do you mean|again)\b"]), ("extend with a reason", [r"\bbecause\b", r"\band then\b"])]),
    11: ("Past-tense storytelling", ["Last …, I went …", "After that …", "In the end …"], ["yesterday", "last", "then", "finally"], [("set the past context", [r"\b(?:yesterday|last|ago|when i was)\b"]), ("sequence events", [r"\b(?:then|after that|next|later)\b"]), ("explain the ending", [r"\b(?:finally|in the end|eventually|ended)\b"])]),
    12: ("Invitations and future plans", ["Would you like to …?", "I'm going to …", "How about Saturday?"], ["invite", "available", "weekend", "plan"], [("make an invitation", [r"\b(?:would you like|do you want|how about)\b"]), ("use future language", [r"\b(?:will|going to|planning to)\b"]), ("agree on details", [r"\b(?:at \d|monday|tuesday|wednesday|thursday|friday|saturday|sunday|that works)\b"])]),
    13: ("Explaining problems clearly", ["The problem is …", "I've already tried …", "So I should …, correct?"], ["problem", "tried", "error", "solution"], [("state the problem", [r"\b(?:the problem is|it isn't|it doesn't|error|issue)\b"]), ("describe an attempt", [r"\b(?:i tried|i've tried|i have tried|already)\b"]), ("confirm the solution", [r"\b(?:so i should|is that correct|do you mean|that should)\b"])]),
    14: ("Sequenced instructions", ["First …", "Next …", "Does that make sense?"], ["first", "next", "then", "finally"], [("sequence steps", [r"\bfirst\b", r"\b(?:next|then|after that)\b"]), ("check understanding", [r"\b(?:does that make sense|is that clear|do you understand|any questions)\b"]), ("correct politely", [r"\b(?:actually|not quite|let me clarify|instead)\b"])]),
    15: ("Opinions with support", ["In my opinion …", "The first reason is …", "I see your point, but …"], ["opinion", "reason", "example", "however"], [("state an opinion", [r"\b(?:i think|i believe|in my opinion|my view)\b"]), ("support it", [r"\b(?:because|reason|for example|such as)\b"]), ("acknowledge another view", [r"\b(?:i see your point|i understand|however|on the other hand)\b"])]),
    16: ("Natural workplace small talk", ["How was your …?", "That sounds …", "By the way, about …"], ["weekend", "sounds", "by the way", "project"], [("open naturally", [r"\b(?:how was|how is|did you|good morning|morning)\b"]), ("ask a follow-up", [r"\b(?:what|where|how|did|do)\b[^?]*\?"]), ("transition to work", [r"\b(?:by the way|speaking of|about the|shall we discuss|project|work)\b"])]),
    17: ("Structured work updates", ["The current status is …", "The blocker is …", "Next, I will …"], ["status", "completed", "blocker", "next"], [("give status", [r"\b(?:status|completed|finished|on track|in progress)\b"]), ("explain a blocker", [r"\b(?:blocker|blocked|delay|because|waiting)\b"]), ("commit to a next step", [r"\b(?:next i|i will|by (?:today|tomorrow|monday|tuesday|wednesday|thursday|friday))\b"])]),
    18: ("Active-listening language", ["I understand that …", "So you're concerned about …", "What would help most?"], ["understand", "concerned", "so", "help"], [("acknowledge", [r"\b(?:i understand|i hear you|that sounds|i appreciate)\b"]), ("paraphrase", [r"\b(?:so you|if i understand|you mean|it sounds like)\b"]), ("ask a follow-up", [r"\b(?:what|how|which|could you)\b[^?]*\?"])]),
    19: ("Empathetic customer responses", ["I'm sorry that …", "Could you confirm …?", "What I can do is …"], ["sorry", "understand", "confirm", "resolve"], [("acknowledge emotion", [r"\b(?:sorry|understand|frustrating|appreciate)\b"]), ("clarify", [r"\b(?:could you|can you|when did|which|what)\b[^?]*\?"]), ("offer an action", [r"\b(?:i can|i will|what i can do|next step)\b"])]),
    20: ("Collaborative planning", ["I suggest we prioritise … because …", "What do you think?", "So we agree to …"], ["priority", "suggest", "because", "agree"], [("contribute an idea", [r"\b(?:i suggest|we should|our priority|i recommend)\b"]), ("engage another speaker", [r"\b(?:what do you think|do you agree|your view)\b"]), ("state a decision", [r"\b(?:we agree|we decided|our decision|so we will)\b"])]),
    21: ("Focused interview introductions", ["I am a … with experience in …", "A relevant achievement is …", "This role interests me because …"], ["experience", "achievement", "skills", "role"], [("summarise experience", [r"\b(?:experience|worked|background|currently)\b"]), ("connect to the role", [r"\b(?:this role|position|relevant|would help)\b"]), ("give a specific example", [r"\b(?:for example|achievement|result|increased|reduced|improved)\b"])]),
    22: ("STAR evidence", ["The situation was …", "My task was …", "I took …", "The result was …"], ["situation", "task", "action", "result"], [("set situation and task", [r"\b(?:situation|task|needed to|responsible for)\b"]), ("explain personal action", [r"\b(?:i took|i created|i led|i decided|my action)\b"]), ("quantify a result", [r"\b(?:result|percent|%|increased|reduced|saved|improved|\d+)\b"])]),
    23: ("Persuasive recommendations", ["I recommend …", "The evidence shows …", "I understand that concern; however …"], ["recommend", "evidence", "benefit", "however"], [("state a recommendation", [r"\b(?:i recommend|my proposal|we should)\b"]), ("support with evidence", [r"\b(?:evidence|data|because|result|research)\b"]), ("answer an objection", [r"\b(?:i understand|that concern|however|we can address)\b"])]),
    24: ("Negotiating trade-offs", ["What matters most is …?", "If we …, could you …?", "So we have agreed …"], ["priority", "trade-off", "scope", "agreement"], [("discover a priority", [r"\b(?:what matters most|which is more important|your priority|why is)\b"]), ("offer a trade-off", [r"\b(?:if we|in exchange|could reduce|could extend|trade-off)\b"]), ("confirm agreement", [r"\b(?:we agree|agreed that|to confirm|our agreement)\b"])]),
    25: ("Constructive disagreement", ["I agree that …", "My concern is … because …", "An alternative would be …"], ["agree", "concern", "evidence", "alternative"], [("acknowledge common ground", [r"\b(?:i agree|we both|common goal|i understand)\b"]), ("explain the concern", [r"\b(?:my concern|however|because|evidence)\b"]), ("offer an alternative", [r"\b(?:alternative|instead|another option|i suggest)\b"])]),
    26: ("Specific feedback", ["When you …, I noticed …", "The impact was …", "Next time, could we …?"], ["noticed", "impact", "feedback", "improve"], [("give an observation", [r"\b(?:i noticed|when you|specific example)\b"]), ("explain impact", [r"\b(?:impact|meant that|as a result|caused)\b"]), ("agree an improvement", [r"\b(?:next time|i will|we can|agree to)\b"])]),
    27: ("Conflict mediation", ["Let me hear both views.", "You both want …", "A fair next step is …"], ["perspective", "both", "shared", "fair"], [("invite both sides", [r"\b(?:both views|each of you|your perspective|hear from)\b"]), ("identify common ground", [r"\b(?:you both|shared|common|both want)\b"]), ("propose a fair step", [r"\b(?:fair|next step|i propose|we could)\b"])]),
    28: ("Leading challenging meetings", ["Our purpose today is …", "Let's hear … first.", "To conclude, X will do Y by …"], ["agenda", "priority", "owner", "deadline"], [("set an agenda", [r"\b(?:agenda|purpose today|our goal|first we will)\b"]), ("manage contributions", [r"\b(?:let's hear|one at a time|come back to|your concern)\b"]), ("close with ownership", [r"\b(?:will (?:do|own|send|prepare)|owner|by (?:today|tomorrow|monday|tuesday|wednesday|thursday|friday)|deadline)\b"])]),
    29: ("Cross-cultural clarification", ["When you say …, do you mean …?", "To avoid ambiguity …", "Let's agree to …"], ["clarify", "mean", "expectation", "agree"], [("clarify meaning", [r"\b(?:do you mean|when you say|could you clarify|to clarify)\b"]), ("check understanding", [r"\b(?:is that correct|have i understood|same understanding|does that mean)\b"]), ("agree a norm", [r"\b(?:let's agree|we will|from now on|communication norm)\b"])]),
    30: ("Capstone leadership conversation", ["My recommendation is …", "I hear both perspectives …", "To summarise, we decided …"], ["recommendation", "evidence", "perspective", "decision"], [("make a supported recommendation", [r"\b(?:my recommendation|i recommend|we should)\b.*\b(?:because|evidence|data|result)\b"]), ("respond to viewpoints", [r"\b(?:your point|your concern|both perspectives|i understand)\b"]), ("summarise the decision", [r"\b(?:to summarise|in summary|we decided|next steps)\b"])]),
}


def learning_design(sequence: int) -> dict:
    """Return teachable and machine-checkable content for one English lesson."""
    focus, examples, vocabulary, targets = _LEARNING_TARGETS[sequence]
    level = ENGLISH_CURRICULUM[sequence - 1][2]
    return {
        "focus": focus,
        "grammar": {"beginner": "Use short complete sentences", "intermediate": "Connect ideas clearly", "advanced": "Use precise, audience-aware language"}[level],
        "examples": examples,
        "vocabulary": vocabulary,
        "targets": [{"name": name, "patterns": patterns} for name, patterns in targets],
        "minimum_turns": {"beginner": 3, "intermediate": 4, "advanced": 5}[level],
        "word_target": {"beginner": 24, "intermediate": 55, "advanced": 90}[level],
        "max_answer_seconds": {"beginner": 18, "intermediate": 30, "advanced": 60}[level],
    }
