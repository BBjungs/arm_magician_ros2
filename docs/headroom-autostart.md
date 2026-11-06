# Headroom Dashboard at startup

Open http://172.30.10.101:8787/ (redirects to `/dashboard`).

Two systemd user services are enabled for user `jetson`:

- `headroom-proxy.service` keeps the backend at `127.0.0.1:8787`. If an
  interactive `headroom wrap` proxy is already running, it waits for that
  process to exit before starting the persistent backend.
- `headroom-dashboard.service` serves the monitoring dashboard, statistics,
  history exports and transformation feed at `172.30.10.101:8787`. Other API
  paths and write requests are blocked. Settings remain local to the host.

`loginctl show-user jetson -p Linger` must report `Linger=yes` for startup
before login. Both services restart automatically on failure. The LAN service
also retries if the network address is not yet available during boot.

The Wi-Fi connection currently uses DHCP. The router must continue assigning
`172.30.10.101` to this device for this URL to remain valid; a DHCP reservation
on the router is the preferred way to guarantee that address.

Check status:

```bash
systemctl --user status headroom-proxy.service headroom-dashboard.service
journalctl --user -u headroom-proxy.service -u headroom-dashboard.service
```

After editing the scripts, restart the relevant service. After editing unit
files in this repository, install them and reload systemd:

```bash
install -m 0644 systemd/headroom-{proxy,dashboard}.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now headroom-proxy.service headroom-dashboard.service
```

Disable automatic startup:

```bash
systemctl --user disable --now headroom-dashboard.service headroom-proxy.service
```

An existing interactive proxy is not stopped by these services.
