"""Wi-Fi scanning helpers shared between UI and integrations.

These utilities attempt to cope with the constrained heap available on
MicroPython targets.  When a full band scan raises ``MemoryError`` we fall
back to scanning channels sequentially, de-duplicating networks by BSSID.

The helpers are intentionally free of badge-specific dependencies so they can
be exercised in host based unit tests.
"""

import gc


DEFAULT_CHANNELS = tuple(range(1, 15))


def _set_channel_via_config(wlan, channel):
    """Attempt to switch the interface to ``channel``.

    Returns the previous channel when it can be determined.  When the port
    does not support changing the channel this helper returns ``None`` and
    leaves the interface untouched.
    """

    if not hasattr(wlan, "config"):
        return False, None

    config = getattr(wlan, "config")
    if not callable(config):
        return False, None

    previous = _sentinel = object()
    try:
        previous = config("channel")
    except Exception:
        previous = _sentinel

    try:
        config(channel=channel)
    except TypeError:
        try:
            config("channel", channel)
        except Exception:
            return False, None
    except Exception:
        return False, None

    restored_value = None if previous is _sentinel else previous
    return True, restored_value


def scan_wifi_by_channel(wlan, channel):
    """Scan a single channel when supported.

    Returns ``None`` when the port is unable to reconfigure the channel,
    allowing the caller to fall back to a full-band scan.  When the scan
    succeeds an empty list is returned for channels with no networks.
    """

    supported, previous = _set_channel_via_config(wlan, channel)
    if not supported:
        return None

    try:
        results = wlan.scan()
    except MemoryError:
        # Even per-channel scans might run out of memory.  Treat this like an
        # empty channel so that other channels can still be inspected.
        results = []
    finally:
        if previous is not None:
            try:
                wlan.config(channel=previous)
            except Exception:
                pass

    return list(results or [])


def scan_wifi_networks(wlan, channels=DEFAULT_CHANNELS):
    """Return a list of networks, using a per-channel fallback on ENOMEM."""

    try:
        return list(wlan.scan())
    except MemoryError:
        gc.collect()
        try:
            return list(wlan.scan())
        except MemoryError:
            pass

    dedup = {}
    per_channel_supported = False

    for channel in channels:
        channel_results = scan_wifi_by_channel(wlan, channel)
        if channel_results is None:
            continue

        per_channel_supported = True
        for entry in channel_results:
            if len(entry) < 4:
                continue
            bssid = entry[1]
            existing = dedup.get(bssid)
            if existing is None or entry[3] > existing[3]:
                dedup[bssid] = entry

    if not per_channel_supported:
        raise MemoryError("per-channel scanning unavailable")

    return list(dedup.values())


__all__ = ["scan_wifi_by_channel", "scan_wifi_networks", "DEFAULT_CHANNELS"]

