"""Tests for ResourceMonitor and safeguards."""

from pathlib import Path
import pytest

from benxautomation.queue.monitor import (
    EmergencyStopTriggered,
    ResourceMonitor,
    StorageSafeguardError,
)


class TestResourceMonitor:
    def test_default_status_is_safe(self, tmp_path: Path):
        monitor = ResourceMonitor(watch_dir=tmp_path)
        status = monitor.get_status()
        assert status.free_disk_bytes > 0
        assert status.emergency_stop_active is False

    def test_emergency_stop_programmatic(self, tmp_path: Path):
        monitor = ResourceMonitor(watch_dir=tmp_path)
        assert monitor.check_emergency_stop() is False

        monitor.trigger_emergency_stop()
        assert monitor.check_emergency_stop() is True

        with pytest.raises(EmergencyStopTriggered):
            monitor.enforce_safeguards()

        monitor.clear_emergency_stop()
        assert monitor.check_emergency_stop() is False

    def test_emergency_stop_file_signal(self, tmp_path: Path):
        sig_file = tmp_path / "stop.signal"
        monitor = ResourceMonitor(watch_dir=tmp_path, emergency_signal_file=sig_file)

        assert monitor.check_emergency_stop() is False

        sig_file.write_text("STOP", encoding="utf-8")
        assert monitor.check_emergency_stop() is True

        with pytest.raises(EmergencyStopTriggered):
            monitor.enforce_safeguards()

    def test_storage_safeguard_threshold_breach(self, tmp_path: Path):
        # Set an impossibly high minimum threshold (e.g. 100 Terabytes)
        huge_bytes = 100 * 1024 * 1024 * 1024 * 1024
        monitor = ResourceMonitor(watch_dir=tmp_path, min_free_bytes=huge_bytes)

        assert monitor.check_storage_safety() is False
        with pytest.raises(StorageSafeguardError):
            monitor.enforce_safeguards()
