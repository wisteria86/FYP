"""Persistent training domain for the Hikari employee-training platform."""
from __future__ import annotations

import json
import math
import re
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from database.connection import connect_database
from database.migration_runner import run_migrations
from core.english_curriculum import (
    ENGLISH_CURRICULUM,
    learning_design,
    participants as english_participants,
    roleplay_mode,
)


SKILLS = [
    ("english-speaking", "Spoken English", "Build practical English fluency through structured conversation.", ["fluency", "vocabulary", "grammar", "comprehension"]),
    ("communication", "Workplace Communication", "Practice clear, concise and professional conversations.", ["clarity", "professionalism", "conciseness"]),
    ("active-listening", "Active Listening", "Understand, confirm and respond to what colleagues need.", ["acknowledgement", "clarifying questions", "summarising"]),
    ("conflict-resolution", "Conflict Resolution", "De-escalate disagreement and find workable next steps.", ["empathy", "de-escalation", "problem solving"]),
    ("negotiation", "Negotiation", "Reach fair agreements while protecting key priorities.", ["discovery", "trade-offs", "closing",'anchoring','counteroffers','concessions','objection handling']),
    ("interviews", "Job Interviews", "Give relevant, evidence-led answers with confidence.", ["relevance", "STAR evidence", "confidence"]),
    ("presentations", "Presentations", "Explain ideas with structure, pace and audience awareness.", ["structure", "delivery", "audience focus"]),
    ("storytelling", "Professional Storytelling", "Make workplace examples memorable and purposeful.", ["narrative", "evidence", "impact"]),
    ("critical-thinking", "Critical Thinking", "Question assumptions and make evidence-based decisions.", ["analysis", "evidence", "judgement"]),
    ("ai-literacy", "Responsible AI Use", "Use AI safely, critically and transparently at work.", ["verification", "privacy", "transparency"]),
    ("social-engineering", "Social Engineering Awareness", "Recognise and safely respond to manipulation attempts.", ["risk recognition", "verification", "reporting"]),
    ('company-knowledge','Company Knowledge','Apply your organization’s policies using cited evidence.',['policy application','source evidence','uncertainty']),
    ('email-professionalism','Email Professionalism','Write clear, polite workplace emails with actionable next steps.',['subject clarity','tone','requested action','closing']),
]

SCENARIOS = {
    'company-knowledge':('Company policy practice','Apply an authorized policy to a workplace request.','Policy trainer',['Explain the relevant policy rule','Apply the rule to the request','Verify anything the document does not cover']),
    'email-professionalism':('Professional email','Write a clear professional email for a workplace request.','Colleague',['Use a clear subject and greeting','Explain the purpose politely','Request an action and close professionally']),
    "english-speaking": ("English conversation", "Practise useful spoken English in a guided real-life conversation.", "Conversation partner", ["Speak in complete English sentences", "Listen and respond naturally", "Ask for clarification when needed"]),
    "communication": ("Priority update", "Your team lead asks why a task is late and what will happen next.", "Team lead", ["Explain the issue without blame", "State impact", "Propose a specific next step"]),
    "active-listening": ("Unclear customer concern", "A customer says the service is unreliable but gives few details.", "Concerned customer", ["Acknowledge the concern", "Ask a useful clarifying question", "Confirm what you understood"]),
    "conflict-resolution": ("Shared-resource conflict", "A colleague says you monopolised a resource and delayed their work.", "Frustrated colleague", ["De-escalate", "Recognise their impact", "Agree a fair process"]),
    "negotiation": ("Deadline negotiation", "A client wants delivery two days earlier without changing scope.", "Client", ["Discover the true priority", "Offer a trade-off", "Confirm an agreement"]),
    "interviews": ("Behavioural interview", "An interviewer asks about a time you solved a difficult team problem.", "Interviewer", ["Give a structured example", "Explain your own actions", "Quantify or clarify the result"]),
    "presentations": ("Executive project brief", "Give a short update to leaders who have little time and no technical context.", "Department director", ["Lead with the main point", "Use a clear structure", "Finish with a decision or next step"]),
    "storytelling": ("Customer success story", "Explain how your work improved an outcome without overselling it.", "Prospective customer", ["Set context", "Describe the turning point", "Connect the result to the audience"]),
    "critical-thinking": ("Conflicting metrics", "Two reports disagree about whether a pilot succeeded.", "Project sponsor", ["Identify assumptions", "Ask for evidence", "Recommend a defensible next step"]),
    "ai-literacy": ("AI-generated report", "A colleague wants to send an AI-written report containing customer data.", "Colleague", ["Identify privacy and accuracy risks", "Suggest verification", "Explain responsible disclosure"]),
    "social-engineering": ("Urgent access request", "Someone claiming to be an executive asks you to bypass normal access checks.", "Impatient caller", ["Do not disclose credentials", "Verify through an approved channel", "Report the attempt"]),
}

