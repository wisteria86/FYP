import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from api.application import create_application
from api.routers.auth import build_auth_router
from config import Config
from core.training_service import TrainingService
from services.auth_service import AuthService


class AuthApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name) / "auth.db"
        TrainingService(path)
        self.service = AuthService(path, session_hours=1)
        app = create_application()
        app.include_router(build_auth_router(self.service))
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_register_login_me_and_logout(self):
        registered = self.client.post(
            "/api/auth/register",
            json={
                "name": "Ayesha Khan",
                "email": "ayesha@example.com",
                "password": "training123",
                "organization_name": "Example Company",
            },
        )
        self.assertEqual(registered.status_code, 201)
        self.assertEqual(registered.json()["user"]["email"], "ayesha@example.com")
        self.assertIn(Config.AUTH_COOKIE_NAME, registered.cookies)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)

        logged_out = self.client.post("/api/auth/logout")
        self.assertEqual(logged_out.status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

        logged_in = self.client.post(
            "/api/auth/login",
            json={"email": "AYESHA@example.com", "password": "training123"},
        )
        self.assertEqual(logged_in.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").json()["user"]["name"], "Ayesha Khan")

    def test_rejects_duplicate_email_and_bad_password(self):
        payload = {
            "name": "Ayesha Khan",
            "email": "ayesha@example.com",
            "password": "training123",
        }
        self.assertEqual(self.client.post("/api/auth/register", json=payload).status_code, 201)
        duplicate = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()["error"]["code"], "email_exists")
        invalid = self.client.post(
            "/api/auth/login",
            json={"email": payload["email"], "password": "wrong-password"},
        )
        self.assertEqual(invalid.status_code, 401)

    def test_profile_password_and_preferences_persist(self):
        self.client.post(
            "/api/auth/register",
            json={"name": "Ayesha Khan", "email": "ayesha@example.com", "password": "training123"},
        )
        profile = self.client.put("/api/auth/profile", json={"name": "Ayesha Ahmed"})
        self.assertEqual(profile.json()["user"]["name"], "Ayesha Ahmed")

        settings = self.client.put(
            "/api/auth/settings", json={
                "preferred_language": "English", "native_language": "Japanese",
                "proficiency_level": "beginner", "captions_enabled": False,
            }
        )
        self.assertEqual(settings.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/settings").json()["native_language"], "Japanese")
        self.assertFalse(self.client.get("/api/auth/settings").json()["captions_enabled"])

        changed = self.client.post(
            "/api/auth/password",
            json={"current_password": "training123", "new_password": "updated456"},
        )
        self.assertEqual(changed.status_code, 204)
        self.client.post("/api/auth/logout")
        self.assertEqual(
            self.client.post(
                "/api/auth/login", json={"email": "ayesha@example.com", "password": "updated456"}
            ).status_code,
            200,
        )


if __name__ == "__main__":
    unittest.main()
