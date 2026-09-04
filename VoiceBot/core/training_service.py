"""Persistent training domain for the Hikari prototype.

The service deliberately uses Python's built-in SQLite support so the prototype
remains easy to run on a student laptop and does not add another server.
"""
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


SKILLS = [
    ("communication", "Workplace Communication", "Practice clear, concise and professional conversations.", ["clarity", "professionalism", "conciseness"]),
    ("active-listening", "Active Listening", "Understand, confirm and respond to what colleagues need.", ["acknowledgement", "clarifying questions", "summarising"]),
    ("conflict-resolution", "Conflict Resolution", "De-escalate disagreement and find workable next steps.", ["empathy", "de-escalation", "problem solving"]),
    ("negotiation", "Negotiation", "Reach fair agreements while protecting key priorities.", ["discovery", "trade-offs", "closing"]),
    ("interviews", "Job Interviews", "Give relevant, evidence-led answers with confidence.", ["relevance", "STAR evidence", "confidence"]),
    ("presentations", "Presentations", "Explain ideas with structure, pace and audience awareness.", ["structure", "delivery", "audience focus"]),
    ("storytelling", "Professional Storytelling", "Make workplace examples memorable and purposeful.", ["narrative", "evidence", "impact"]),
    ("critical-thinking", "Critical Thinking", "Question assumptions and make evidence-based decisions.", ["analysis", "evidence", "judgement"]),
    ("ai-literacy", "Responsible AI Use", "Use AI safely, critically and transparently at work.", ["verification", "privacy", "transparency"]),
    ("social-engineering", "Social Engineering Awareness", "Recognise and safely respond to manipulation attempts.", ["risk recognition", "verification", "reporting"]),
]

