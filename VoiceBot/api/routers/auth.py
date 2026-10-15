"""Account and browser-session endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, HTTPException, Response

from api.schemas import LoginRequest, PasswordChange, ProfileUpdate, RegisterRequest, UserSettingsUpdate
from config import Config
from services.auth_service import AuthService


def build_auth_router(service: AuthService) -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["authentication"])

    def set_cookie(response: Response, token: str) -> None:
        response.set_cookie(
            Config.AUTH_COOKIE_NAME,
            token,
            max_age=Config.AUTH_SESSION_HOURS * 3600,
            httponly=True,
            secure=Config.APP_ENV == "production",
            samesite="lax",
            path="/",
        )

    def require_user(token: str | None) -> dict:
        user = service.user_for_token(token)
        if not user:
            raise HTTPException(401, "Authentication required")
        return user

    @router.post("/register", status_code=201)
    def register(request: RegisterRequest, response: Response):
        user, token = service.register(request.name, request.email, request.password, request.organization_name)
        set_cookie(response, token)
        return {"user": user}

    @router.post("/login")
    def login(request: LoginRequest, response: Response):
        user, token = service.authenticate(request.email, request.password)
        set_cookie(response, token)
        return {"user": user}

    @router.post("/logout", status_code=204)
    def logout(response: Response, hikari_session: str | None = Cookie(default=None, alias=Config.AUTH_COOKIE_NAME)):
        service.revoke(hikari_session)
        response.delete_cookie(Config.AUTH_COOKIE_NAME, path="/")

    @router.get("/me")
    def me(hikari_session: str | None = Cookie(default=None, alias=Config.AUTH_COOKIE_NAME)):
        return {"user": require_user(hikari_session)}

    @router.put("/profile")
    def update_profile(request: ProfileUpdate, hikari_session: str | None = Cookie(default=None, alias=Config.AUTH_COOKIE_NAME)):
        user = require_user(hikari_session)
        return {"user": service.update_profile(user["id"], request.name)}

    @router.post("/password", status_code=204)
    def change_password(request: PasswordChange, hikari_session: str | None = Cookie(default=None, alias=Config.AUTH_COOKIE_NAME)):
        user = require_user(hikari_session)
        service.change_password(user["id"], request.current_password, request.new_password)

    @router.get("/settings")
    def get_settings(hikari_session: str | None = Cookie(default=None, alias=Config.AUTH_COOKIE_NAME)):
        user = require_user(hikari_session)
        return service.settings(user["id"])

    @router.put("/settings")
    def update_settings(request: UserSettingsUpdate, hikari_session: str | None = Cookie(default=None, alias=Config.AUTH_COOKIE_NAME)):
        user = require_user(hikari_session)
        return service.update_settings(
            user["id"], request.preferred_language, request.native_language,
            request.proficiency_level, request.captions_enabled,
        )

    return router
