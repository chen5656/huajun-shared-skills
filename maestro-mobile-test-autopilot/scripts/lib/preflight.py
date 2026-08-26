"""Preflight: prove the runtime is real before spending an hour against nothing.

Contract:
  * preflight is the ONLY step allowed to prepare the runtime (boot, install,
    start the dev server);
  * every runner calls require_ready() and fails in seconds when it cannot be
    satisfied, instead of producing a suite of look-alike selector failures;
  * the readiness record expires, so a stale one cannot vouch for a rebooted machine.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from . import devices
from .config import Config, ConfigError, java_env

READY_MAX_AGE_HOURS = 12


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ready_path(cfg: Config, platform: str) -> Path:
    d = cfg.artifacts / "autopilot" / "preflight"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{platform}.json"


def port_listening(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def cleanup(app_id: str, serial: str | None = None) -> None:
    """Kill half-dead sessions from an interrupted run before starting a new one."""
    for pattern in ("maestro.cli.AppKt", "idb_companion"):
        subprocess.run(["pkill", "-f", pattern], capture_output=True)
    if serial:
        subprocess.run(["adb", "-s", serial, "shell", "am", "force-stop", app_id], capture_output=True)


def start_dev_server(cfg: Config, spec: dict) -> None:
    port = spec.get("port", 8081)
    if port_listening(port):
        return
    workspace = cfg.resolve(cfg.get("workspace"))
    if not workspace or not workspace.is_dir():
        raise ConfigError("dev_server is configured but `workspace` does not exist")
    env = dict(os.environ)
    # Some CI-ish env vars suppress dev-server registration; the app then cannot
    # find a server and EVERY flow fails at setup, which reads as a mass regression.
    for forbidden in spec.get("forbidden_env", []):
        env.pop(forbidden, None)
    log = cfg.artifacts / "autopilot" / "preflight" / "dev-server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as fh:
        subprocess.Popen(
            spec["start_command"], shell=True, cwd=workspace, env=env,
            stdout=fh, stderr=fh, stdin=subprocess.DEVNULL, start_new_session=True,
        )
    for _ in range(60):
        if port_listening(port):
            return
        time.sleep(1)
    raise ConfigError(f"Dev server did not start listening on {port}; see {log}")


def run(cfg: Config, platform: str, *, reboot: bool = False, skip_install: bool = False) -> dict:
    p = cfg.platform(platform)
    app_id = p["app_id"]

    if platform == "ios":
        cleanup(app_id)
        dev = devices.resolve_ios(cfg, p, boot=True)
        if dev["android_attached"]:
            print(f"[warn] Android device(s) attached: {dev['android_attached']}. "
                  "Every Maestro invocation must be pinned with --device.")
        if p.get("dev_server"):
            start_dev_server(cfg, p["dev_server"])
        target = {"udid": dev["udid"], "name": dev["name"]}
    elif platform == "android":
        dev = devices.resolve_android(cfg, p)
        serial = dev["serial"]
        cleanup(app_id, serial)
        for port in p.get("reverse_ports", []):
            # per-connection state; a re-plug drops it
            subprocess.run(["adb", "-s", serial, "reverse", f"tcp:{port}", f"tcp:{port}"],
                           capture_output=True)
        if not skip_install:
            _install_android(cfg, p, serial)
        _verify_android_variant(p, serial, app_id)
        target = {"serial": serial}
    else:
        raise ConfigError(f"Unknown platform '{platform}'")

    smoke = p.get("smoke_flow")
    if smoke:
        _smoke(cfg, platform, p, target, smoke)

    record = {"platform": platform, "app_id": app_id, "target": target, "at": _now(),
              "app_version": devices.app_version(platform, target, app_id)}
    _ready_path(cfg, platform).write_text(json.dumps(record, indent=2))
    return record


def _install_android(cfg: Config, p: dict, serial: str) -> None:
    variant = p.get("preferred_apk", "release")
    apk = cfg.resolve((p.get("apk_paths") or {}).get(variant))
    if not apk or not apk.is_file():
        build = (p.get("build_command") or "").format(serial=serial, variant=variant)
        raise ConfigError(
            f"{variant} apk not found at {apk}. There is no fallback between variants — "
            f"build it first:\n  {build}"
        )
    r = subprocess.run(["adb", "-s", serial, "install", "-r", str(apk)],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        hint = ""
        if "SIGNATURE" in (r.stdout + r.stderr).upper():
            hint = " Signature mismatch needs a manual `adb uninstall` — stop and report."
        raise ConfigError(f"adb install failed: {r.stdout or r.stderr}.{hint}")


def _verify_android_variant(p: dict, serial: str, app_id: str) -> None:
    """A debug build installed over release fails every flow identically."""
    want = p.get("preferred_apk", "release")
    debuggable = devices.installed_is_debuggable(serial, app_id)
    if debuggable is None:
        raise ConfigError(f"{app_id} is not installed on {serial} after preflight install")
    if want == "release" and debuggable:
        raise ConfigError(
            f"Installed {app_id} is flagged DEBUGGABLE but config asks for the release build. "
            "Aborting: a whole batch against the wrong binary reports as selector regressions."
        )


def _smoke(cfg: Config, platform: str, p: dict, target: dict, flow: str) -> None:
    flow_path = cfg.resolve(flow)
    if not flow_path or not flow_path.is_file():
        raise ConfigError(f"smoke_flow {flow} does not exist")
    out = cfg.artifacts / "autopilot" / "preflight" / f"{datetime.now():%Y%m%d-%H%M%S}-{platform}"
    out.mkdir(parents=True, exist_ok=True)
    if platform == "android":
        serial = target["serial"]
        subprocess.run(["adb", "-s", serial, "shell", "am", "force-stop", p["app_id"]], capture_output=True)
        subprocess.run(["adb", "-s", serial, "shell", "monkey", "-p", p["app_id"], "-c",
                        "android.intent.category.LAUNCHER", "1"], capture_output=True)
        for _ in range(60):
            if devices.app_in_foreground(serial, p["app_id"]):
                break
            time.sleep(1)
        else:
            shot = out / "smoke-failed.png"
            with shot.open("wb") as fh:
                subprocess.run(["adb", "-s", serial, "exec-out", "screencap", "-p"], stdout=fh)
            raise ConfigError(
                f"{p['app_id']} never reached the foreground. See {shot}. "
                "A batch against an app that never started produces failures that all "
                "look like selector regressions."
            )
    device_arg = target.get("udid") or target.get("serial")
    cmd = _maestro(cfg) + ["--device", device_arg, "test", str(flow_path),
                           "--debug-output", str(out / "debug"), "--flatten-debug-output"]
    r = subprocess.run(cmd, capture_output=True, text=True, env=java_env(cfg),
                       stdin=subprocess.DEVNULL, timeout=600)
    (out / "smoke.log").write_text(r.stdout + r.stderr)
    if r.returncode != 0:
        raise ConfigError(f"Preflight smoke flow failed. Log: {out / 'smoke.log'}")


def _maestro(cfg: Config) -> list[str]:
    exe = shutil.which("maestro") or str(Path.home() / ".maestro" / "bin" / "maestro")
    if not Path(exe).exists():
        raise ConfigError("maestro CLI not found on PATH")
    return [exe]


def require_ready(cfg: Config, platform: str) -> dict:
    """Re-verify the recorded runtime, or fail fast with the fix command."""
    path = _ready_path(cfg, platform)
    fix = f"python3 scripts/autopilot.py preflight --platform {platform}"
    if not path.is_file():
        raise ConfigError(f"No preflight record for {platform}. Run:\n  {fix}")
    try:
        record = json.loads(path.read_text())
        stamp = datetime.fromisoformat(record["at"])
        target = record["target"]
        app_id = record["app_id"]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        # A record written by another tool (or a half-written one) vouches for nothing.
        raise ConfigError(
            f"{path} is not a readiness record this engine wrote. Run:\n  {fix}"
        ) from None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    age_h = (datetime.now(timezone.utc) - stamp).total_seconds() / 3600
    if age_h > READY_MAX_AGE_HOURS:
        raise ConfigError(f"Preflight record is {age_h:.1f}h old (max {READY_MAX_AGE_HOURS}h). Run:\n  {fix}")

    p = cfg.platform(platform)
    if platform == "ios":
        if not any(d["udid"] == target["udid"] for d in devices.booted_simulators()):
            raise ConfigError(f"Simulator {target['udid']} is no longer booted. Run:\n  {fix}")
        spec = p.get("dev_server")
        if spec and not port_listening(spec.get("port", 8081)):
            raise ConfigError(f"Dev server on port {spec.get('port', 8081)} is gone. Run:\n  {fix}")
    else:
        if not any(d["serial"] == target["serial"] and d["state"] == "device"
                   for d in devices.adb_devices()):
            raise ConfigError(f"Device {target['serial']} is not connected. Run:\n  {fix}")
        if devices.installed_is_debuggable(target["serial"], app_id) is None:
            raise ConfigError(f"{app_id} is no longer installed. Run:\n  {fix}")
    return record
