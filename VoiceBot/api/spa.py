"""Serve the built frontend so that page addresses such as /progress or /session/<id> survive a refresh."""
from pathlib import Path

from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

# The first part of every address the frontend router understands.
APP_PAGES = frozenset({
    'learning-path', 'training', 'progress', 'plan', 'resources', 'settings', 'monitor',
    'briefing', 'session', 'results',
})
NO_CACHE = {'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache', 'Expires': '0'}


def is_app_page(path: str) -> bool:
    # Starlette hands over an OS path, so Windows uses backslashes.
    first = path.replace('\\', '/').strip('/').split('/', 1)[0]
    return first in APP_PAGES


def index_response(dist: Path) -> FileResponse:
    return FileResponse(dist / 'index.html', headers=NO_CACHE)


class FrontendFiles(StaticFiles):
    """Static files, plus index.html for app page addresses that are not files."""

    def __init__(self, directory: Path):
        super().__init__(directory=directory, html=True)
        self.dist = Path(directory)

    async def get_response(self, path, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and is_app_page(path):
                return index_response(self.dist)
            raise
        if response.status_code == 404 and is_app_page(path):
            return index_response(self.dist)
        return response
