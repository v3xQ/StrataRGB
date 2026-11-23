"""OpenRGB SDK client wrapper. Sets one solid color across every device.

The openrgb package import is deferred so dry-run/tests work without it.
"""

from __future__ import annotations

import logging
from typing import Sequence

log = logging.getLogger("stratargb.lights")


class LightsError(RuntimeError):
    pass


class OpenRGBLights:
    def __init__(self, host: str, port: int, client_name: str):
        self.host = host
        self.port = port
        self.client_name = client_name
        self._client = None

    def _connect(self):
        from openrgb import OpenRGBClient  # deferred: hard dep only when live

        self._client = OpenRGBClient(
            address=self.host, port=self.port, name=self.client_name
        )
        log.info(
            "connected to OpenRGB %s:%d (%d devices)",
            self.host,
            self.port,
            len(self._client.devices),
        )

    def set_color(self, rgb: Sequence[int]) -> None:
        """Set *rgb* on every device. Raises LightsError if ALL devices fail."""
        if self._client is None:
            self._connect()
        assert self._client is not None  # for type-checkers; _connect raises on failure
        from openrgb.utils import RGBColor

        color = RGBColor(*rgb)
        failures = []
        applied = 0
        for device in list(self._client.devices):
            try:
                device.set_color(color)
                applied += 1
            except Exception as exc:  # per-device: one odd device must not block the rest
                failures.append(f"{device.name}: {exc}")
        if failures:
            log.warning("devices failed: %s", "; ".join(failures))
        if applied == 0:
            # Drop the client so the next call reconnects (OpenRGB app restarted, etc.)
            self._client = None
            raise LightsError(
                "no device accepted color: " + ("; ".join(failures) or "no devices")
            )

    def close(self):
        self._client = None


class DryRunLights:
    """Logs what would be set; used with --dry-run and in tests."""

    def __init__(self):
        self.last = None

    def set_color(self, rgb: Sequence[int]) -> None:
        self.last = tuple(rgb)
        log.info("[dry-run] would set all devices to rgb=%s", tuple(rgb))

    def close(self):
        pass
