"""Poll the Strata /metrics endpoint and classify live.state into a named state."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Optional

from .config import Config

log = logging.getLogger("stratargb.status")


def fetch_status(url: str, timeout_s: float) -> Optional[dict]:
    """GET *url*, parse JSON. Return None on any failure (engine down/timeout)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            body = resp.read()
        return json.loads(body)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.debug("status fetch failed: %s", exc)
        return None


def extract_state(payload: dict, path: str = "live.state"):
    """Walk a dot-path (e.g. 'live.state') into *payload*. None if absent/malformed."""
    cur = payload
    for key in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def classify(payload: Optional[dict], cfg: Config) -> str:
    """Map a /metrics payload to one of: reading|thinking|answering|idle.

    Uses the pair (cfg.phase_path, cfg.state_path) — by default
    (live.phase, live.state). live.phase is the specific human-readable
    label (e.g. "thinking" while live.state is the coarse "generating"),
    so rules are matched against phase first, then state. All other
    /metrics data (engine, requests, hardware, history) is ignored.
    """
    if payload is None:
        return cfg.unreachable_state
    phase = extract_state(payload, cfg.phase_path)
    state = extract_state(payload, cfg.state_path)
    for value in (phase, state):  # phase first: it is the more specific signal
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        s = str(value).lower()
        for contains, mapped in cfg.phase_rules:
            if contains in s:
                return mapped
    # Warning (not debug): unrecognized pairs mean the rules need tuning,
    # and the raw values in the log tell you exactly how.
    log.warning("unrecognized %s=%r %s=%r -> fallback %s",
                cfg.phase_path, phase, cfg.state_path, state,
                cfg.fallback_state)
    return cfg.fallback_state


def raw_pair(payload: Optional[dict], cfg: Config):
    """(live.state, live.phase) values for logging; None values pass through."""
    if payload is None:
        return None, None
    return (extract_state(payload, cfg.state_path),
            extract_state(payload, cfg.phase_path))