SCENARIO_OPENINGS = {
    'company-knowledge':'What rule applies to this request, and where is it stated?',
    'email-professionalism':'Please draft the email you would send, including the subject and closing.',
    "english-speaking": "Hello! Let's practise English together. Tell me a little about yourself.",
    "communication": "Hi, thanks for meeting with me. As your team lead, I noticed our priority project deliverable is running behind schedule and stakeholders are asking for an update. Could you walk me through what happened and what our next steps are? Feel free to ask if you need any context.",
    "active-listening": "Hello, thank you for taking my call. I'm really frustrated because our service has been unstable all week and it's severely impacting our clients, but nobody seems to be taking it seriously. Can you help me understand what's going on?",
    "conflict-resolution": "Hi, I wanted to speak with you directly. You've been occupying the shared testing environment all morning without coordinating with the team, and it completely blocked our deployment release. How can we resolve this fairly?",
    "negotiation": "Thanks for getting on the call. Our executive leadership has requested that we pull forward the final product delivery by two days, but we cannot reduce any of the agreed scope. How can we make this timeline work?",
    "interviews": "Welcome! We're glad to have you interviewing with us today. To start off, could you walk me through a specific time when you had to resolve a difficult conflict or roadblock within your team?",
    "presentations": "Thanks for the quick briefing. We only have a few minutes before the board meeting, and we need a clear, high-level update on where the project stands and what decisions are needed today.",
    "storytelling": "Hello! We're evaluating potential partners for our upcoming initiative, and I'd love to hear a concrete example of how your team tackled a major challenge and delivered measurable impact.",
    "critical-thinking": "Thanks for joining. We have a dilemma: Report A shows our pilot program was a massive success, while Report B claims user engagement actually dropped. How should we interpret these contradictory metrics?",
    "ai-literacy": "Hey, take a look at this: I used an AI tool to generate our customer performance report, and I'm planning to email it to external clients this afternoon. Do you have any concerns before I hit send?",
    "social-engineering": "Hi, this is urgent! I'm calling from Vice President Miller's office. Mr. Miller is in an offsite executive meeting and needs access to the production admin portal immediately. Can you bypass the two-factor authentication for us right away?",
}

SCENARIO_PARTICIPANTS = {
    "english-speaking": ["Conversation partner"],
    "communication": ["Team lead"],
    "active-listening": ["Concerned customer"],
    "conflict-resolution": ["Frustrated colleague"],
    "negotiation": ["Client"],
    "interviews": ["Hiring manager"],
    "presentations": ["Department director", "Finance lead", "Operations lead"],
    "storytelling": ["Prospective customer"],
    "critical-thinking": ["Project sponsor"],
    "ai-literacy": ["Colleague"],
    "social-engineering": ["Impatient caller"],
}

# Multiple participants are opt-in. A normal roleplay must never become a
# group call merely because more plausible characters could exist.
MULTI_AI_SKILLS = {"presentations"}

STOP_WORDS = {"the", "a", "an", "and", "or", "to", "of", "in", "is", "it", "for", "on", "that", "this", "with", "be", "as", "at", "we", "you", "i"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z'-]*", text.lower())


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


