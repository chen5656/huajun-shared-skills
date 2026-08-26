"""Batch runner.

Differences from a naive `for flow in flows: maestro test` loop, each of which
comes from a specific wasted hour:

  * per-flow timeout — one hung Maestro process must not block the batch forever;
  * PROGRESS.md rewritten before every flow, plus a stable `latest-<platform>`
    symlink, so a run in flight can be watched without hunting a timestamped folder;
  * debug output always on — without it a failure leaves no screenshot to inspect;
  * an explicit run root, never the cwd, so named captures cannot litter the repo;
  * seeding failures fail the flow instead of silently running it on stale data.
"""
from __future__ import annotations

import json
import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path

from . import preflight, triage
from .config import Config, ConfigError, java_env


def load_manifest(cfg: Config, platform: str) -> tuple[Path, dict]:
    p = cfg.platform(platform)
    path = cfg.resolve(p["manifest"])
    if not path or not path.is_file():
        raise ConfigError(f"Manifest {p['manifest']} not found")
    return path, json.loads(path.read_text())


def select_flows(cfg: Config, manifest: dict, *, only=None, exclude=None,
                 status=None, families=None) -> list[dict]:
    status = status or cfg.get("run.default_status", "active")
    exclude_tags = set(cfg.get("run.exclude_tags", []))
    flows = []
    for f in manifest.get("flows", []):
        if only:
            if f["id"] not in only:
                continue
        else:
            if status and f.get("status") != status:
                continue
            if families and f.get("family") not in families:
                continue
            if exclude_tags & {t for t in f.keys() if f.get(t) is True}:
                continue
        if exclude and f["id"] in exclude:
            continue
        flows.append(f)
    return flows


def _run_root(cfg: Config, platform: str, explicit: str | None) -> Path:
    base = cfg.artifacts / "autopilot" / "maestro-runs"
    root = cfg.resolve(explicit) if explicit else base / f"{datetime.now():%Y%m%d-%H%M%S}-{platform}"
    root.mkdir(parents=True, exist_ok=True)
    link = base / f"latest-{platform}"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(root, target_is_directory=True)
    return root


def _progress(root: Path, platform: str, flows: list[dict], results: list[dict], current: str | None):
    lines = [f"# Run progress — {platform}", "",
             f"- Run root: `{root}`",
             f"- Flows: {len(results)}/{len(flows)} finished",
             f"- Passed: {sum(1 for r in results if r['passed'])}",
             f"- Failed: {sum(1 for r in results if not r['passed'])}",
             f"- Currently running: `{current or '—'}`",
             f"- Updated: {datetime.now():%Y-%m-%d %H:%M:%S}", "",
             "| flow | result | class | seconds |", "|---|---|---|---|"]
    for r in results:
        lines.append(f"| `{r['id']}` | {'pass' if r['passed'] else 'FAIL'} "
                     f"| {r['triage']['class'] if not r['passed'] else '—'} | {r['seconds']:.0f} |")
    (root / "PROGRESS.md").write_text("\n".join(lines) + "\n")


def _seed(cfg: Config, flow: dict, run_id: str, flow_dir: Path) -> dict:
    spec = cfg.get("seed") or {}
    want = flow.get("seed")
    if not spec.get("command") or not want:
        return {}
    count = want.get("count", 1) if isinstance(want, dict) else 1
    prefix = spec.get("env_prefix", "SEED")
    env_vars: dict[str, str] = {}
    for i in range(1, count + 1):
        marker = run_id if i == 1 else f"{run_id}_{i}"
        cmd = spec["command"].format(run_id=marker)
        if isinstance(want, dict) and want.get("fixture"):
            cmd += f" --fixture {shlex.quote(want['fixture'])}"
        r = subprocess.run(cmd, shell=True, cwd=cfg.root, capture_output=True,
                           text=True, timeout=300, stdin=subprocess.DEVNULL)
        (flow_dir / "seed.log").write_text(r.stdout + r.stderr)
        if r.returncode != 0:
            raise ConfigError(f"Seeding failed for {flow['id']}: see {flow_dir / 'seed.log'}")
        suffix = "" if i == 1 else f"_{i}"
        env_vars[f"{prefix}_MARKER{suffix}"] = marker
        try:
            payload = json.loads(r.stdout.strip().splitlines()[-1])
            for k, v in payload.items():
                env_vars[f"{prefix}_{k.upper()}{suffix}"] = str(v)
        except (json.JSONDecodeError, IndexError):
            pass
    return env_vars


