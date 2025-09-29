"""Wi-Fi scanning helpers shared between UI and integrations.

These utilities attempt to cope with the constrained heap available on
MicroPython targets.  When a full band scan raises ``MemoryError`` (or the
ESP32-specific ``OSError: wifi out of memory``) we fall back to scanning
channels sequentially, de-duplicating networks by BSSID.  When all strategies
fail a verbose :class:`RuntimeError` is raised so the UI can present useful
diagnostics to the user instead of a vague "out of memory" banner.

The helpers are intentionally free of badge-specific dependencies so they can
be exercised in host based unit tests.
"""

from __future__ import annotations

import errno
import gc
from typing import Iterable, List, Optional


DEFAULT_CHANNELS = tuple(range(1, 15))
_KNOWN_ENOMEM = {getattr(errno, "ENOMEM", 12), 12}


def _format_exception(exc):
    if isinstance(exc, OSError):
        parts = []
        err = getattr(exc, "errno", None)
        if err is not None:
            parts.append(f"errno={err}")
        for arg in exc.args[1:]:
            if isinstance(arg, str) and arg:
                parts.append(arg)
        if not parts and exc.args:
            parts.append(str(exc.args[0]))
        detail = ", ".join(parts) if parts else exc.__class__.__name__
        return f"{exc.__class__.__name__}({detail})"

    text = str(exc)
    return f"{exc.__class__.__name__}({text})" if text else exc.__class__.__name__


def _is_memory_error(exc):
    if isinstance(exc, MemoryError):
        return True

    if isinstance(exc, OSError):
        err = getattr(exc, "errno", None)
        if err in _KNOWN_ENOMEM:
            return True
        text = " ".join(str(arg) for arg in exc.args if isinstance(arg, str)).lower()
        if "out of memory" in text or "enomem" in text:
            return True

    return False


def _set_channel_via_config(wlan, channel, diagnostics: Optional[List[str]] = None):
    if not hasattr(wlan, "config"):
        if diagnostics is not None:
            diagnostics.append("WLAN.config attribute missing")
        return False, None

    config = getattr(wlan, "config")
    if not callable(config):
        if diagnostics is not None:
            diagnostics.append("WLAN.config is not callable")
        return False, None

    sentinel = object()
    previous = sentinel
    try:
        previous = config("channel")
    except Exception as exc:
        if diagnostics is not None:
            diagnostics.append(f"reading current channel failed: {_format_exception(exc)}")

    try:
        config(channel=channel)
    except TypeError:
        try:
            config("channel", channel)
        except Exception as exc:
            if diagnostics is not None:
                diagnostics.append(
                    f"setting channel via positional arguments failed: {_format_exception(exc)}"
                )
            return False, None
    except Exception as exc:
        if diagnostics is not None:
            diagnostics.append(f"setting channel failed: {_format_exception(exc)}")
        return False, None

    restored_value = None if previous is sentinel else previous
    return True, restored_value


def _restore_channel(wlan, previous, diagnostics: Optional[List[str]] = None):
    if previous is None:
        return

    try:
        wlan.config(channel=previous)
    except TypeError:
        try:
            wlan.config("channel", previous)
        except Exception as exc:
            if diagnostics is not None:
                diagnostics.append(
                    f"restoring channel via positional arguments failed: {_format_exception(exc)}"
                )
    except Exception as exc:
        if diagnostics is not None:
            diagnostics.append(f"restoring channel failed: {_format_exception(exc)}")


def scan_wifi_by_channel(wlan, channel, diagnostics: Optional[List[str]] = None):
    """Scan a single channel when supported.

    Returns ``None`` when the port is unable to reconfigure the channel,
    allowing the caller to fall back to a full-band scan.  When the scan
    succeeds an empty list is returned for channels with no networks.
    """

    supported, previous = _set_channel_via_config(wlan, channel, diagnostics)
    if not supported:
        return None

    try:
        results = wlan.scan()
    except Exception as exc:
        if _is_memory_error(exc):
            if diagnostics is not None:
                diagnostics.append(
                    f"scan on channel {channel} exhausted memory: {_format_exception(exc)}"
                )
            results = []
        else:
            if diagnostics is not None:
                diagnostics.append(f"scan on channel {channel} failed: {_format_exception(exc)}")
            raise
    finally:
        _restore_channel(wlan, previous, diagnostics)

    return list(results or [])


def scan_wifi_networks(wlan, channels: Iterable[int] = DEFAULT_CHANNELS):
    """Return a list of networks, using a per-channel fallback on ENOMEM."""

    attempts = []
    for attempt in (1, 2):
        try:
            return list(wlan.scan())
        except Exception as exc:
            if _is_memory_error(exc):
                attempts.append(f"full scan attempt {attempt}: {_format_exception(exc)}")
                if attempt == 1:
                    gc.collect()
                    continue
                break
            raise
    # Only reached when the second attempt raised a memory related failure.

    dedup = {}
    per_channel_supported = False
    per_channel_failures = []

    for channel in channels:
        channel_diag = []
        try:
            channel_results = scan_wifi_by_channel(wlan, channel, diagnostics=channel_diag)
        except Exception as exc:
            per_channel_failures.append(
                f"channel {channel}: {_format_exception(exc)}"
            )
            continue

        if channel_results is None:
            if channel_diag:
                per_channel_failures.append(
                    f"channel {channel}: {'; '.join(channel_diag)}"
                )
            else:
                per_channel_failures.append(f"channel {channel}: channel switching unsupported")
            continue

        per_channel_supported = True
        for entry in channel_results:
            if len(entry) < 4:
                continue
            bssid = entry[1]
            existing = dedup.get(bssid)
            if existing is None or entry[3] > existing[3]:
                dedup[bssid] = entry

    if per_channel_supported:
        return list(dedup.values())

    details = attempts + per_channel_failures
    if not details:
        details.append("no scanning methods succeeded")
    raise RuntimeError(
        "Wi-Fi scan failed after attempting per-channel fallback: "
        + "; ".join(details)
    )


__all__ = ["scan_wifi_by_channel", "scan_wifi_networks", "DEFAULT_CHANNELS"]

