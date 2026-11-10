# Keeping Agenda safe

Two things: a daily backup of the calendar, and reaching it away from home without putting it on
the internet.

## Backups

The whole calendar is one file, `/data/agenda.db`, in the `agenda_data` Docker volume.
[scripts/backup.sh](../scripts/backup.sh) makes a copy of it:

- It asks SQLite for the copy (its backup API), so it's safe while the app is running.
- The copy is `agenda-YYYY-MM-DD.db`, in `/data/backups` inside the volume, and also in a folder
  you choose outside Docker. Only the newest 14 are kept in each (change it with a second
  argument).
- The server only needs Docker: the script runs Python inside the `agenda` container.

### Set it up (once, on the server)

1. Get the script onto the server, e.g. `git clone https://github.com/graloop/calendar.git ~/agenda`
   (later, `git -C ~/agenda pull` updates it).
2. Pick a backup folder, ideally on another disk or a NAS share: e.g. `/mnt/backups/agenda`.
3. Try it by hand (`sudo` if your user can't run `docker`):

   ```sh
   ~/agenda/scripts/backup.sh /mnt/backups/agenda
   ```

   It should say `Backed up to /data/backups/agenda-2026-11-10.db` and list the backups copied.
4. Run it every day with cron: `crontab -e` (or `sudo crontab -e`), then add this line, with your
   paths:

   ```
   15 3 * * * /home/me/agenda/scripts/backup.sh /mnt/backups/agenda >> /home/me/agenda-backup.log 2>&1
   ```

   That's every day at 3:15. Check `agenda-backup.log` the next day.

A backup that only lives on the same disk dies with the disk: copy the folder somewhere else
from time to time (a USB drive, another computer, a cloud drive).

### Restore a backup

1. In Portainer: **Stacks** → `agenda` → **Stop this stack**. (The app must not be writing while
   the file is replaced.)
2. On the server, put the backup back into the volume. This runs the Agenda image just to copy
   the file, as the app's own user, so the app can still write to it afterwards:

   ```sh
   docker run --rm --entrypoint cp \
     -v agenda_data:/data -v /mnt/backups/agenda:/backup:ro \
     ghcr.io/graloop/agenda:latest /backup/agenda-2026-11-09.db /data/agenda.db
   ```

   (Change the folder and the date to the backup you want.)
3. In Portainer: **Start this stack**. Open the app: the calendar is as it was that day.

Only undoing one bad import? No need for a backup: use **Undo** in Settings → past imports.

## Away from home: Tailscale only

[Tailscale](https://tailscale.com) makes a private network between your own devices (your
"tailnet"). The phone reaches the server through it from anywhere, and nobody else can.
Nothing is opened on the router.

1. Make a free Tailscale account.
2. On the server, install Tailscale and connect it (Linux):

   ```sh
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```

   Open the link it prints and sign in.
3. On the iPhone, install **Tailscale** from the App Store and sign in with the same account.
4. Find the server's Tailscale address: `tailscale ip -4` on the server (a `100.x.y.z` number), or
   its name in the Tailscale app. With **MagicDNS** on (the default), the name works too.
5. On the phone, with Tailscale on, open `http://100.x.y.z:8030` or `http://<server-name>:8030`
   and add that address to the home screen as in [server.md](server.md). It also works at home.

### Optional: HTTPS inside the tailnet

`tailscale serve` gives the app an `https://<server-name>.<tailnet>.ts.net` address with a real
certificate, still reachable **only by your own devices**:

```sh
sudo tailscale serve --bg 8030
```

`tailscale serve status` shows the address; `sudo tailscale serve reset` turns it off.

### Never `tailscale funnel`

`tailscale funnel` puts the app **on the public internet** for anyone with the address. Agenda
has no logins, so that would hand the calendar to anyone. Never use it, just like port forwarding
or a Cloudflare tunnel.

## The firewall

Port 8030 should only be reachable from the home network and the tailnet:

- **The router**: no port forwarding to the server, no "DMZ" host, UPnP off if you can.
- **On the server** (if it uses `ufw`): allow 8030 only from the LAN and Tailscale, e.g.

  ```sh
  sudo ufw allow from 192.168.1.0/24 to any port 8030 proto tcp
  sudo ufw allow in on tailscale0 to any port 8030 proto tcp
  ```

  (Use your own network, the first three numbers of the server's IP followed by `.0/24`.) Note
  that Docker's published ports can go around `ufw`; the router not forwarding anything is what
  actually keeps the internet out.
- **Check from outside**: on the phone, with Wi-Fi **and** Tailscale off (mobile data only), the
  address must **not** open.
