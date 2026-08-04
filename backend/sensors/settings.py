"""Persistent settings (ADR 0007, 0010, 0013).

Backend-owned settings, stored as JSON when a path is supplied (the Decky
runtime passes a file under the plugin dir; tests pass ``None``).  All
changes are persisted eagerly so a crash cannot leave the plugin enabled
against the user's last explicit choice.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

MAX_REPORTS = 20  # bounded local retention (ADR 0010, 0013)


class Settings:
    """Minimal JSON-backed settings bag.

    Fields (defaults): ``enabled`` (default off, ADR 0007),
    ``notice_acknowledged`` (one-time kinetosis notice, ADR 0010),
    ``report_consent`` (opt-in anonymous reports, ADR 0013), and a bounded
    local store of comfort reports (nothing leaves the device yet).
    """

    def __init__(self, path: Optional[str | Path] = None) -> None:
        self.path = Path(path) if path else None
        self.enabled = False
        self.notice_acknowledged = False
        self.report_consent = False
        self.reports: list = []
        self._load()

    def _load(self) -> None:
        if self.path is None or not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return
        self.enabled = bool(data.get("enabled", False))
        self.notice_acknowledged = bool(data.get("notice_acknowledged", False))
        self.report_consent = bool(data.get("report_consent", False))
        reports = data.get("reports")
        if isinstance(reports, list):
            self.reports = reports[-MAX_REPORTS:]

    def save(self) -> None:
        if self.path is None:
            return
        payload = {
            "enabled": self.enabled,
            "notice_acknowledged": self.notice_acknowledged,
            "report_consent": self.report_consent,
            "reports": self.reports,
        }
        # Atomic-ish write: temp file in the same dir, then rename.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(payload, fh)
            os.replace(tmp, self.path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        self.save()

    def set_notice_acknowledged(self, ack: bool) -> None:
        self.notice_acknowledged = bool(ack)
        self.save()

    def set_report_consent(self, consent: bool) -> None:
        self.report_consent = bool(consent)
        self.save()

    def record_report(self, report: dict) -> None:
        """Append a comfort report to the bounded local store (ADR 0013).
        Network submission is a later slice; nothing leaves the device yet."""
        self.reports.append(report)
        self.reports = self.reports[-MAX_REPORTS:]
        self.save()
