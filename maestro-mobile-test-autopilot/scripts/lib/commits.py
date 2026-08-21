"""Commit-driven coverage: turn the last N hours of product commits into a work order.

The engine does not write tests. It answers the question a test author needs
answered first — *what changed, and which flows already cover it?* — and hands the
agent a work order with each changed surface marked covered or uncovered.

Deliberately conservative: the mapping is glob-based and declared in config, so a
wrong guess is visible and fixable, not buried in a model's reasoning.
"""
from __future__ import annotations

import fnmatch
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from .config import Config


def changed_files(repo: Path, since_hours: int = 24, base: str | None = None) -> list[dict]:
    since = (datetime.now() - timedelta(hours=since_hours)).isoformat(timespec="seconds")
    rev = f"--since={since}" if not base else f"{base}..HEAD"
    log = subprocess.run(
        ["git", "-C", str(repo), "log", rev, "--no-merges",
         "--pretty=format:%H%x1f%an%x1f%s", "--name-only"],
        capture_output=True, text=True, timeout=120,
    ).stdout
    commits, current = [], None
    for line in log.splitlines():
        if "\x1f" in line:
            if current:
                commits.append(current)
            sha, author, subject = line.split("\x1f")
            current = {"sha": sha[:10], "author": author, "subject": subject, "files": []}
        elif line.strip() and current:
            current["files"].append(line.strip())
    if current:
        commits.append(current)
    return commits


def _covered_families(cfg: Config, path: str) -> list[str]:
    fams: list[str] = []
    for rule in cfg.get("coverage.map", []):
        if fnmatch.fnmatch(path, rule["glob"]):
            fams.extend(rule.get("families", []))
    return sorted(set(fams))


def _ignored(cfg: Config, path: str) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in cfg.get("coverage.ignore_globs", []))


def work_order(cfg: Config, *, since_hours: int = 24, platforms: list[str] | None = None) -> dict:
    workspace = cfg.resolve(cfg.get("workspace"))
    commits = changed_files(workspace, since_hours) if workspace else []
    platforms = platforms or cfg.enabled_platforms()

    manifests = {}
    for plat in platforms:
        try:
            from .runner import load_manifest
            _, m = load_manifest(cfg, plat)
            manifests[plat] = m
        except Exception as e:  # a missing manifest must not kill the nightly
            manifests[plat] = {"flows": [], "error": str(e)}

    surfaces: dict[str, dict] = {}
    for c in commits:
        for f in c["files"]:
            if _ignored(cfg, f):
                continue
            fams = _covered_families(cfg, f)
            entry = surfaces.setdefault(f, {"families": fams, "commits": [], "flows": []})
            entry["commits"].append(c["sha"])

    for path, entry in surfaces.items():
        for plat, m in manifests.items():
            for flow in m.get("flows", []):
                if flow.get("family") in entry["families"] and flow.get("status") == "active":
                    entry["flows"].append({"platform": plat, "id": flow["id"]})

    covered = {p: e for p, e in surfaces.items() if e["flows"]}
    uncovered = {p: e for p, e in surfaces.items() if not e["flows"] and e["families"]}
    unmapped = {p: e for p, e in surfaces.items() if not e["families"]}

    affected_flow_ids = sorted({f["id"] for e in covered.values() for f in e["flows"]})
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "since_hours": since_hours,
        "commits": commits,
        "platforms": platforms,
        "affected_flows": affected_flow_ids,
        "covered_surfaces": covered,
        "uncovered_surfaces": uncovered,
        "unmapped_surfaces": unmapped,
    }


def render(order: dict) -> str:
    L = [f"# Nightly work order ({order['generated_at']})", "",
         f"Window: last {order['since_hours']}h — {len(order['commits'])} commit(s).", ""]
    if not order["commits"]:
        L += ["No product commits in the window. Nothing to generate; run the regression "
              "set only if the schedule calls for it.", ""]
        return "\n".join(L)
    L += ["## Commits", ""]
    for c in order["commits"]:
        L.append(f"- `{c['sha']}` {c['subject']} — {len(c['files'])} file(s)")
    L += ["", "## 1. Run these existing flows (changed surface is already covered)", ""]
    L += [f"- `{fid}`" for fid in order["affected_flows"]] or ["- (none)"]
    L += ["", "## 2. Uncovered changed surfaces — propose a flow, do not invent one silently", ""]
    for path, e in order["uncovered_surfaces"].items():
        L.append(f"- `{path}` → families {e['families']} have no active flow")
    if not order["uncovered_surfaces"]:
        L.append("- (none)")
    L += ["", "## 3. Unmapped files — coverage.map has no rule for these", "",
          "Add a rule to config, or confirm they are not user-facing.", ""]
    for path in list(order["unmapped_surfaces"])[:40]:
        L.append(f"- `{path}`")
    if not order["unmapped_surfaces"]:
        L.append("- (none)")
    return "\n".join(L) + "\n"
