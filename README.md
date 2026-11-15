# Agenda

A small self-hosted school calendar: classes, labs, exams and deadlines in one place.
Events are pasted as text lines into an import box (filled by Claude in Chrome from Moodle or
email), previewed, then added. No duplicates, every import can be undone, and everything can
be edited by hand.

FastAPI, SQLite, plain HTML/CSS/JS. Runs on a home server with Docker, home network only.

Work in progress.

## Run it locally

Needs Python 3.11+ and Node (for prettier).

```sh
npm install
npm start        # same as scripts/dev.sh
```

It makes `backend/.venv` and `.env` the first time, then opens on http://127.0.0.1:8000 (only this
computer can reach it). The database is `backend/data/agenda.db`. `npm test` runs the tests,
`npm run lint` the checks.

## On the home server

Every push to `main` publishes the image `ghcr.io/graloop/agenda`; Portainer runs it with
[docker-compose.yml](docker-compose.yml) at `http://<server-ip>:8030`, on the home network only.
Never forward the port or point a public tunnel at the page: it has no login. The one exception
is Claude's connector (`MCP_PLAN.md`): a separate public hostname that only reaches `/mcp` and its
OAuth login, behind a password. The app refuses everything else on that hostname by itself.

- [docs/server.md](docs/server.md): the Portainer stack, the address on the home Wi-Fi, the phone's
  home screen, updating.
- [docs/safety.md](docs/safety.md): daily backups and restoring, reaching it away from home with
  Tailscale, and what Claude's connector makes public.
- Claude's connector (optional): [docs/server.md](docs/server.md#6-claudes-connector-optional) step 6,
  and the plan it follows, [MCP_PLAN.md](MCP_PLAN.md).

## Settings

Set in `.env` on the laptop, or as the stack's environment variables in Portainer.

| Variable | Default | Meaning |
|---|---|---|
| `DATA_DIR` | `./data` (`/data` in the container) | Where `agenda.db` lives |
| `TZ` | `America/Toronto` | The timezone dates and times are in |
| `ENABLE_API_DOCS` | `false` | Swagger at `/docs` |
| `MCP_ENABLED` | `false` | Mounts `/mcp` and the OAuth routes only when true |
| `MCP_HOST` | `""` | The connector's public hostname, e.g. `agenda-mcp.graloop.com`. Required when enabled |
| `MCP_PASSWORD_HASH` | `""` | scrypt hash of the connector password, from `python -m app.mcp.hashpw`. Never the password |
| `MCP_TOKEN_DAYS` | `30` | How long Claude stays connected (refresh token). Access tokens last 1 h |

## License

MIT, see [LICENSE](LICENSE).
