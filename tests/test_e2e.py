"""End-to-end smoke test: mock /metrics HTTP server + stub OpenRGB client.

Runs strata_rgb.daemon.main() with --once against a local mock server and
asserts the stub OpenRGB client received the right color for each live.state.
"""
import http.server
import json
import os
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(HERE, "stub"))  # stub openrgb package

import openrgb_stub_state  # noqa: E402  (shared call recorder)
from strata_rgb import daemon  # noqa: E402


class Handler(http.server.BaseHTTPRequestHandler):
    payload = {}

    def do_GET(self):
        body = json.dumps(self.payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args, **kwargs):  # silence
        pass


def run_case(server, payload, empty_config_path):
    Handler.payload = payload
    openrgb_stub_state.CALLS.clear()
    rc = daemon.main([
        "--config", empty_config_path,
        "--status-url", f"http://127.0.0.1:{server.server_address[1]}/metrics",
        "--interval", "5",
        "--once",
    ])
    assert rc == 0, f"main() returned {rc}"
    return [(c.red, c.green, c.blue) for c in openrgb_stub_state.CALLS]


def main():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    ok = True
    with tempfile.TemporaryDirectory() as d:
        empty_cfg = os.path.join(d, "empty.yaml")
        open(empty_cfg, "w").close()  # empty YAML -> all defaults

        def metrics(state, phase=None):
            return {"engine": {"model": "mock"},
                    "live": {"state": state, "phase": phase, "queued": 0},
                    "requests": [], "hardware": {}}

        cases = [
            (metrics("reading", "reading the prompt"), (0, 0, 255)),
            # Regression: coarse state "generating" + phase "thinking" = yellow.
            (metrics("generating", "thinking"), (255, 255, 0)),
            (metrics("generating", "answering"), (0, 255, 0)),
            (metrics("generating"), (0, 255, 0)),
            (metrics("idle"), (255, 0, 0)),
        ]
        for payload, want in cases:
            colors = run_case(server, payload, empty_cfg)
            state = payload["live"]["state"]
            phase = payload["live"]["phase"]
            # Stub exposes 2 devices; each must get the color.
            if len(colors) == 2 and all(c == want for c in colors):
                print(f"[PASS] state={state!r} phase={phase!r} -> {want} on all devices")
            else:
                print(f"[FAIL] state={state!r} phase={phase!r} -> {colors} want 2x{want}")
                ok = False

    server.shutdown()
    print("ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
