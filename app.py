import os
import sys
import time
import signal
import struct
import fcntl
import select
import subprocess

# Render off-screen: no SDL video/mouse driver is needed (SDL2 has no fbcon/TSLIB).
# We push pixels straight to the framebuffer and read touch events from evdev ourselves.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame
import psutil

FB_DEV = os.getenv("FRAMEBUFFER_DEV", "/dev/fb1")
FB_NAME = os.path.basename(FB_DEV)
TOUCH_DEV = os.getenv("TOUCH_DEVICE", "/dev/input/event0")

WIDTH, HEIGHT = 480, 320

# Touch calibration (override via env if coordinates don't line up)
TOUCH_SWAP_XY = os.getenv("TOUCH_SWAP_XY", "0") == "1"
TOUCH_INVERT_X = os.getenv("TOUCH_INVERT_X", "0") == "1"
TOUCH_INVERT_Y = os.getenv("TOUCH_INVERT_Y", "0") == "1"

pygame.init()
pygame.font.init()
screen = pygame.Surface((WIDTH, HEIGHT))

# CLI / TUI Palette
C_BG = (10, 10, 10)
C_FRAME = (50, 50, 50)
C_GREEN = (0, 255, 120)
C_WARN = (255, 180, 0)
C_RED = (255, 60, 60)
C_WHITE = (220, 220, 220)
C_DIM = (120, 120, 120)

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


def load_font(size):
    # Real monospace font keeps the ASCII bars aligned; fall back to pygame default.
    try:
        return pygame.font.Font(FONT_PATH, size)
    except Exception:
        return pygame.font.SysFont("monospace", size, bold=True)


font_mono = load_font(17)
font_btn = load_font(15)

BTN_REBOOT = pygame.Rect(30, 260, 195, 45)
BTN_POWEROFF = pygame.Rect(255, 260, 195, 45)

confirm_action = None
confirm_time = 0


# ---------------------------------------------------------------- framebuffer
def read_sysfs(name, default=None):
    try:
        with open(f"/sys/class/graphics/{FB_NAME}/{name}") as f:
            return f.read().strip()
    except Exception:
        return default


