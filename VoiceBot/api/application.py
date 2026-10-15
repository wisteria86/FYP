"""FastAPI application factory and cross-cutting HTTP configuration."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.errors import DomainError, domain_error_handler
from config import Config


Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[AsyncIterator[Any]]]


def create_application(*, lifespan: Lifespan | None = None) -> FastAPI:
    """Build the Hikari API without importing heavyweight model providers."""

    app = FastAPI(
        title="Hikari Employee Trainer API",
        version=Config.API_VERSION,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=Config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Server-Timing", "X-Process-Time-Ms", "X-Request-Id"],
    )
    app.add_exception_handler(DomainError, domain_error_handler)
    return app
