"""Stable application errors shared across future feature routers."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


from domain.errors import DomainError


async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )
