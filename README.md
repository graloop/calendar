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
Never forward the port or put it behind a public tunnel: the app has no logins.

- [docs/server.md](docs/server.md): the Portainer stack, the address on the home Wi-Fi, the phone's
  home screen, updating.
- [docs/safety.md](docs/safety.md): daily backups and restoring, reaching it away from home with
  Tailscale.

## License

MIT, see [LICENSE](LICENSE).
