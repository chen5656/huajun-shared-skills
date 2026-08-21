"""Device pinning.

The single most expensive class of wasted time in mobile black-box testing is
running a suite against the wrong target. Maestro picks a device implicitly
when none is pinned, and the failures it produces are indistinguishable from
selector regressions. This module makes the target explicit and refuses to
proceed when it cannot be proven.
"""
from __future__ import annotations

import json
import re
import subprocess

from .config import Config, ConfigError


def _run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


# ---------------------------------------------------------------- iOS
def booted_simulators() -> list[dict]:
    out = _run(["xcrun", "simctl", "list", "devices", "booted", "--json"]).stdout
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    devices = []
    for runtime, entries in data.get("devices", {}).items():
        for d in entries:
            if d.get("state") == "Booted":
                devices.append({"udid": d["udid"], "name": d["name"], "runtime": runtime})
    return devices


def resolve_ios(cfg: Config, platform: dict, boot: bool = True) -> dict:
    want = platform.get("device", {})
    udid, name = want.get("udid"), want.get("name")
    known_bad = want.get("known_bad", [])
    if name and any(bad.lower() == name.lower() for bad in known_bad):
        raise ConfigError(
            f"Configured simulator '{name}' is listed in known_bad. "
            "Pick another and record why in the knowledge base."
        )

    booted = booted_simulators()
    match = None
    if udid:
        match = next((d for d in booted if d["udid"] == udid), None)
    if not match and name:
        match = next((d for d in booted if name.lower() in d["name"].lower()), None)

    if not match and boot and udid:
        _run(["xcrun", "simctl", "boot", udid], timeout=180)
        match = next((d for d in booted_simulators() if d["udid"] == udid), None)

    if not match:
        raise ConfigError(
            f"No booted simulator matches device config {want!r}. "
            "Boot it (`xcrun simctl boot <udid>`) before running; an unpinned "
            "Maestro run will grab a connected iPhone or Android phone instead."
        )

    # A connected Android phone silently steals unpinned iOS runs.
    strays = [d for d in adb_devices() if d["state"] == "device"]
    return {**match, "android_attached": [d["serial"] for d in strays]}


# ------------------------------------------------------------ Android
def adb_devices() -> list[dict]:
    try:
        out = _run(["adb", "devices"]).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    devices = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            devices.append({"serial": parts[0], "state": parts[1]})
    return devices


def resolve_android(cfg: Config, platform: dict) -> dict:
    want = platform.get("device", {})
    allow_emulator = want.get("allow_emulator", False)
    devices = [d for d in adb_devices() if d["state"] == "device"]
    if not allow_emulator:
        devices = [d for d in devices if not d["serial"].startswith("emulator-")]

    unauthorized = [d for d in adb_devices() if d["state"] != "device"]
    if not devices:
        detail = f" (found, but not usable: {unauthorized})" if unauthorized else ""
        raise ConfigError(
            "No authorized Android device connected"
            + ("" if allow_emulator else " (emulators are disabled by config)")
            + detail
            + ". Stop and report — do not start an emulator to unblock."
        )

    serial = want.get("serial")
    if serial:
        match = next((d for d in devices if d["serial"] == serial), None)
        if not match:
            raise ConfigError(
                f"Configured Android serial {serial} is not connected. "
                f"Connected: {[d['serial'] for d in devices]}. Serial mismatch is a "
                "stop condition — do not silently run against another phone."
            )
        return match
    if len(devices) > 1:
        print(f"[warn] {len(devices)} devices connected; using {devices[0]['serial']}")
    return devices[0]


def installed_is_debuggable(serial: str, app_id: str) -> bool | None:
    """Return True/False, or None when the package is not installed."""
    out = _run(["adb", "-s", serial, "shell", "dumpsys", "package", app_id]).stdout
    if not out.strip() or "Unable to find package" in out:
        return None
    return bool(re.search(r"\bDEBUGGABLE\b", out))


def app_in_foreground(serial: str, app_id: str) -> bool:
    out = _run(["adb", "-s", serial, "shell", "dumpsys", "window"]).stdout
    return app_id in out


def restore_connectivity(serial: str) -> None:
    """Airplane mode is system state; turning wifi/data back on does not clear it.

    Order matters, and this must run on failure paths too — the test rig may be
    someone's daily-driver phone.
    """
    for cmd in (
        ["shell", "cmd", "connectivity", "airplane-mode", "disable"],
        ["shell", "svc", "wifi", "enable"],
        ["shell", "svc", "data", "enable"],
    ):
        _run(["adb", "-s", serial, *cmd], timeout=30)
