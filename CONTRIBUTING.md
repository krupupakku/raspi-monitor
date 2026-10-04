# Contributing

Thanks for your interest in raspi-monitor!

## Workflow

1. Fork the repo and create a branch from `main` (`feat/...` or `fix/...`).
2. Keep changes small and focused; one topic per pull request.
3. Test on real hardware when you touch display or touch input, and mention the board, display and OS in the PR.
4. Open a pull request describing what changed and why.

## Guidelines

- Python 3, PEP 8 style; keep dependencies minimal (the app must stay lightweight).
- No X11/Wayland requirement: rendering goes straight to the framebuffer.
- Never commit secrets, tokens or personal data.
- Update `README.md` if you change configuration or behaviour.

## Reporting bugs

Open an issue with: Raspberry Pi model, display/touch controller, OS version, `docker compose logs`, and the output of `cat /proc/bus/input/devices` and `cat /sys/class/graphics/fb1/bits_per_pixel`.

Security issues: see [SECURITY.md](SECURITY.md).

By contributing you agree that your work is released under the [MIT License](LICENSE).