def fb_geometry():
    """Return (width, height, bits_per_pixel, stride_bytes) of the framebuffer."""
    w, h = WIDTH, HEIGHT
    size = read_sysfs("virtual_size")
    if size and "," in size:
        w, h = (int(v) for v in size.split(","))
    bpp = int(read_sysfs("bits_per_pixel", "16"))
    stride = int(read_sysfs("stride", str(w * bpp // 8)))
    return w, h, bpp, stride


FB_W, FB_H, FB_BPP, FB_STRIDE = fb_geometry()


def frame_to_bytes(surface):
    """Convert the pygame surface to raw framebuffer bytes (RGB565 or 32bpp)."""
    if (FB_W, FB_H) != surface.get_size():
        surface = pygame.transform.scale(surface, (FB_W, FB_H))
    arr = pygame.surfarray.array3d(surface).transpose(1, 0, 2)  # (h, w, 3)
    r = arr[:, :, 0].astype(np.uint16)
    g = arr[:, :, 1].astype(np.uint16)
    b = arr[:, :, 2].astype(np.uint16)
    if FB_BPP == 16:
        raw = (((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)).astype("<u2")
    else:  # 24/32 bpp little-endian: B, G, R (, A)
        chans = [b.astype(np.uint8), g.astype(np.uint8), r.astype(np.uint8)]
        if FB_BPP == 32:
            chans.append(np.full_like(chans[0], 255))
        raw = np.stack(chans, axis=2)
    raw = np.ascontiguousarray(raw)
    rows = raw.view(np.uint8).reshape(FB_H, -1)
    if rows.shape[1] < FB_STRIDE:  # pad each line to the framebuffer stride
        pad = np.zeros((FB_H, FB_STRIDE - rows.shape[1]), dtype=np.uint8)
        rows = np.concatenate([rows, pad], axis=1)
    return rows.tobytes()


def blit_to_fb(surface):
    try:
        with open(FB_DEV, "r+b", buffering=0) as fb:
            fb.write(frame_to_bytes(surface))
    except Exception as e:
        print(f"[fb] write failed: {e}", file=sys.stderr)


def clear_fb():
    try:
        with open(FB_DEV, "wb", buffering=0) as fb:
            fb.write(b"\x00" * (FB_STRIDE * FB_H))
    except Exception:
        pass


# ---------------------------------------------------------------------- touch
EV_SYN, EV_KEY, EV_ABS = 0x00, 0x01, 0x03
ABS_X, ABS_Y = 0x00, 0x01
BTN_TOUCH = 0x14A
EVENT_FMT = "@llHHi"  # native timeval size: 24 bytes on 64-bit, 16 on 32-bit
EVENT_SIZE = struct.calcsize(EVENT_FMT)


def abs_range(fd, axis, default):
    """Read min/max of an ABS axis through EVIOCGABS."""
    try:
        buf = bytearray(struct.calcsize("6i"))
        fcntl.ioctl(fd, 0x80184540 + axis, buf)  # EVIOCGABS(axis)
        _, lo, hi, _, _, _ = struct.unpack("6i", buf)
        if hi > lo:
            return lo, hi
    except Exception:
        pass
    return default


class Touch:
    def __init__(self, path):
        self.fd = None
        self.raw_x = self.raw_y = 0
        self.down = False
        try:
            self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            self.x_rng = abs_range(self.fd, ABS_X, (0, 4095))
            self.y_rng = abs_range(self.fd, ABS_Y, (0, 4095))
            print(f"[touch] {path} X{self.x_rng} Y{self.y_rng}", flush=True)
        except Exception as e:
            print(f"[touch] cannot open {path}: {e}", file=sys.stderr)

    def _map(self):
        x_rng, y_rng = self.x_rng, self.y_rng
        rx, ry = self.raw_x, self.raw_y
        if TOUCH_SWAP_XY:
            rx, ry = ry, rx
            x_rng, y_rng = y_rng, x_rng
        nx = (rx - x_rng[0]) / max(1, x_rng[1] - x_rng[0])
        ny = (ry - y_rng[0]) / max(1, y_rng[1] - y_rng[0])
        if TOUCH_INVERT_X:
            nx = 1 - nx
        if TOUCH_INVERT_Y:
            ny = 1 - ny
        return (int(min(max(nx, 0), 1) * (WIDTH - 1)),
                int(min(max(ny, 0), 1) * (HEIGHT - 1)))

    def poll(self):
        """Return list of (x, y) taps (registered on finger release)."""
        taps = []
        if self.fd is None:
            return taps
        while select.select([self.fd], [], [], 0)[0]:
            try:
                data = os.read(self.fd, EVENT_SIZE * 64)
            except BlockingIOError:
                break
            except OSError:
                break
            if not data:
                break
            for off in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
                _, _, etype, code, value = struct.unpack_from(EVENT_FMT, data, off)
                if etype == EV_ABS:
                    if code == ABS_X:
                        self.raw_x = value
                    elif code == ABS_Y:
                        self.raw_y = value
                elif etype == EV_KEY and code == BTN_TOUCH:
                    if value == 1:
                        self.down = True
                    elif value == 0 and self.down:
                        self.down = False
                        mapped = self._map()
                        print(f"[touch tap] raw=({self.raw_x}, {self.raw_y}) -> mapped={mapped}", flush=True)
                        taps.append(mapped)
        return taps


# --------------------------------------------------------------------- system
def cleanup_and_exit(signum=None, frame=None):
    pygame.quit()
    try:
        clear_fb()
        os.system("setterm -cursor on > /dev/tty1 2>/dev/null")
    except Exception:
        pass
    sys.exit(0)


signal.signal(signal.SIGTERM, cleanup_and_exit)
signal.signal(signal.SIGINT, cleanup_and_exit)


def host_cmd(action):
    method = {"reboot": "Reboot", "poweroff": "PowerOff"}[action]
    subprocess.run(["dbus-send", "--system", "--print-reply",
                    "--dest=org.freedesktop.systemd1",
                    "/org/freedesktop/systemd1",
                    f"org.freedesktop.systemd1.Manager.{method}"], check=False)


def get_temp():
    try:
        with open("/host/thermal/temp", "r") as f:
            return float(f.read().strip()) / 1000.0
    except Exception:
        return 0.0


def format_usage_bar(percent, free_bytes, length=18):
    filled = int(round(length * percent / 100.0))
    bar = "[" + "=" * filled + " " * (length - filled) + "]"
    return bar, f"{percent:>4.1f}% ({free_bytes / (1024 ** 3):.1f}G free)"


def get_disk_bar(path, length=18):
    try:
        u = psutil.disk_usage(path)
        return format_usage_bar(u.percent, u.free, length)
    except Exception:
        return "[ OFFLINE          ]", "N/A"


def get_cpu_percent():
    # Non-blocking: average load since the previous call (primed once in main()).
    try:
        return psutil.cpu_percent(interval=None)
    except Exception:
        return 0.0


def get_ram_percent():
    try:
        return psutil.virtual_memory().percent
    except Exception:
        return 0.0


def level_color(value, warn, crit):
    return C_GREEN if value < warn else (C_WARN if value < crit else C_RED)


VALUE_X = 235  # shared x of the single-line metric values


def draw_metric(label, text, color, y):
    screen.blit(font_mono.render(label, True, C_DIM), (30, y))
    screen.blit(font_mono.render(text, True, color), (VALUE_X, y))


def draw(temp, cpu, ram, sd, usb):
    sd_bar, sd_text = sd
    usb_bar, usb_text = usb
    screen.fill(C_BG)

    # CPU and GPU share one die (SoC) and one sensor, so a single reading covers both.
    draw_metric("SoC Temp (CPU+GPU):", f"{temp:.1f} °C", level_color(temp, 60, 75), 18)
    draw_metric("CPU Usage:", f"{cpu:.1f} %", level_color(cpu, 70, 90), 50)
    draw_metric("RAM Usage:", f"{ram:.1f} %", level_color(ram, 70, 90), 82)

    screen.blit(font_mono.render("SD (/):", True, C_DIM), (30, 128))
    screen.blit(font_mono.render(f"{sd_bar} {sd_text}", True, C_WHITE), (30, 152))

    screen.blit(font_mono.render("USB (/mnt/usb0):", True, C_DIM), (30, 194))
    screen.blit(font_mono.render(f"{usb_bar} {usb_text}", True, C_WHITE), (30, 218))

    rb_txt = "CONFIRM?" if confirm_action == "reboot" else "[ REBOOT ]"
    rb_col = C_WARN if confirm_action == "reboot" else C_DIM
    pygame.draw.rect(screen, C_FRAME, BTN_REBOOT, 1)
    lbl_r = font_btn.render(rb_txt, True, rb_col)
    screen.blit(lbl_r, lbl_r.get_rect(center=BTN_REBOOT.center))

    po_txt = "CONFIRM?" if confirm_action == "poweroff" else "[ SHUTDOWN ]"
    po_col = C_RED if confirm_action == "poweroff" else C_DIM
    pygame.draw.rect(screen, C_FRAME, BTN_POWEROFF, 1)
    lbl_p = font_btn.render(po_txt, True, po_col)
    screen.blit(lbl_p, lbl_p.get_rect(center=BTN_POWEROFF.center))

    blit_to_fb(screen)


def handle_tap(pos, now):
    """Two-step confirmation logic. Returns True if the UI must be redrawn."""
    global confirm_action, confirm_time
    if BTN_REBOOT.collidepoint(pos):
        print(f"[button hit] REBOOT at {pos} (confirm={confirm_action})", flush=True)
        if confirm_action == "reboot":
            confirm_action = None
            host_cmd("reboot")
        else:
            confirm_action, confirm_time = "reboot", now
    elif BTN_POWEROFF.collidepoint(pos):
        print(f"[button hit] POWEROFF at {pos} (confirm={confirm_action})", flush=True)
        if confirm_action == "poweroff":
            confirm_action = None
            host_cmd("poweroff")
        else:
            confirm_action, confirm_time = "poweroff", now
    else:
        print(f"[tap outside buttons] pos={pos} (BTN_REBOOT={BTN_REBOOT}, BTN_POWEROFF={BTN_POWEROFF})", flush=True)
        confirm_action = None
    return True


def main():
    global confirm_action
    touch = Touch(TOUCH_DEV)
    get_cpu_percent()  # first call always returns 0.0; later calls average since the previous one
    last_update = 0
    metrics = None
    dirty = True

    while True:
        now = time.time()

        if confirm_action and (now - confirm_time > 4):
            confirm_action = None
            dirty = True

        for pos in touch.poll():
            dirty |= handle_tap(pos, now)

        if now - last_update >= 3 or metrics is None:
            last_update = now
            metrics = (get_temp(),
                       get_cpu_percent(),
                       get_ram_percent(),
                       get_disk_bar("/host/root"),
                       get_disk_bar("/host/usb0"))
            dirty = True

        if dirty:
            draw(*metrics)
            dirty = False

        time.sleep(0.05)


if __name__ == "__main__":
    main()
