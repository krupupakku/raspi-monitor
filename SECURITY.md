# Security Policy

## Supported versions

Only the latest commit on `main` is supported.

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Use GitHub's private reporting: **Security → Report a vulnerability** on this repository.
You can expect an initial reply within a few days.

## Scope notes

This project mounts the host root filesystem (read-only) and the systemd D-Bus socket into
the container so it can reboot or power off the host. Reports about privilege exposure,
unsafe defaults in `docker-compose.yml`, or command-injection paths in `app.py` are welcome.
