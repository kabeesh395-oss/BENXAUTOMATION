"""Resource monitoring, storage safeguards, and emergency stop."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from benxautomation.errors import BenxError
from benxautomation.logger import get_logger

log = get_logger(__name__)


class StorageSafeguardError(BenxError):
    """Raised when available storage is below safe operating threshold."""


class EmergencyStopTriggered(BenxError):
    """Raised when emergency stop signal is active."""


@dataclass
class SystemResourceStatus:
    """Snapshot of system storage and health."""
    free_disk_bytes: int
    total_disk_bytes: int
    free_disk_gb: float
    is_safe: bool
    emergency_stop_active: bool


class ResourceMonitor:
    """Monitors system resources and enforces storage and emergency stop safeguards."""

    MIN_FREE_DISK_BYTES = 500 * 1024 * 1024  # 500 MB minimum free disk

    def __init__(
        self,
        watch_dir: Path | str = ".",
        *,
        min_free_bytes: int = MIN_FREE_DISK_BYTES,
        emergency_signal_file: Path | str = "emergency.stop",
    ):
        self.watch_dir = Path(watch_dir)
        self.min_free_bytes = min_free_bytes
        self.emergency_signal_file = Path(emergency_signal_file)
        self._manual_stop = False

    def trigger_emergency_stop(self) -> None:
        """Programmatically activate emergency stop."""
        self._manual_stop = True
        log.warning("EMERGENCY STOP manually triggered.")

    def clear_emergency_stop(self) -> None:
        """Clear emergency stop flag and remove signal file."""
        self._manual_stop = False
        if self.emergency_signal_file.exists():
            try:
                self.emergency_signal_file.unlink()
            except OSError:
                pass
        log.info("Emergency stop cleared.")

    def check_emergency_stop(self) -> bool:
        """Return True if emergency stop is triggered."""
        if self._manual_stop:
            return True
        if self.emergency_signal_file.is_file():
            return True
        return False

    def check_storage_safety(self) -> bool:
        """Return True if free disk space is above minimum safety threshold."""
        try:
            usage = shutil.disk_usage(str(self.watch_dir.resolve()))
            return usage.free >= self.min_free_bytes
        except Exception as exc:
            log.warning("Could not check disk usage: %s", exc)
            return True

    def get_status(self) -> SystemResourceStatus:
        """Return full resource snapshot."""
        usage = shutil.disk_usage(str(self.watch_dir.resolve()))
        free_gb = round(usage.free / (1024 ** 3), 2)
        safe = usage.free >= self.min_free_bytes
        stop_active = self.check_emergency_stop()

        return SystemResourceStatus(
            free_disk_bytes=usage.free,
            total_disk_bytes=usage.total,
            free_disk_gb=free_gb,
            is_safe=safe,
            emergency_stop_active=stop_active,
        )

    def enforce_safeguards(self) -> None:
        """Check all safeguards; raises exception if unsafe to proceed."""
        if self.check_emergency_stop():
            raise EmergencyStopTriggered("Operation aborted: emergency stop signal is active.")

        if not self.check_storage_safety():
            usage = shutil.disk_usage(str(self.watch_dir.resolve()))
            free_mb = round(usage.free / (1024 ** 2), 1)
            min_mb = round(self.min_free_bytes / (1024 ** 2), 1)
            raise StorageSafeguardError(
                f"Free storage ({free_mb} MB) is below safe minimum ({min_mb} MB). Refusing execution."
            )
