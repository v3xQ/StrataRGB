#!/usr/bin/env python3
"""Mock Strata /metrics server for local testing.

Serves the /metrics JSON shape (engine/live/requests/hardware/...) and
cycles the live.state/live.phase pair through the real Strata combinations:
idle/null -> reading/"reading the prompt" -> generating/"thinking" ->
generating/"answering". The thinking case is the regression: live.state
alone says "generating" (green) but live.phase says "thinking" (yellow).
Usage: python mock/mock_metrics_server.py [port]
Then:  python -m strata_rgb --dry-run --status-url http://127.0.0.1:18080/metrics
"""

import http.server
import json
import sys
import time

# (live.state, live.phase) — phase is the specific label, state the coarse one.
PHASES = [
    ("idle", None),
    ("reading", "reading the prompt"),
    ("generating", "thinking"),
    ("generating", "answering"),
]
SECONDS_PER_STATE = 4


def build_payload(state: str, phase) -> dict:
    busy = state != "idle"
    return {
        "engine": {"model": "mock-model", "max_context": 131072,
                   "version": "0.0.0-mock"},
        "live": {
            "state": state,
            "queued": 0,
            "phase": phase,
            "prompt_tokens": 24453 if busy else None,
            "generated": 512 if state == "generating" else (0 if busy else None),
            "max_tokens": 102791 if busy else None,
            "elapsed_s": round(time.time() % 60, 1) if busy else None,
            "tok_s": 58.4 if state == "generating" else None,
            "parallel": 2,
            "running": 1 if busy else 0,
            "slots": [{"slot": 0, "state": state, "held_tokens": 0},
                      {"slot": 1, "state": "idle", "held_tokens": 0}],
            "outside_slots": 0, "waiting": 0, "admitting": 0,
        },
        "requests": [],
        "requests_kept": 0,
        "totals": {"requests": 0},
        "hardware": {"gpu_util": 42, "cpu": 5.2, "tok_s": 0.0},
        "time": time.time(),
    }


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_error(404)
            return
        state, phase = PHASES[int(time.time() // SECONDS_PER_STATE) % len(PHASES)]
        body = json.dumps(build_payload(state, phase)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # silence
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18080
    http.server.HTTPServer(("127.0.0.1", port), Handler).serve_forever()