def run_batch(cfg: Config, platform: str, *, only=None, exclude=None, status=None,
              families=None, run_root=None, no_seed=False) -> dict:
    record = preflight.require_ready(cfg, platform)
    device = record["target"].get("udid") or record["target"].get("serial")
    manifest_path, manifest = load_manifest(cfg, platform)
    maestro_dir = cfg.resolve(manifest.get("maestro_dir", ".")) or cfg.root
    flows = select_flows(cfg, manifest, only=only, exclude=exclude, status=status, families=families)
    if not flows:
        raise ConfigError("No flows selected")

    batch_started = time.time()
    root = _run_root(cfg, platform, run_root)
    latest = cfg.artifacts / "autopilot" / "maestro-runs" / f"latest-{platform}"
    print(f"Run root: {root}\nWatch: cat {latest}/PROGRESS.md")
    rules = triage.load_rules(cfg.knowledge)
    timeout = cfg.get("run.per_flow_timeout_seconds", 600)
    env = java_env(cfg)
    results: list[dict] = []
    _progress(root, platform, flows, results, None)

    for flow in flows:
        _progress(root, platform, flows, results, flow["id"])
        flow_dir = root / flow["id"]
        flow_dir.mkdir(parents=True, exist_ok=True)
        started = time.time()
        flow_file = (maestro_dir / flow["file"]).resolve()
        extra_env: dict[str, str] = {}
        log = ""
        try:
            if not no_seed:
                extra_env = _seed(cfg, flow, root.name, flow_dir)
        except ConfigError as e:
            log = f"SEED FAILURE: {e}"

        if not log:
            cmd = preflight._maestro(cfg) + ["--device", device, "test", str(flow_file),
                                             "--debug-output", str(flow_dir / "debug"),
                                             "--flatten-debug-output",
                                             "--test-output-dir", str(flow_dir / "test-output")]
            for k, v in extra_env.items():
                cmd += ["-e", f"{k}={v}"]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, env={**env, **extra_env},
                                      cwd=root, stdin=subprocess.DEVNULL, timeout=timeout)
                log, code = proc.stdout + proc.stderr, proc.returncode
            except subprocess.TimeoutExpired as e:
                subprocess.run(["pkill", "-f", "maestro.cli.AppKt"], capture_output=True)
                log = (e.stdout or b"").decode(errors="replace") + \
                      f"\nAUTOPILOT_TIMEOUT: killed after {timeout}s"
                code = 124
        else:
            code = 1

        (flow_dir / "maestro.log").write_text(log)
        passed = code == 0
        shots = sorted(str(p.relative_to(root)) for p in flow_dir.rglob("*.png"))
        results.append({
            "id": flow["id"], "file": str(flow["file"]), "passed": passed,
            "exit_code": code, "seconds": time.time() - started,
            "seed": extra_env, "screenshots": shots,
            "triage": {"class": "pass"} if passed else triage.classify(log, rules),
        })
        if platform == "android" and cfg.platform("android").get("restore_connectivity", True):
            from . import devices
            devices.restore_connectivity(device)
        _progress(root, platform, flows, results, None)

    summary = {
        "platform": platform, "device": device, "run_root": str(root),
        "app_id": record.get("app_id"), "app_version": record.get("app_version"),
        "started_at": datetime.fromtimestamp(batch_started).isoformat(timespec="seconds"),
        "at": datetime.now().isoformat(timespec="seconds"),
        "wall_seconds": time.time() - batch_started,
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "verdict": triage.batch_verdict(results),
        "results": results,
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2))
    _progress(root, platform, flows, results, None)
    return summary
