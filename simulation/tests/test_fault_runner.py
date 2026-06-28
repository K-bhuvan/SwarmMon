"""Tests for simulation/fault_runner.py helpers."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fault_runner import fault_delay_seconds, fault_message  # noqa: E402


def test_fault_delay_seconds_from_minute():
    assert fault_delay_seconds({"start_minute": 2}) == 120.0


def test_fault_delay_seconds_from_seconds():
    assert fault_delay_seconds({"start_after_seconds": 15}) == 15.0


def test_fault_message_default():
    msg = fault_message({"type": "sensor_rate_drop", "signal_id": "/scan"})
    assert "/scan" in msg
    assert "sensor_rate_drop" in msg
