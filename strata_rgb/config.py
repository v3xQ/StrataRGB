"""Configuration loading for StrataRGB.

Config is YAML. Every key has a default, so an empty file is valid.
"""

from __future__ import annotations

import dataclasses
from typing import Dict, List, Tuple

DEFAULT_COLORS: Dict[str, Tuple[int, int, int]] = {
    "reading": (0, 0, 255),
    "thinking": (255, 255, 0),
    "answering": (0, 255, 0),
    "idle": (255, 0, 0),
}

# Ordered substring rules, first match wins. Tunable via config.
# Matched against the /metrics live.state value.
DEFAULT_PHASE_RULES: List[Dict[str, str]] = [
    {"contains": "idle", "state": "idle"},
    # reading: prompt ingestion / prefill
    {"contains": "read", "state": "reading"},
    {"contains": "prompt", "state": "reading"},
    {"contains": "prefill", "state": "reading"},
    {"contains": "context", "state": "reading"},
    {"contains": "upload", "state": "reading"},
    {"contains": "think", "state": "thinking"},
    {"contains": "reason", "state": "thinking"},
    {"contains": "tool", "state": "thinking"},
    {"contains": "answer", "state": "answering"},
    {"contains": "generat", "state": "answering"},
    {"contains": "respond", "state": "answering"},
    {"contains": "stream", "state": "answering"},
    {"contains": "decod", "state": "answering"},
    {"contains": "token", "state": "answering"},
]

VALID_STATES = ("reading", "thinking", "answering", "idle")


@dataclasses.dataclass
class Config:
    status_url: str = "http://127.0.0.1:8080/metrics"
    # Dot-path into the JSON payload whose value drives the color,
    # e.g. "live.state" for Strata /metrics.
    state_path: str = "live.state"
    # Human-readable label paired with state_path; rules match this first
    # (e.g. live.phase="thinking" while live.state="generating").
    phase_path: str = "live.phase"
    poll_seconds: float = 5.0
    request_timeout_s: float = 3.0

    openrgb_host: str = "127.0.0.1"
    openrgb_port: int = 6742
    client_name: str = "StrataRGB"

    colors: Dict[str, Tuple[int, int, int]] = dataclasses.field(
        default_factory=lambda: dict(DEFAULT_COLORS)
    )
    phase_rules: List[Tuple[str, str]] = dataclasses.field(
        default_factory=lambda: [(r["contains"], r["state"]) for r in DEFAULT_PHASE_RULES]
    )
    # State used when the state_path field is missing/unrecognized.
    fallback_state: str = "thinking"
    # State used when /metrics is unreachable (engine down).
    unreachable_state: str = "idle"

    log_file: str = "stratargb.log"
    log_level: str = "INFO"


def _validate_color(name: str, value) -> Tuple[int, int, int]:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 3
        or not all(isinstance(c, int) and 0 <= c <= 255 for c in value)
    ):
        raise ValueError(f"colors.{name} must be [r,g,b] ints 0-255, got {value!r}")
    return (value[0], value[1], value[2])


def load_config(path: str) -> Config:
    """Load YAML config from *path*; missing file => all defaults."""
    import yaml  # local import: keeps tests/dry-run usable without pyyaml

    raw: dict = {}
    if path:
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

    cfg = Config()
    cfg.status_url = raw.get("status_url", cfg.status_url)
    cfg.state_path = str(raw.get("state_path", cfg.state_path))
    cfg.phase_path = str(raw.get("phase_path", cfg.phase_path))
    cfg.poll_seconds = float(raw.get("poll_seconds", cfg.poll_seconds))
    cfg.request_timeout_s = float(raw.get("request_timeout_s", cfg.request_timeout_s))

    orgbsdk = raw.get("openrgb", {}) or {}
    cfg.openrgb_host = orgbsdk.get("host", cfg.openrgb_host)
    cfg.openrgb_port = int(orgbsdk.get("port", cfg.openrgb_port))
    cfg.client_name = orgbsdk.get("client_name", cfg.client_name)

    colors_raw = raw.get("colors", {}) or {}
    cfg.colors = dict(DEFAULT_COLORS)
    for name, value in colors_raw.items():
        if name not in VALID_STATES:
            raise ValueError(f"unknown state in colors: {name!r} (valid: {VALID_STATES})")
        cfg.colors[name] = _validate_color(name, value)

    if "phase_rules" in raw:
        rules = raw["phase_rules"] or []
        cfg.phase_rules = []
        for rule in rules:
            contains = str(rule["contains"]).lower()
            state = str(rule["state"]).lower()
            if state not in VALID_STATES:
                raise ValueError(f"phase_rules state {state!r} not in {VALID_STATES}")
            cfg.phase_rules.append((contains, state))

    for key in ("fallback_state", "unreachable_state"):
        value = str(raw.get(key, getattr(cfg, key))).lower()
        if value not in VALID_STATES:
            raise ValueError(f"{key} {value!r} not in {VALID_STATES}")
        setattr(cfg, key, value)

    cfg.log_file = raw.get("log_file", cfg.log_file)
    cfg.log_level = str(raw.get("log_level", cfg.log_level))

    if cfg.poll_seconds <= 0:
        raise ValueError("poll_seconds must be > 0")
    return cfg
