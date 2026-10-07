"""Serve the built React app after normal API routes have been matched."""
import os
from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        # Unknown API endpoints must remain JSON 404s, never an HTML app shell.
        if path.split('/')[0] in {'api', 'docs', 'redoc', 'openapi.json'}:
            raise HTTPException(404)
        try:
            response = await super().get_response(path, scope)
            if response.status_code != 404:
                if path in {'.', '', 'index.html'}:
                    response.headers['Cache-Control'] = 'no-cache'
                return response
        except HTTPException as error:
            if error.status_code != 404:
                raise

        accept = dict(scope['headers']).get(b'accept', b'').decode()
        # Fall back only for browser navigation, not missing scripts/images.
        if (scope['method'] in {'GET', 'HEAD'}
                and ('text/html' in accept or 'application/xhtml+xml' in accept)
                and not Path(path).suffix
                and '..' not in Path(path).parts):
            return FileResponse(Path(self.directory) / 'index.html',
                                headers={'Cache-Control': 'no-cache'})
        raise HTTPException(404)


def mount_frontend(app: FastAPI, directory: Path | None = None):
    configured = os.getenv('FRONTEND_DIST')
    directory = directory or Path(configured or Path(__file__).resolve().parent.parent / 'static')
    if not (directory / 'index.html').is_file():
        if configured:
            raise RuntimeError(f'FRONTEND_DIST is missing its index.html: {directory}')
        return  # Local development uses the independent Vite dev server.
    app.mount('/', FrontendFiles(directory=str(directory), html=True), name='frontend')
