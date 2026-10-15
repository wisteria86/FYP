"""Local account authentication with scrypt passwords and revocable sessions."""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from config import Config

from domain.errors import DomainError
from database.connection import connect_database
from database.migration_runner import run_migrations


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def _password_matches(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt),
            n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(expected)),
        )
        return secrets.compare_digest(digest.hex(), expected)
    except (TypeError, ValueError):
        return False


class AuthService:
    def __init__(self, database_path: str | Path, session_hours: int = 168):
        self.path = Path(database_path)
        self.session_hours = max(1, session_hours)
        run_migrations(self.path)

    def connect(self) -> sqlite3.Connection:
        return connect_database(self.path)

    @staticmethod
    def _public_user(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "role": row["role"],
            "organization": row["organization"],
            "status": row["status"],
            "is_admin": (row["email"] or '').lower() in Config.ADMIN_EMAILS,
        }

    def register(self, name: str, email: str, password: str, organization_name: str | None = None) -> tuple[dict, str]:
        name = " ".join(name.split()).strip()
        email = email.strip().lower()
        organization_name = " ".join((organization_name or f"{name}'s Workspace").split()).strip()
        if len(name) < 2:
            raise DomainError("invalid_name", "Enter your full name.", status_code=422)
        if not EMAIL_PATTERN.match(email):
            raise DomainError("invalid_email", "Enter a valid email address.", status_code=422)
        if len(password) < 10 or not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
            raise DomainError(
                "weak_password", "Use at least 10 characters with a letter and a number.", status_code=422
            )
        user_id, organization_id = str(uuid.uuid4()), str(uuid.uuid4())
        now = _now()
        try:
            with self.connect() as db:
                db.execute(
                    "INSERT INTO organizations(id,name,slug,created_at,updated_at) VALUES (?,?,?,?,?)",
                    (organization_id, organization_name, f"org-{organization_id[:12]}", _iso(now), _iso(now)),
                )
                db.execute(
                    """INSERT INTO users(
                        id,name,role,organization,created_at,email,password_hash,status,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        user_id, name, "Learner", organization_name, _iso(now), email,
                        _password_hash(password), "active", _iso(now),
                    ),
                )
                db.execute(
                    "INSERT INTO organization_memberships VALUES (?,?,?,?)",
                    (organization_id, user_id, "owner", _iso(now)),
                )
                db.execute("INSERT INTO user_settings(user_id,updated_at) VALUES (?,?)", (user_id, _iso(now)))
                db.execute(
                    """INSERT INTO proficiency(user_id,skill_id,score,sessions,updated_at)
                    SELECT ?,id,50,0,? FROM skill_catalog""",
                    (user_id, _iso(now)),
                )
                db.execute(
                    """INSERT INTO subskill_proficiency(user_id,skill_id,subskill,score,sessions,updated_at)
                    SELECT ?,skill_id,name,50,0,? FROM subskill_catalog""",
                    (user_id, _iso(now)),
                )
                row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        except sqlite3.IntegrityError as exc:
            if "email" in str(exc).lower() or "idx_users_email" in str(exc).lower():
                raise DomainError("email_exists", "An account with this email already exists.", status_code=409) from exc
            raise
        token = self.create_session(user_id)
        return self._public_user(row), token

    def authenticate(self, email: str, password: str) -> tuple[dict, str]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE lower(email)=?", (email.strip().lower(),)).fetchone()
        if not row or row["status"] != "active" or not _password_matches(password, row["password_hash"]):
            raise DomainError("invalid_credentials", "Email or password is incorrect.", status_code=401)
        return self._public_user(row), self.create_session(row["id"])

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = _now()
        with self.connect() as db:
            db.execute(
                """INSERT INTO auth_sessions(
                    id,user_id,token_hash,expires_at,created_at,last_seen_at
                ) VALUES (?,?,?,?,?,?)""",
                (
                    str(uuid.uuid4()), user_id, _token_hash(token),
                    _iso(now + timedelta(hours=self.session_hours)), _iso(now), _iso(now),
                ),
            )
        return token

    def user_for_token(self, token: str | None) -> dict | None:
        if not token:
            return None
        now = _now()
        with self.connect() as db:
            row = db.execute(
                """SELECT u.*,a.last_seen_at auth_last_seen FROM auth_sessions a
                JOIN users u ON u.id=a.user_id
                WHERE a.token_hash=? AND a.revoked_at IS NULL AND a.expires_at>? AND u.status='active'""",
                (_token_hash(token), _iso(now)),
            ).fetchone()
            if row and row['auth_last_seen'] < _iso(now-timedelta(minutes=1)):
                db.execute(
                    "UPDATE auth_sessions SET last_seen_at=? WHERE token_hash=?",
                    (_iso(now), _token_hash(token)),
                )
        return self._public_user(row) if row else None

    def revoke(self, token: str | None) -> None:
        if not token:
            return
        with self.connect() as db:
            db.execute(
                "UPDATE auth_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                (_iso(_now()), _token_hash(token)),
            )

    def update_profile(self, user_id: str, name: str) -> dict:
        name = " ".join(name.split()).strip()
        if len(name) < 2:
            raise DomainError("invalid_name", "Enter your full name.", status_code=422)
        with self.connect() as db:
            db.execute("UPDATE users SET name=?,updated_at=? WHERE id=?", (name, _iso(_now()), user_id))
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise DomainError("user_not_found", "Account not found.", status_code=404)
        return self._public_user(row)

    def change_password(self, user_id: str, current_password: str, new_password: str) -> None:
        if len(new_password) < 10 or not any(c.isalpha() for c in new_password) or not any(c.isdigit() for c in new_password):
            raise DomainError("weak_password", "Use at least 10 characters with a letter and a number.", status_code=422)
        with self.connect() as db:
            row = db.execute("SELECT password_hash FROM users WHERE id=?", (user_id,)).fetchone()
            if not row or not _password_matches(current_password, row["password_hash"]):
                raise DomainError("invalid_password", "Current password is incorrect.", status_code=401)
            db.execute(
                "UPDATE users SET password_hash=?,updated_at=? WHERE id=?",
                (_password_hash(new_password), _iso(_now()), user_id),
            )

    def settings(self, user_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM user_settings WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            raise DomainError("settings_not_found", "Account settings were not found.", status_code=404)
        return {
            "preferred_language": row["preferred_language"],
            "native_language": row["native_language"],
            "proficiency_level": row["proficiency_level"],
            "captions_enabled": bool(row["captions_enabled"]),
        }

    def update_settings(self, user_id: str, preferred_language: str, native_language: str,
                        proficiency_level: str, captions_enabled: bool) -> dict:
        with self.connect() as db:
            db.execute(
                """UPDATE user_settings SET preferred_language=?,native_language=?,proficiency_level=?,
                captions_enabled=?,updated_at=?
                WHERE user_id=?""",
                (preferred_language, native_language, proficiency_level, int(captions_enabled), _iso(_now()), user_id),
            )
        return self.settings(user_id)
