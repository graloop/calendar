# The FastAPI app: creates the tables at startup, plugs in the API routes and
# serves the front end. Every page address (/upcoming, /week/..., /event/5...)
# answers with the same index.html; js/main.js then shows the right screen.
# With MCP_ENABLED, also Claude's connector: /mcp and its OAuth login (app/mcp/),
# reachable only through the public hostname (the guard, app/mcp/guard.py).

import logging
import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Route

from .config import get_settings
from .database import Base, add_missing_columns, engine
from .mcp import auth as mcp_auth
from .mcp import oauth as mcp_oauth
from .mcp.guard import PublicHostGuard
from .mcp.server import McpApp
from .routers import calendars, courses, events, imports, todos
from .version import VERSION

logging.basicConfig(level=logging.INFO)  # What the app says goes to `docker logs`.
log = logging.getLogger("agenda")
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # create_all only creates what's missing, so existing data is left alone.
    Base.metadata.create_all(bind=engine)
    add_missing_columns()
    calendars.set_up_calendars()  # School, Personal, Work on a new database
    # The connector: a wrong setting is said clearly in the logs, and only turns it off.
    if problem := settings.mcp_problem():
        log.error(problem)
    if mcp_auth.is_configured():
        log.info("Claude's connector is on at %s/mcp", mcp_auth.public_base())
        async with mcp_app.running():
            yield
    else:
        yield


mcp_app = McpApp()  # Claude's connector; only reachable when mounted further down


app = FastAPI(
    title="Agenda",
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)

# First of all, before any route: the public hostname reaches only the connector.
app.add_middleware(PublicHostGuard)

app.include_router(courses.router)
app.include_router(events.router)
app.include_router(calendars.router)
app.include_router(todos.router)


app.include_router(imports.router)

# Claude's connector, only with MCP_ENABLED and its settings right. Two plain
# routes rather than a mount, so /mcp answers without a redirect to /mcp/.
if mcp_auth.is_configured():
    app.include_router(mcp_oauth.router)
    _mcp_endpoint = mcp_auth.BearerAuth(mcp_app)
    app.router.routes.append(Route("/mcp", endpoint=_mcp_endpoint))
    app.router.routes.append(Route("/mcp/", endpoint=_mcp_endpoint))


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
