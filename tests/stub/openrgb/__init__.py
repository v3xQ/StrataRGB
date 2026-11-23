"""Stub of the openrgb package for offline testing (records set_color calls)."""
from .utils import RGBColor  # noqa: F401

import openrgb_stub_state


class _Device:
    def __init__(self, name):
        self.name = name

    def set_color(self, color):
        openrgb_stub_state.CALLS.append(color)


class OpenRGBClient:
    # lights.py calls OpenRGBClient(address=..., port=..., name=...)
    def __init__(self, address, port, name):
        self.address = address
        self.port = port
        self.name = name
        self.devices = [_Device("stub-mobo"), _Device("stub-kbd")]
