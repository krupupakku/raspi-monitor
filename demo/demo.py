"""Local preview of the monitor UI with fake data. No Raspberry Pi hardware needed.

Run from the repo root (see demo/README.md):

    python demo/demo.py                      # writes demo/out/preview.png
    python demo/demo.py --window             # interactive window, click = touch

app.py is imported untouched; only its hardware-facing functions are replaced here.
Delete the whole demo/ folder to remove this feature.
"""
import argparse
import os
import sys
import time
from collections import namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import app  # noqa: E402  (renders off-screen with SDL's dummy driver)
import pygame  # noqa: E402

MAC_FONT = "/System/Library/Fonts/Menlo.ttc"
Usage = namedtuple("Usage", "total used free percent")
Mem = namedtuple("Mem", "total available percent")
TOTAL = 64 * 1024 ** 3
RAM_TOTAL = 4 * 1024 ** 3

state = {"temp": 52.0, "cpu": 23.0, "ram": 38.0, "/host/root": 37.0, "/host/usb0": 71.0}
presenter = None


def fake_disk_usage(path):
    pct = state[path]
    if pct is None:  # simulates an unmounted disk -> "OFFLINE"
        raise OSError("offline")
    used = TOTAL * pct / 100
    return Usage(TOTAL, used, TOTAL - used, pct)


def fake_virtual_memory():
    pct = state["ram"]
    return Mem(RAM_TOTAL, RAM_TOTAL * (100 - pct) / 100, pct)


def parse_pct(value):
    return None if value.lower() == "offline" else float(value)


def install_mocks():
    app.get_temp = lambda: state["temp"]
    app.psutil.disk_usage = fake_disk_usage
    app.psutil.virtual_memory = fake_virtual_memory
    app.psutil.cpu_percent = lambda interval=None: state["cpu"]
    app.host_cmd = lambda action: print(f"[demo] host_cmd({action!r}) would run on the Pi")
    app.blit_to_fb = lambda surface: presenter(surface)
    if os.path.exists(MAC_FONT) and not os.path.exists(app.FONT_PATH):
        app.FONT_PATH = MAC_FONT  # closest to DejaVu Sans Mono on macOS
        app.font_mono = app.load_font(17)
        app.font_btn = app.load_font(15)


def render():
    app.draw(app.get_temp(),
             app.get_cpu_percent(),
             app.get_ram_percent(),
             app.get_disk_bar("/host/root"),
             app.get_disk_bar("/host/usb0"))


def run_png(args):
    app.confirm_action = {"reboot": "reboot", "shutdown": "poweroff"}.get(args.state)

    def save(surface):
        out = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if args.scale != 1:
            surface = pygame.transform.scale(
                surface, (surface.get_width() * args.scale, surface.get_height() * args.scale))
        pygame.image.save(surface, out)
        print(f"[demo] saved {out}")

    global presenter
    presenter = save
    render()


def run_window(args):
    global presenter
    # Switch from the dummy driver to a real window.
    pygame.display.quit()
    os.environ.pop("SDL_VIDEODRIVER", None)
    pygame.display.init()
    size = (app.WIDTH * args.scale, app.HEIGHT * args.scale)
    window = pygame.display.set_mode(size)
    pygame.display.set_caption("raspi-monitor demo  [t temp  c CPU  r RAM  s SD  u USB  (Shift = down)  o USB offline  q quit]")

    def show(surface):
        window.blit(pygame.transform.scale(surface, size), (0, 0))
        pygame.display.flip()

    presenter = show
    steps = {pygame.K_t: ("temp", 5), pygame.K_c: ("cpu", 5), pygame.K_r: ("ram", 5),
             pygame.K_s: ("/host/root", 5), pygame.K_u: ("/host/usb0", 5)}
    render()
    clock = pygame.time.Clock()
    running = True
    while running:
        now = time.time()
        dirty = False
        if app.confirm_action and now - app.confirm_time > 4:
            app.confirm_action = None
            dirty = True
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONUP:
                x, y = event.pos
                dirty |= app.handle_tap((x // args.scale, y // args.scale), now)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False
                elif event.key == pygame.K_o:
                    state["/host/usb0"] = None if state["/host/usb0"] is not None else 71.0
                    dirty = True
                elif event.key in steps:
                    key, step = steps[event.key]
                    sign = -1 if event.mod & pygame.KMOD_SHIFT else 1
                    cur = state[key] if state[key] is not None else 0
                    limit = 100 if key != "temp" else 95
                    state[key] = min(max(cur + sign * step, 0), limit)
                    dirty = True
        if dirty:
            render()
        clock.tick(30)
    pygame.quit()


def main():
    p = argparse.ArgumentParser(description="Preview the raspi-monitor UI with fake data.")
    p.add_argument("--window", action="store_true", help="interactive window (click = tap)")
    p.add_argument("--temp", type=float, default=52.0, help="SoC temperature in C")
    p.add_argument("--cpu", type=float, default=23.0, help="CPU usage %%")
    p.add_argument("--ram", type=float, default=38.0, help="RAM usage %%")
    p.add_argument("--sd", type=parse_pct, default=37.0, help="SD usage %% or 'offline'")
    p.add_argument("--usb", type=parse_pct, default=71.0, help="USB usage %% or 'offline'")
    p.add_argument("--state", choices=["idle", "reboot", "shutdown"], default="idle",
                   help="PNG mode: show the CONFIRM? prompt on a button")
    p.add_argument("--scale", type=int, default=2, help="output/window magnification")
    p.add_argument("-o", "--output", default=os.path.join(HERE, "out", "preview.png"))
    args = p.parse_args()

    state.update({"temp": args.temp, "cpu": args.cpu, "ram": args.ram,
                  "/host/root": args.sd, "/host/usb0": args.usb})
    install_mocks()
    run_window(args) if args.window else run_png(args)


if __name__ == "__main__":
    main()
