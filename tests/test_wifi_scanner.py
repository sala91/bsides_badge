import errno
import sys
from pathlib import Path

import pytest


LIB_DIR = Path(__file__).resolve().parents[1] / "software" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from wifi_scanner import scan_wifi_by_channel, scan_wifi_networks


class _BaseStubWLAN:
    def __init__(self):
        self._channel = 0

    def config(self, *args, **kwargs):
        if args and args[0] == "channel" and len(args) == 1 and not kwargs:
            return self._channel
        if "channel" in kwargs:
            self._channel = kwargs["channel"]
            return None
        raise TypeError("unsupported config invocation")

    def scan(self):
        return []


class _MemorySavingWLAN(_BaseStubWLAN):
    """Simulate ENOMEM on full scans with working per-channel scans."""

    def __init__(self, channel_results):
        super().__init__()
        self._channel = 0
        self._channel_results = channel_results
        self._full_scan_attempts = 0

    def scan(self):
        if self._channel == 0:
            self._full_scan_attempts += 1
            raise OSError(errno.ENOMEM, "wifi out of memory")
        return self._channel_results.get(self._channel, [])


class _SimpleWLAN(_BaseStubWLAN):
    def __init__(self, results):
        super().__init__()
        self._results = results

    def scan(self):
        if self._channel == 0:
            return self._results
        return [(b"other", b"other", self._channel, -70, 0)]


class _NoConfigWLAN:
    def __init__(self, results, fail=False):
        self._results = results
        self._fail = fail

    def scan(self):
        if self._fail:
            raise OSError(errno.ENOMEM, "wifi out of memory")
        return self._results


def test_scan_wifi_by_channel_sets_channel_and_restores():
    wlan = _BaseStubWLAN()
    wlan._channel = 6

    diagnostics = []
    results = scan_wifi_by_channel(
        wlan,
        11,
        diagnostics=diagnostics,
    )

    assert wlan._channel == 6  # restored to original
    assert results == []
    assert diagnostics == []


def test_scan_wifi_networks_fallback_collects_results():
    channel_results = {
        1: [(b"ssid1", b"\x01", 1, -30, 0)],
        6: [(b"ssid2", b"\x02", 6, -40, 0)],
    }
    wlan = _MemorySavingWLAN(channel_results)

    nets = scan_wifi_networks(wlan, channels=(1, 6, 11))

    assert sorted(nets, key=lambda entry: entry[1]) == [
        (b"ssid1", b"\x01", 1, -30, 0),
        (b"ssid2", b"\x02", 6, -40, 0),
    ]
    assert wlan._full_scan_attempts == 2


def test_scan_wifi_networks_handles_standard_scan():
    expected = [(b"ssid", b"\xaa", 1, -55, 0)]
    wlan = _SimpleWLAN(expected)

    nets = scan_wifi_networks(wlan)

    assert nets == expected


def test_scan_wifi_networks_deduplicates_bssid():
    channel_results = {
        1: [(b"ssid", b"\x01", 1, -70, 0)],
        6: [(b"ssid", b"\x01", 6, -35, 0)],
    }
    wlan = _MemorySavingWLAN(channel_results)

    nets = scan_wifi_networks(wlan, channels=(1, 6))

    assert nets == [(b"ssid", b"\x01", 6, -35, 0)]


def test_scan_wifi_by_channel_without_config_returns_none():
    wlan = _NoConfigWLAN([(b"ssid", b"\x01", 1, -40, 0)])

    diagnostics = []

    assert scan_wifi_by_channel(wlan, 1, diagnostics=diagnostics) is None
    assert diagnostics


def test_scan_wifi_networks_raises_when_no_fallback():
    wlan = _NoConfigWLAN([(b"ssid", b"\x01", 1, -40, 0)], fail=True)

    with pytest.raises(RuntimeError) as excinfo:
        scan_wifi_networks(wlan)

    message = str(excinfo.value)
    assert "full scan attempt" in message
    assert "channel" in message


def test_scan_wifi_networks_raises_other_errors():
    class _FailingWLAN(_BaseStubWLAN):
        def scan(self):
            raise OSError(errno.EIO, "wifi internal error")

    wlan = _FailingWLAN()

    with pytest.raises(OSError) as excinfo:
        scan_wifi_networks(wlan)

    assert excinfo.value.errno == errno.EIO
