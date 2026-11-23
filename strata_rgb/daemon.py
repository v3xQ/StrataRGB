"""Main loop: poll Strata status, push color to OpenRGB on state changes."""

from __future__ import annotations

import logging
import signal
import sys
import threading
from logging.handlers import RotatingFileHandler

from .config import Config, load_config
from .lights import DryRunLights, LightsError, OpenRGBLights
from .status import classify, fetch_status, raw_pair

log = logging.getLogger("stratargb")


def setup_logging(cfg: Config) -> None:
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    root = logging.getLogger()
    root.handlers.clear()  # idempotent: repeated main() calls (tests) don't stack handlers
    root.setLevel(getattr(logging, cfg.log_level.upper(), logging.INFO))
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    root.addHandler(stream)
    if cfg.log_file:
        try:
            fileh = RotatingFileHandler(
                cfg.log_file, maxBytes=1_000_000, backupCount=3
            )
            fileh.setFormatter(fmt)
            root.addHandler(fileh)
        except OSError as exc:
            log.warning("cannot open log file %s: %s", cfg.log_file, exc)


def run(cfg: Config, lights, stop: threading.Event, once: bool = False) -> None:
    last_state = None
    first_payload = True
    while not stop.is_set():
        payload = fetch_status(cfg.status_url, cfg.request_timeout_s)
        state = classify(payload, cfg)
        if payload is not None and first_payload:
            # Log only the fields we consume — /metrics payloads are large.
            st, ph = raw_pair(payload, cfg)
            log.info("first payload: %s=%r %s=%r",
                     cfg.state_path, st, cfg.phase_path, ph)
            first_payload = False
        if state != last_state:
            color = cfg.colors[state]
            st, ph = raw_pair(payload, cfg)
            try:
                lights.set_color(color)
                last_state = state
                # Raw pair logged on every transition: unmapped combinations
                # are visible in the log for phase_rules tuning.
                log.info("state=%s (raw %s=%r %s=%r) -> rgb=%s applied",
                         state, cfg.state_path, st, cfg.phase_path, ph, color)
            except LightsError as exc:
                # Keep last_state so the next tick retries the hardware write.
                log.warning("lights write failed (state=%s): %s", state, exc)
        if once:
            break
        stop.wait(cfg.poll_seconds)


def main(argv=None) -> int:
    import argparse
    import os

    def _env(name):
        return os.environ.get(name) or None

    parser = argparse.ArgumentParser(prog="stratargb")
    parser.add_argument(
        "--config",
        default=_env("STRATA_RGB_CONFIG") or "config.yaml",
        help="YAML config path (env STRATA_RGB_CONFIG)",
    )
    parser.add_argument(
        "--status-url", default=_env("STRATA_STATUS_URL"),
        help="Override status_url (env STRATA_STATUS_URL)",
    )
    parser.add_argument(
        "--interval", type=float,
        default=float(_env("STRATA_POLL_INTERVAL")) if _env("STRATA_POLL_INTERVAL") else None,
        help="Poll interval in seconds (env STRATA_POLL_INTERVAL; config default 5)",
    )
    parser.add_argument(
        "--openrgb-host", default=_env("OPENRGB_HOST"),
        help="Override OpenRGB SDK host (env OPENRGB_HOST)",
    )
    parser.add_argument(
        "--openrgb-port", type=int,
        default=int(_env("OPENRGB_PORT")) if _env("OPENRGB_PORT") else None,
        help="Override OpenRGB SDK port (env OPENRGB_PORT)",
    )
    parser.add_argument("--log-file", default=None, help="Override log_file path")
    parser.add_argument("--log-level", default=None, help="Override log level")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="log colors instead of driving OpenRGB (no openrgb package needed)",
    )
    parser.add_argument(
        "--once", action="store_true", help="single poll then exit (smoke test)"
    )
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    # CLI flags override YAML, which overrides defaults.
    if args.status_url:
        cfg.status_url = args.status_url
    if args.interval is not None:
        cfg.poll_seconds = args.interval
    if args.openrgb_host:
        cfg.openrgb_host = args.openrgb_host
    if args.openrgb_port:
        cfg.openrgb_port = args.openrgb_port
    if args.log_file:
        cfg.log_file = args.log_file
    if args.log_level:
        cfg.log_level = args.log_level
    setup_logging(cfg)
    log.info(
        "starting: url=%s poll=%ss openrgb=%s:%d dry_run=%s",
        cfg.status_url,
        cfg.poll_seconds,
        cfg.openrgb_host,
        cfg.openrgb_port,
        args.dry_run,
    )

    lights = (
        DryRunLights()
        if args.dry_run
        else OpenRGBLights(cfg.openrgb_host, cfg.openrgb_port, cfg.client_name)
    )

    stop = threading.Event()

    def _stop(signum, _frame):
        log.info("signal %s -> shutting down", signum)
        stop.set()

    for sig in (signal.SIGINT, getattr(signal, "SIGTERM", None)):
        if sig is not None:
            try:
                signal.signal(sig, _stop)
            except (ValueError, OSError):
                pass  # not on main thread / unsupported (e.g. SIGTERM on Windows)

    try:
        run(cfg, lights, stop, once=args.once)
    finally:
        lights.close()
    return 0
