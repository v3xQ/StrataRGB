import unittest

from strata_rgb.config import Config, load_config
from strata_rgb.status import classify, extract_state, fetch_status


def payload(state, phase=None):
    """Minimal /metrics-shaped payload with the given live.state/live.phase."""
    return {"engine": {"model": "x"}, "live": {"state": state, "phase": phase,
                                               "queued": 0}}


class ClassifyTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()

    def test_sample_from_strata(self):
        p = {
            "engine": {"model": "example-model", "max_context": 131072},
            "live": {"state": "idle", "queued": 0, "phase": None,
                     "parallel": 2, "running": 0,
                     "slots": [{"slot": 0, "state": "idle", "held_tokens": 0}]},
            "requests": [],
            "hardware": {"gpu_util": 8},
        }
        self.assertEqual(classify(p, self.cfg), "idle")

    def test_reading(self):
        self.assertEqual(classify(payload("reading"), self.cfg), "reading")

    def test_thinking(self):
        self.assertEqual(classify(payload("thinking"), self.cfg), "thinking")

    def test_answering_variants(self):
        self.assertEqual(classify(payload("answering"), self.cfg), "answering")
        self.assertEqual(classify(payload("generating"), self.cfg), "answering")
        self.assertEqual(classify(payload("generating", "answering"), self.cfg),
                         "answering")

    def test_phase_overrides_state(self):
        # Regression: while reasoning, live.state is the coarse "generating"
        # (which alone would map to green) and live.phase is "thinking".
        self.assertEqual(classify(payload("generating", "thinking"), self.cfg),
                         "thinking")
        self.assertEqual(classify(payload("generating", "reading the prompt"),
                                   self.cfg), "reading")
        # Empty-string phase is treated as absent -> falls back to state.
        self.assertEqual(classify(payload("generating", ""), self.cfg),
                         "answering")

    def test_long_form_states(self):
        self.assertEqual(classify(payload("reading the prompt"), self.cfg), "reading")
        self.assertEqual(classify(payload("running tool: web_search"), self.cfg), "thinking")

    def test_unknown_state_falls_back(self):
        self.assertEqual(classify(payload("warming kv cache"), self.cfg), "thinking")

    def test_unreachable(self):
        self.assertEqual(classify(None, self.cfg), "idle")
        self.cfg.unreachable_state = "reading"
        self.assertEqual(classify(None, self.cfg), "reading")

    def test_case_insensitive(self):
        self.assertEqual(classify(payload("Reading The Prompt"), self.cfg), "reading")

    def test_missing_live_state(self):
        self.assertEqual(classify({"engine": {}}, self.cfg), "thinking")
        self.assertEqual(classify({"live": {}}, self.cfg), "thinking")
        self.assertEqual(classify({"live": None}, self.cfg), "thinking")

    def test_custom_state_path(self):
        cfg = Config()
        cfg.state_path = "live.slots.0.state"
        p = {"live": {"slots": [{"state": "thinking"}, {"state": "idle"}]}}
        self.assertEqual(classify(p, cfg), "thinking")


class ExtractTests(unittest.TestCase):
    def test_extract_state(self):
        self.assertEqual(extract_state({"live": {"state": "idle"}}), "idle")
        self.assertIsNone(extract_state({}, "live.state"))
        self.assertIsNone(extract_state({"live": "junk"}, "live.state"))
        self.assertIsNone(extract_state({"live": {"state": None}}, "live.state"))


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        cfg = Config()
        self.assertEqual(cfg.poll_seconds, 5.0)
        self.assertEqual(cfg.status_url, "http://127.0.0.1:8080/metrics")
        self.assertEqual(cfg.state_path, "live.state")
        self.assertEqual(cfg.phase_path, "live.phase")
        self.assertEqual(cfg.colors["reading"], (0, 0, 255))
        self.assertEqual(cfg.colors["idle"], (255, 0, 0))

    def test_load_yaml_overrides(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.yaml")
            with open(path, "w") as fh:
                fh.write(
                    "poll_seconds: 2\n"
                    "state_path: live.phase\n"
                    "phase_path: live.label\n"
                    "colors:\n"
                    "  idle: [10, 20, 30]\n"
                    "phase_rules:\n"
                    "  - {contains: 'decode', state: answering}\n"
                    "unreachable_state: thinking\n"
                )
            cfg = load_config(path)
        self.assertEqual(cfg.poll_seconds, 2.0)
        self.assertEqual(cfg.state_path, "live.phase")
        self.assertEqual(cfg.phase_path, "live.label")
        self.assertEqual(cfg.colors["idle"], (10, 20, 30))
        self.assertEqual(cfg.colors["reading"], (0, 0, 255))  # default kept
        self.assertEqual(cfg.phase_rules, [("decode", "answering")])
        self.assertEqual(cfg.unreachable_state, "thinking")

    def test_bad_color_rejected(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.yaml")
            with open(path, "w") as fh:
                fh.write("colors:\n  idle: [300, 0, 0]\n")
            with self.assertRaises(ValueError):
                load_config(path)

    def test_bad_state_rejected(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.yaml")
            with open(path, "w") as fh:
                fh.write("unreachable_state: purple\n")
            with self.assertRaises(ValueError):
                load_config(path)


class FetchTests(unittest.TestCase):
    def test_unreachable_returns_none(self):
        # Port 1 on loopback: connection refused fast.
        self.assertIsNone(fetch_status("http://127.0.0.1:1/metrics", timeout_s=2))


if __name__ == "__main__":
    unittest.main()