SCENARIOS = {
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

STOP_WORDS = {"the", "a", "an", "and", "or", "to", "of", "in", "is", "it", "for", "on", "that", "this", "with", "be", "as", "at", "we", "you", "i"}


class ClosingConnection(sqlite3.Connection):
    """Make ``with connection`` release Windows file handles as callers expect."""
    def __exit__(self, exc_type, exc_value, traceback):
        result = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z'-]*", text.lower())


class TrainingService:
    def __init__(self, database_path: str | Path):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=20, factory=ClosingConnection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
                    organization TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, skill_id TEXT NOT NULL,
                    difficulty TEXT NOT NULL, title TEXT NOT NULL, situation TEXT NOT NULL,
                    counterpart TEXT NOT NULL, objectives TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, completed_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                    role TEXT NOT NULL, text TEXT NOT NULL, duration_seconds REAL DEFAULT 0,
                    created_at TEXT NOT NULL, FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                CREATE TABLE IF NOT EXISTS assessments (
                    id TEXT PRIMARY KEY, session_id TEXT UNIQUE NOT NULL, overall REAL NOT NULL,
                    scores TEXT NOT NULL, strengths TEXT NOT NULL, improvements TEXT NOT NULL,
                    evidence TEXT NOT NULL, feedback TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS proficiency (
                    user_id TEXT NOT NULL, skill_id TEXT NOT NULL, score REAL NOT NULL,
                    sessions INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, skill_id)
                );
                CREATE TABLE IF NOT EXISTS subskill_proficiency (
                    user_id TEXT NOT NULL, skill_id TEXT NOT NULL, subskill TEXT NOT NULL,
                    score REAL NOT NULL, sessions INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, skill_id, subskill)
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL,
                    content TEXT NOT NULL, chunks TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS posture (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                    slouching REAL, head_position REAL, shoulder_alignment REAL,
                    body_orientation REAL, created_at TEXT NOT NULL
                );
            """)
            db.execute(
                "INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?)",
                ("demo", "Demo Learner", "Employee", "Hikari Demo", _now()),
            )
            for skill_id, *_ in SKILLS:
                db.execute(
                    "INSERT OR IGNORE INTO proficiency VALUES (?, ?, ?, 0, ?)",
                    ("demo", skill_id, 50.0, _now()),
                )
            for skill_id, _, _, subskills in SKILLS:
                for subskill in subskills:
                    db.execute("INSERT OR IGNORE INTO subskill_proficiency VALUES (?,?,?,50,0,?)", ("demo", skill_id, subskill, _now()))

    def skills(self, user_id: str = "demo") -> list[dict[str, Any]]:
        with self.connect() as db:
            values = {r["skill_id"]: dict(r) for r in db.execute("SELECT * FROM proficiency WHERE user_id=?", (user_id,))}
            subvalues = {(r["skill_id"], r["subskill"]): r["score"] for r in db.execute("SELECT * FROM subskill_proficiency WHERE user_id=?", (user_id,))}
        return [
            {"id": sid, "name": name, "description": desc, "subskills": subskills,
             "subskill_scores": {sub: round(subvalues.get((sid, sub), 50), 1) for sub in subskills},
             "score": round(values.get(sid, {}).get("score", 50), 1), "sessions": values.get(sid, {}).get("sessions", 0)}
            for sid, name, desc, subskills in SKILLS
        ]

    def create_session(self, user_id: str, skill_id: str, difficulty: str) -> dict[str, Any]:
        if skill_id not in SCENARIOS:
            raise ValueError("Unknown skill")
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
                raise ValueError("Unknown user")
        difficulty = difficulty if difficulty in {"beginner", "intermediate", "advanced"} else "intermediate"
        title, situation, counterpart, objectives = SCENARIOS[skill_id]
        prior = next((s for s in self.skills(user_id) if s["id"] == skill_id), None)
        if prior and prior["sessions"]:
            weakest = min(prior["subskills"], key=lambda sub: prior["subskill_scores"][sub])
            situation += f" Focus especially on improving {weakest}."
        sid = str(uuid.uuid4())
        with self.connect() as db:
            db.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, NULL)",
                (sid, user_id, skill_id, difficulty, title, situation, counterpart, _json(objectives), _now()),
            )
        return self.session(sid)

    def session(self, session_id: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if not row:
                raise ValueError("Session not found")
            result = dict(row)
            result["objectives"] = json.loads(result["objectives"])
            result["turns"] = [dict(r) for r in db.execute("SELECT role,text,duration_seconds,created_at FROM turns WHERE session_id=? ORDER BY id", (session_id,))]
            assessment = db.execute("SELECT * FROM assessments WHERE session_id=?", (session_id,)).fetchone()
            result["assessment"] = self._assessment_dict(assessment) if assessment else None
            return result

    def add_turn(self, session_id: str, role: str, text: str, duration_seconds: float = 0) -> None:
        if role not in {"user", "assistant"} or not text.strip():
            raise ValueError("Invalid turn")
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM sessions WHERE id=? AND status='active'", (session_id,)).fetchone():
                raise ValueError("Active session not found")
            db.execute("INSERT INTO turns(session_id,role,text,duration_seconds,created_at) VALUES (?,?,?,?,?)", (session_id, role, text.strip(), max(0, duration_seconds), _now()))

    def prompt(self, session_id: str, knowledge: list[dict[str, str]] | None = None) -> str:
        session = self.session(session_id)
        transcript = "\n".join(f"{t['role']}: {t['text']}" for t in session["turns"][-10:])
        sources = "\n".join(f"[{x['name']}] {x['text']}" for x in (knowledge or []))
        return (
            "You are Hikari, acting as the workplace counterpart in a spoken training roleplay. "
            "Stay in character, reply in natural English in no more than 18 words, advance the scenario, "
            "and output only the words the counterpart should say. Never output analysis, reasoning, or think tags, "
            "and do not score or coach until the session ends.\n"
            f"Role: {session['counterpart']}\nSituation: {session['situation']}\n"
            f"Learner objectives: {', '.join(session['objectives'])}\n"
            f"Authorised organization context (use only if relevant):\n{sources or 'None'}\n"
            f"Conversation so far:\n{transcript or 'No turns yet. Open the roleplay in character.'}"
        )

    def fallback_reply(self, session_id: str) -> str:
        session = self.session(session_id)
        user_turns = [t["text"] for t in session["turns"] if t["role"] == "user"]
        if not user_turns:
            return f"Hello, I'm your {session['counterpart'].lower()}. {session['situation']} How would you handle this?"
        count = len(user_turns)
        prompts = [
            "I understand your point, but what specific action do you want us to take next?",
            "What evidence or example supports that, and how does it affect the other people involved?",
            "That helps. Can you summarise the agreement, owner, and deadline before we finish?",
        ]
        return prompts[min(count - 1, len(prompts) - 1)]

    def assess(self, session_id: str) -> dict[str, Any]:
        session = self.session(session_id)
        if session["assessment"]:
            return session["assessment"]
        user_turns = [t for t in session["turns"] if t["role"] == "user"]
        text = " ".join(t["text"] for t in user_turns)
        words = _words(text)
        word_count = len(words)
        spoken_seconds = sum(float(t.get("duration_seconds") or 0) for t in user_turns)
        words_per_minute = round(word_count / spoken_seconds * 60) if spoken_seconds >= 1 else None
        pace_score = max(35, 95 - abs(words_per_minute - 135) * .45) if words_per_minute else 70
        unique_ratio = len(set(words)) / max(1, word_count)
        filler_count = sum(words.count(w) for w in ("um", "uh", "like", "basically", "actually"))
        question_count = text.count("?")
        evidence_hits = sum(1 for w in ("because", "example", "result", "data", "evidence") if w in words)
        next_hits = sum(1 for w in ("next", "will", "deadline", "agree", "plan") if w in words)
        empathy_hits = sum(1 for phrase in ("understand", "appreciate", "sorry", "concern", "thank") if phrase in words)
        scores = {
            "clarity": min(96, 38 + min(word_count, 100) * .35 + unique_ratio * 24),
            "relevance": min(96, 48 + evidence_hits * 8 + next_hits * 5),
            "professionalism": min(96, 55 + empathy_hits * 7 - filler_count * 2),
            "active_listening": min(96, 45 + empathy_hits * 8 + question_count * 8),
            "delivery": max(30, min(96, pace_score - filler_count * 5 + min(len(user_turns), 4) * 3)),
        }
        if word_count < 12:
            scores["clarity"] = min(scores["clarity"], 52)
            scores["relevance"] = min(scores["relevance"], 50)
        with self.connect() as db:
            posture = db.execute("SELECT AVG((slouching+head_position+shoulder_alignment+body_orientation)/4.0) score FROM posture WHERE session_id=?", (session_id,)).fetchone()["score"]
        if posture is not None:
            scores["posture"] = posture
        scores = {k: round(max(0, min(100, v)), 1) for k, v in scores.items()}
        overall = round(sum(scores.values()) / len(scores), 1)
        ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        strengths = [f"{name.replace('_', ' ').title()} was a relative strength ({score:.0f}/100)." for name, score in ordered[:2]]
        improvements = [f"Improve {name.replace('_', ' ')} by using one clear example and an explicit next step." for name, _ in ordered[-2:]]
        pace_evidence = f" Estimated speaking pace was {words_per_minute} words per minute." if words_per_minute else " Type-only turns were assessed without speaking pace."
        evidence = [f"You contributed {len(user_turns)} response(s) containing {word_count} words.{pace_evidence}", f"Detected {filler_count} filler word(s), {question_count} question(s), and {evidence_hits} evidence cue(s)."]
        feedback = "Good foundation. " + ("Move to a harder scenario next." if overall >= 75 else "Repeat this skill with clearer evidence and a specific close.")
        assessment_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO assessments VALUES (?,?,?,?,?,?,?,?,?)", (assessment_id, session_id, overall, _json(scores), _json(strengths), _json(improvements), _json(evidence), feedback, _now()))
            db.execute("UPDATE sessions SET status='completed', completed_at=? WHERE id=?", (_now(), session_id))
            current = db.execute("SELECT score,sessions FROM proficiency WHERE user_id=? AND skill_id=?", (session["user_id"], session["skill_id"])).fetchone()
            previous, count = (current["score"], current["sessions"]) if current else (50, 0)
            updated = round(previous * .65 + overall * .35, 1) if count else overall
            db.execute("INSERT INTO proficiency VALUES (?,?,?,?,?) ON CONFLICT(user_id,skill_id) DO UPDATE SET score=excluded.score,sessions=excluded.sessions,updated_at=excluded.updated_at", (session["user_id"], session["skill_id"], updated, count + 1, _now()))
            skill_meta = next(item for item in SKILLS if item[0] == session["skill_id"])
            rubric_values = list(scores.values())
            for index, subskill in enumerate(skill_meta[3]):
                row = db.execute("SELECT score,sessions FROM subskill_proficiency WHERE user_id=? AND skill_id=? AND subskill=?", (session["user_id"], session["skill_id"], subskill)).fetchone()
                prior_score, prior_count = (row["score"], row["sessions"]) if row else (50, 0)
                observed = rubric_values[index % len(rubric_values)]
                new_score = round(prior_score * .65 + observed * .35, 1) if prior_count else observed
                db.execute("INSERT INTO subskill_proficiency VALUES (?,?,?,?,?,?) ON CONFLICT(user_id,skill_id,subskill) DO UPDATE SET score=excluded.score,sessions=excluded.sessions,updated_at=excluded.updated_at", (session["user_id"], session["skill_id"], subskill, new_score, prior_count + 1, _now()))
        return self.session(session_id)["assessment"]

    @staticmethod
    def _assessment_dict(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for key in ("scores", "strengths", "improvements", "evidence"):
            result[key] = json.loads(result[key])
        return result

    def dashboard(self, user_id: str = "demo") -> dict[str, Any]:
        skills = self.skills(user_id)
        with self.connect() as db:
            rows = db.execute("SELECT s.id,s.title,s.skill_id,s.completed_at,a.overall FROM sessions s LEFT JOIN assessments a ON a.session_id=s.id WHERE s.user_id=? AND s.status='completed' ORDER BY s.completed_at DESC LIMIT 8", (user_id,)).fetchall()
        practiced = [s for s in skills if s["sessions"]]
        overall = round(sum(s["score"] for s in practiced) / len(practiced), 1) if practiced else 50.0
        weakest = min(skills, key=lambda s: s["score"])
        difficulty = "advanced" if weakest["score"] >= 80 else "intermediate" if weakest["score"] >= 60 else "beginner"
        return {"user": {"id": user_id, "name": "Demo Learner"}, "overall": overall, "completed_sessions": sum(s["sessions"] for s in skills), "skills": skills, "recent_sessions": [dict(r) for r in rows], "recommendation": {"skill_id": weakest["id"], "skill": weakest["name"], "difficulty": difficulty, "reason": f"Your {weakest['name']} score is currently {weakest['score']:.0f}/100, making it the best next area to practise."}, "plan": self.plan(skills)}

    @staticmethod
    def plan(skills: list[dict[str, Any]]) -> list[dict[str, str]]:
        chosen = sorted(skills, key=lambda x: (x["score"], x["sessions"]))[:3]
        return [{"day": f"Session {i + 1}", "skill_id": s["id"], "activity": s["name"], "focus": s["subskills"][i % len(s["subskills"])]} for i, s in enumerate(chosen)]

    def history(self, user_id: str = "demo") -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT s.id,s.title,s.skill_id,s.difficulty,s.status,s.created_at,s.completed_at,a.overall FROM sessions s LEFT JOIN assessments a ON a.session_id=s.id WHERE s.user_id=? ORDER BY s.created_at DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def add_document(self, user_id: str, name: str, content: str) -> dict[str, Any]:
        clean = re.sub(r"\s+", " ", content).strip()
        if not clean:
            raise ValueError("No readable text found")
        chunks = [clean[i:i + 900] for i in range(0, len(clean), 750)][:200]
        doc_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO documents VALUES (?,?,?,?,?,'ready',?)", (doc_id, user_id, name, clean, _json(chunks), _now()))
        return {"id": doc_id, "name": name, "status": "ready", "chunks": len(chunks), "created_at": _now()}

    def documents(self, user_id: str = "demo") -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT id,name,status,created_at,json_array_length(chunks) chunks FROM documents WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def delete_document(self, document_id: str, user_id: str = "demo") -> bool:
        with self.connect() as db:
            return db.execute("DELETE FROM documents WHERE id=? AND user_id=?", (document_id, user_id)).rowcount > 0

    def search(self, query: str, user_id: str = "demo", limit: int = 3) -> list[dict[str, str]]:
        query_terms = Counter(w for w in _words(query) if w not in STOP_WORDS)
        with self.connect() as db:
            docs = db.execute("SELECT name,chunks FROM documents WHERE user_id=? AND status='ready'", (user_id,)).fetchall()
        matches = []
        for doc in docs:
            for chunk in json.loads(doc["chunks"]):
                terms = Counter(w for w in _words(chunk) if w not in STOP_WORDS)
                score = sum(min(count, terms.get(term, 0)) * math.log(2 + len(chunk) / 200) for term, count in query_terms.items())
                if score:
                    matches.append((score, {"name": doc["name"], "text": chunk}))
        return [item for _, item in sorted(matches, key=lambda x: x[0], reverse=True)[:limit]]

    def add_posture(self, session_id: str, values: dict[str, float]) -> None:
        scores = [max(0, min(100, float(values.get(k, 0)))) for k in ("slouching", "head_position", "shoulder_alignment", "body_orientation")]
        with self.connect() as db:
            db.execute("INSERT INTO posture(session_id,slouching,head_position,shoulder_alignment,body_orientation,created_at) VALUES (?,?,?,?,?,?)", (session_id, *scores, _now()))
