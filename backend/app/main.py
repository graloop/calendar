# The FastAPI app: creates the tables at startup, plugs in the API routes and
# serves the front end. Every page address (/upcoming, /week/..., /event/5...)
# answers with the same index.html; js/main.js then shows the right screen.

import logging
import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import Base, add_missing_columns, engine
from .routers import courses, events, imports
from .version import VERSION

logging.basicConfig(level=logging.INFO)  # What the app says goes to `docker logs`.
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # create_all only creates what's missing, so existing data is left alone.
    Base.metadata.create_all(bind=engine)
    add_missing_columns()
    yield


app = FastAPI(
    title="Agenda",
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)

app.include_router(courses.router)
app.include_router(events.router)
app.include_router(imports.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


class RevalidatingStaticFiles(StaticFiles):
    """Make browsers re-check the front end on every load (a cheap 304 when
    unchanged), so an updated script is never hidden by the cache."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
# src="/js/main.js", href="/css/base.css": the page's own scripts and stylesheets.
_LOCAL_ASSET = re.compile(r'(src|href)="/([\w/.-]+\.(?:js|css))"')


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
@app.get("/upcoming", include_in_schema=False)
@app.get("/week", include_in_schema=False)
@app.get("/week/{day}", include_in_schema=False)
@app.get("/month", include_in_schema=False)
@app.get("/month/{month}", include_in_schema=False)
@app.get("/event/{event_id}", include_in_schema=False)
@app.get("/import", include_in_schema=False)
def index():
    """index.html with ?v=<mtime> on the files it links: any change gives a new
    URL, so no browser can keep running a stale copy."""
    with open(os.path.join(_FRONTEND_DIR, "index.html"), encoding="utf-8") as f:
        html = f.read()

    def versioned(match: re.Match) -> str:
        path = match.group(2)
        version = int(os.path.getmtime(os.path.join(_FRONTEND_DIR, path)))
        return f'{match.group(1)}="/{path}?v={version}"'

    html = _LOCAL_ASSET.sub(versioned, html).replace("__APP_VERSION__", VERSION)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


app.mount("/", RevalidatingStaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
