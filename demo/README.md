# Demo: local UI preview with fake data

Try the display layout on your computer, no Raspberry Pi needed. `app.py` is imported unchanged;
this folder only replaces the hardware parts (temperature, disks, framebuffer, touch, D-Bus).
To remove the feature, delete this `demo/` folder.

## Setup (once, from the repo root)

```bash
python3 -m venv demo/.venv
demo/.venv/bin/pip install -r demo/requirements.txt
```

The demo uses `pygame-ce` (a drop-in fork of pygame) because the original `pygame` has no prebuilt wheel for the newest Python versions. The app on the Pi keeps using `pygame`.

## PNG preview

```bash
demo/.venv/bin/python demo/demo.py                          # -> demo/out/preview.png
demo/.venv/bin/python demo/demo.py --temp 78 --sd 92        # red temp, nearly full SD
demo/.venv/bin/python demo/demo.py --usb offline            # unmounted USB
demo/.venv/bin/python demo/demo.py --state shutdown         # CONFIRM? prompt
demo/.venv/bin/python demo/demo.py --ram 90                 # high RAM usage
```

## Interactive window

```bash
demo/.venv/bin/python demo/demo.py --window
```

- Click the buttons to try the two-step confirmation (reboot/shutdown only print a message).
- Keys: `t` temperature, `c` CPU, `r` RAM, `s` SD, `u` USB (each +5, hold Shift for -5), `o` USB offline on/off, `q` quit.

## Notes

- Colours and layout match the real display; fonts may differ slightly on macOS (Menlo instead of DejaVu Sans Mono).
- Generated images go to `demo/out/` and are git-ignored.
