# Context & Specifications: Raspberry Pi 3.5" TFT Status Monitor

## Overview & Goal
Ultra-lightweight, CLI/TUI-style system monitor for a Raspberry Pi (PoE HAT) running media services (Navidrome, Jellyfin).
3.5" GPIO/SPI TFT (480x320) with resistive touchscreen (ADS7846 / XPT2046 via `/dev/input/event*`).
Runs in Docker via `docker compose` (`start`/`stop` to enable/disable).

## Key Requirements
1. **Lightweight & headless**: Linux framebuffer (`/dev/fb1` or `/dev/fb0`), no X11/Wayland. Python 3, Pygame (SDL2), `psutil`.
2. **Metrics (refresh every 3-5 s)**: SoC temp (`/sys/class/thermal/thermal_zone0/temp`), SD root usage (`/`), USB usage (`/mnt/usb0`).
3. **Touch & host control**: `/dev/input/eventX` mapped to container; **[ REBOOT ]** / **[ SHUTDOWN ]** buttons with two-step `CONFERMI?` (4 s timeout); host actions via D-Bus system socket to systemd (`org.freedesktop.systemd1`).
4. **Clean exit**: handle `SIGTERM`/`SIGINT`, zero `/dev/fb1`, restore `/dev/tty1` cursor.
5. **Aesthetics**: hacker/terminal look, monospace, ASCII bars `[====    ]`, dark palette (black, dim gray, green/amber/red).

## Structure
```text
Dockerfile
docker-compose.yml
app.py
```

## Next Steps
- Touchscreen calibration / coordinate mapping (tslib or axis inversion).
- Service health indicators (Jellyfin / Navidrome via Docker socket or HTTP).
- Show local IP and network status.
