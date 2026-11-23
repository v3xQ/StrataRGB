# StrataRGB

Drives every OpenRGB-visible device to a color reflecting the state of a
local Strata inference engine:

| Engine state        | Color  |
|---------------------|--------|
| reading the prompt  | blue   |
| thinking            | yellow |
| answering           | green  |
| idle                | red    |

It polls Strata's `/metrics` endpoint (default
`http://127.0.0.1:8080/metrics`, every 5 s) and classifies using the
`live.phase` / `live.state` pair (configurable dot-paths, `phase_path` /
`state_path`). `live.phase` is the specific label and is matched first —
e.g. while reasoning, `live.state` is the coarse `"generating"` (which
alone looks like *answering*) and `live.phase` is `"thinking"`. Colors,
poll interval, and the matching rules are all configurable. Runs on
Windows (as a WinSW service) and on any platform with Python 3.10+.

Known Strata combinations:

| `live.state`   | `live.phase`        | Color  |
|----------------|---------------------|--------|
| `idle`         | `null`              | red    |
| `reading`      | `reading the prompt`| blue   |
| `generating`   | `thinking`          | yellow |
| `generating`   | `answering`/`null`  | green  |

Any transition logs the raw pair (`state=... raw live.state=... live.phase=...`)
so unmapped combinations are visible in `stratargb.log` for rule tuning.

## Layout

- `strata_rgb/config.py` — YAML config with validated defaults
- `strata_rgb/status.py` — poll + classify
- `strata_rgb/lights.py` — OpenRGB SDK wrapper (per-device failures isolated, auto-reconnect)
- `strata_rgb/daemon.py` — main loop, CLI, logging
- `service/stratargb.xml` — WinSW service definition (Windows)
- `mock/mock_metrics_server.py` — cycles live.state idle→reading→thinking→answering for local testing
- `tests/` — unit + end-to-end (mock metrics server, stubbed OpenRGB)

## Quick start

1. Install Python 3.10+ and OpenRGB. In OpenRGB: **Settings → General →
   Server**, enable the SDK server (port 6742), and set OpenRGB to start
   at logon — RGB control requires the app running.
2. `pip install -r requirements.txt`
3. Smoke test without touching hardware:
   `python -m strata_rgb --dry-run --once`
4. One live poll: `python -m strata_rgb --once` — watch the
   `first payload: live.state=...` log line; if a state shows as
   `unrecognized ... -> fallback`, tune `phase_rules` in `config.yaml`.
5. Run for real: `python -m strata_rgb`

## Install as a Windows service (WinSW)

1. Download WinSW-x64.exe from <https://github.com/winsw/winsw/releases>.
2. Put the repo at `C:\StrataRGB`, create a venv there
   (`python -m venv venv && venv\Scripts\pip install -r requirements.txt`),
   copy `service\stratargb.xml` to `C:\StrataRGB\stratargb.xml`, and copy
   WinSW as `C:\StrataRGB\stratargb.exe`.
3. From an elevated prompt:
   ```
   cd C:\StrataRGB
   stratargb.exe install
   stratargb.exe start
   ```
4. Logs: WinSW's own stdout log + `stratargb.log` (rotating).

Note: OpenRGB talks to USB/HID devices, so the service should run with
desktop/interactive access. If colors don't change, run the service as the
logged-in user (Task Scheduler at logon is the fallback), not as
LocalSystem.

On Linux, a systemd user service works the same way; run the daemon in the
user's session so OpenRGB (and its device permissions) are reachable.

## Configuration

Copy `config.example.yaml` to `config.yaml` (gitignored). Precedence:
CLI flags > env vars > `config.yaml` > built-in defaults.

CLI: `--config --status-url --interval --openrgb-host --openrgb-port
--log-file --log-level --dry-run --once`

Env: `STRATA_RGB_CONFIG`, `STRATA_STATUS_URL`, `STRATA_POLL_INTERVAL`,
`OPENRGB_HOST`, `OPENRGB_PORT`.

## Tests

```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest tests.test_status -v
.venv/bin/python tests/test_e2e.py
```
