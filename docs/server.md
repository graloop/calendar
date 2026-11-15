# Agenda on the home server

How Agenda gets from GitHub to the home server, and onto the phone. It runs as a Portainer
stack and is only reachable on the home network.

> **Home network only.** The page has no login: anyone who can open it can change the
> calendar. So **never forward port 8030 on the router**, and never point a tunnel or a public
> host name at the page. To reach it away from home, use Tailscale ([safety.md](safety.md)).
>
> **The one exception** is Claude's connector (`MCP_PLAN.md`): a separate public host name,
> `MCP_HOST`, through a Cloudflare tunnel. On it the app only answers `/mcp` and its OAuth login
> (behind a password) and a 404 to everything else, the page and `/api/*` included. It's off
> unless `MCP_ENABLED=true`.

## How it fits together

1. You push to `main` on GitHub.
2. GitHub Actions (`.github/workflows/ci.yml`) runs the tests, builds the Docker image, tries it,
   and publishes it as `ghcr.io/graloop/agenda` with three tags: `latest`, the version number
   (e.g. `1`) and `sha-<short commit>`.
3. Portainer pulls that image and runs it with `docker-compose.yml`. The calendar itself lives in
   the `agenda_data` Docker volume (`/data/agenda.db` inside the container), never in the image
   or on GitHub, so updating the app never touches it.

## 1. Publish the image (once)

1. Push to `main`. On GitHub, open the repository → **Actions** and wait for the **CI** run to go
   green (a few minutes).
2. The image is now under your profile → **Packages** → `agenda`.
3. **Make the package public.** A new ghcr.io package is private, and Portainer can't pull a
   private one without a password. The code and the image are public anyway (MIT, and your
   calendar is never in them), so the simplest is: open the `agenda` package → **Package
   settings** → **Danger Zone** → **Change visibility** → **Public**. Once is enough.

   If you'd rather keep it private: on GitHub make a token (Settings → Developer settings →
   Personal access tokens → Tokens (classic)) with only `read:packages`, then in Portainer go to
   **Registries** → **Add registry** → **GitHub** (or Custom, URL `ghcr.io`), username `graloop`,
   the token as the password.

## 2. Create the stack in Portainer

1. Open Portainer → your environment → **Stacks** → **Add stack**.
2. Name: `agenda`.
3. Pick one:
   - **Web editor**: paste the whole of [docker-compose.yml](../docker-compose.yml).
   - **Repository**: URL `https://github.com/graloop/calendar`, reference `refs/heads/main`,
     compose path `docker-compose.yml`. Portainer then reads the file from GitHub.
4. **Environment variables** (both optional):
   - `TZ` = `America/Toronto` (the default; what "today" means).
   - `TAG` = `latest` (the default). Put a version number (`1`) or `sha-abc1234` to run an
     older version.
5. **Deploy the stack**. In **Containers**, `agenda` should show **running**, then **healthy**
   after about 30 seconds (the image checks `/api/health` by itself).

## 3. Open it on the home Wi-Fi

The address is `http://<server-ip>:8030`, for example `http://192.168.1.50:8030`.

Finding the server's IP:
- It's the address you already type to open Portainer, without its port (`:9443` or `:9000`).
- Or on the server itself: `hostname -I` (Linux) and take the first number, usually
  `192.168.x.x` or `10.x.x.x`.
- Or in your router's page, under the connected devices.

Tip: in the router, give the server a fixed address (a "DHCP reservation") so it never changes
and the phone's bookmark keeps working.

Open the address on your laptop and phone, on the home Wi-Fi. The version is shown in Settings.
It's `http://`, not `https://`: that's normal on the home network.

## 4. Add it to the iPhone home screen

1. Open `http://<server-ip>:8030` in **Safari** (not Chrome: only Safari can do this on iPhone).
2. Tap **Share** (the square with an arrow) → **Add to Home Screen** → **Add**.
3. The orange loop icon opens Agenda full screen, straight on **Upcoming**.

Android: Chrome → ⋮ → **Add to Home screen**.

## 5. Updating

