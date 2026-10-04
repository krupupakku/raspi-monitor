# raspi-monitor

Ultra-lightweight, terminal-style system monitor for a Raspberry Pi with a 3.5" SPI TFT (480x320) and resistive touchscreen. Runs in Docker, writes straight to the Linux framebuffer: no X11, no Wayland.

## Features

- SoC temperature, SD card and external USB disk usage, with ASCII progress bars
- Touch buttons **REBOOT** / **SHUTDOWN** with two-step confirmation (4 s timeout)
- Host reboot/poweroff through the systemd D-Bus socket
- Clean exit on `SIGTERM`/`SIGINT`: clears the framebuffer and restores the console cursor
- Configurable touch calibration (swap / invert axes)

## Requirements

- Raspberry Pi with a framebuffer-driven TFT (e.g. `/dev/fb1`) and an ADS7846/XPT2046 touch controller
- Docker and Docker Compose

## Quick start

```bash
git clone git@github.com:krupupakku/raspi-monitor.git
cd raspi-monitor
cat /proc/bus/input/devices   # find your touch device (eventX)
docker compose up -d --build
```

Stop / start the monitor at any time:

```bash
docker compose stop
docker compose start
```

## Configuration

Set in [docker-compose.yml](docker-compose.yml):

| Variable | Default | Description |
|---|---|---|
| `FRAMEBUFFER_DEV` | `/dev/fb1` | Framebuffer to draw on |
| `TOUCH_DEVICE` | `/dev/input/event0` | Touchscreen evdev node |
| `TOUCH_SWAP_XY` | `0` | Swap X/Y axes |
| `TOUCH_INVERT_X` | `0` | Invert X axis |
| `TOUCH_INVERT_Y` | `0` | Invert Y axis |

If taps land in the wrong place, adjust the three touch variables. Remember to update the `devices:` entry if your touch device is not `event0`.

## Security notes

The container mounts the host root filesystem (read-only) and the systemd D-Bus socket, so it can reboot or power off the host. Only run it on a device you control, and do not expose it to untrusted networks.

## Roadmap

- Jellyfin / Navidrome health indicators
- Local IP and network status

## License

[MIT](LICENSE)
