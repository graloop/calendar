# Agenda on the home server

How Agenda gets from GitHub to the home server, and onto the phone. It runs as a Portainer
stack and is only reachable on the home network.

> **Home network only.** The app has no logins: anyone who can open the page can change the
> calendar. So **never forward port 8030 on the router**, no Cloudflare tunnel, no public host
> name. To reach it away from home, use Tailscale ([safety.md](safety.md)), nothing else.

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