1. Change the code, then raise `VERSION` in `backend/app/version.py` (e.g. `"1"` → `"2"`).
2. Commit and push to `main`. Wait for the **CI** run to go green.
3. In Portainer: **Stacks** → `agenda` → **Update the stack** (or **Pull and redeploy** for a
   repository stack) with **Re-pull image** turned on → **Update**.
4. Reload the page: Settings shows the new version. Your events are still there (they're in the
   `agenda_data` volume). A new database column is added by itself at startup.

Something wrong with the new version? Set `TAG` to the previous version number in the stack's
environment variables and update the stack again.

## 6. Claude's connector (optional)

This lets Claude (claude.ai on the web, the desktop app and the phone) read and fill the calendar
through its own public host name, `agenda-mcp.graloop.com`, behind a password. The page itself
stays home-network only. What that means for safety is in [safety.md](safety.md#claudes-connector-what-is-public-and-why).

1. **Make the password's hash.** On the server, once the new image is running:

   ```sh
   docker exec -it agenda python -m app.mcp.hashpw
   ```

   Type a long password twice (at least 12 characters; nothing shows while typing). It prints
   one line starting with `scrypt$`: that's the hash, not the password. Keep the password in your
   password manager; you type it once in claude.ai.
2. **Make the tunnel.** Cloudflare Zero Trust → **Networks** → **Tunnels** → **Create a tunnel**
   → **Cloudflared**, name it `agenda`. Copy the token it shows (the long text after
   `--token`). Don't install anything: the stack runs cloudflared.
3. **Give it ONE public hostname.** In the tunnel → **Public Hostname** → **Add**:
   subdomain `agenda-mcp`, domain `graloop.com`, path `^/(mcp|oauth|\.well-known)`, service
   **HTTP** `agenda:8000`. Never add a hostname for the page itself.
4. **Optional WAF rule** (Security → WAF → Custom rules): allow `/mcp` and `/oauth/token` only
   from Anthropic's published IP ranges. Don't restrict `/oauth/authorize`: that's the password
   page, and it opens on your own phone or laptop.
5. **Stack variables in Portainer** (Stacks → `agenda` → Editor → Environment variables):
   - `MCP_ENABLED` = `true`
   - `MCP_HOST` = `agenda-mcp.graloop.com`
   - `MCP_PASSWORD_HASH` = the `scrypt$...` line from step 1
   - `CLOUDFLARE_TUNNEL_TOKEN` = the token from step 2
   - `COMPOSE_PROFILES` = `tunnel` (starts the cloudflared container)

   Then **Update the stack** with **Re-pull image and redeploy** on. In `docker logs agenda` you
   should see `Claude's connector is on at https://agenda-mcp.graloop.com/mcp`. A setting that's
   wrong is said there too, and only keeps the connector off.
6. **Check what's public.** From the phone on mobile data (Wi-Fi off):
   `https://agenda-mcp.graloop.com/` must say **Not found**, and so must `/api/events`.
   `https://agenda-mcp.graloop.com/.well-known/oauth-authorization-server` shows a few lines of
   text: that's the only kind of thing it answers.
7. **Connect claude.ai.** Settings → **Connectors** → **Add custom connector** → URL
   `https://agenda-mcp.graloop.com/mcp` → **Add**, then **Connect**. The orange Agenda page opens:
   type the password. Back in Claude, ask "Use connection_check" or "What's due this week?".
8. **Make Claude ask first.** In the connector's tool settings, set `apply_import`,
   `undo_import`, `update_event` and `delete_event` to **Needs approval**. Claude then can't save
   or delete anything without you pressing yes, whatever a message it reads says.

Typical use, in a class project: "Add every deadline from the plan de cours." Claude writes import
lines, calls `preview_import`, shows you what's new or changed, and saves with `apply_import`
only after you say yes. Each save is an import you can undo, in Claude or in Settings on the page.

## If something doesn't work

- **The page doesn't open**: is the container running in Portainer? Are you on the home Wi-Fi
  (not mobile data)? Did you type `:8030`?
- **Portainer says "pull access denied" or "unauthorized"**: the package is still private
  (step 1.3).
- **Logs**: Portainer → Containers → `agenda` → **Logs**.

## Trying the image on a laptop

To build from this folder instead of pulling from ghcr.io:

```sh
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

Then open `http://localhost:8030`.
