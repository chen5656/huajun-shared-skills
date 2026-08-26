#!/usr/bin/env python3
"""maestro-autopilot — a portable, self-improving harness around Maestro.

The engine is product-agnostic. Everything specific to an app lives in the target
repo's autopilot.json and knowledge/ directory.

    autopilot.py preflight --platform ios
    autopilot.py run       --platform ios [--only ID ...] [--family F]
    autopilot.py plan      [--since-hours 24]      # commits -> work order
    autopilot.py report    [--run-root PATH] [--no-compress-screenshots]
    autopilot.py context                            # lessons for the agent
    autopilot.py lesson    --id ... --scope ... ...
    autopilot.py bug       --id ... --flow ... ...
    autopilot.py pr        --title ...              # branch + commit + PR
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import commits, knowledge, preflight, report, runner  # noqa: E402
from lib.config import Config, ConfigError, find_config  # noqa: E402


def _cfg(args) -> Config:
    return Config(Path(args.config).resolve() if args.config else find_config())


# ---------------------------------------------------------------- commands
def cmd_preflight(args):
    cfg = _cfg(args)
    for plat in ([args.platform] if args.platform else cfg.enabled_platforms()):
        if args.check:
            print(json.dumps(preflight.require_ready(cfg, plat), indent=2))
        else:
            print(json.dumps(preflight.run(cfg, plat, skip_install=args.skip_install), indent=2))


def _compress_screenshots(cfg, args) -> bool:
    """Default on. --no-compress-screenshots on the command line beats the config."""
    if getattr(args, "no_compress_screenshots", False):
        return False
    return bool(cfg.get("report.compress_screenshots", True))


def cmd_run(args):
    cfg = _cfg(args)
    summary = runner.run_batch(
        cfg, args.platform, only=args.only or None, exclude=args.exclude or None,
        status=args.status, families=args.family or None,
        run_root=args.run_root, no_seed=args.no_seed,
    )
    root = Path(summary["run_root"])
    report.write(root, compress=_compress_screenshots(cfg, args))
    print(f"\n{summary['passed']} passed, {summary['failed']} failed — {summary['verdict']}")
    print(f"Report: {root / 'report.html'}")
    return 0 if summary["failed"] == 0 else 1


def cmd_list(args):
    cfg = _cfg(args)
    _, manifest = runner.load_manifest(cfg, args.platform)
    for f in manifest.get("flows", []):
        print(f"{f.get('status','?'):>9}  {f['id']:<42} {f.get('family','')}")


def cmd_plan(args):
    cfg = _cfg(args)
    order = commits.work_order(cfg, since_hours=args.since_hours)
    out = cfg.artifacts / "autopilot" / "work-orders"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (out / f"{stamp}.json").write_text(json.dumps(order, indent=2))
    md = out / f"{stamp}.md"
    md.write_text(commits.render(order))
    print(commits.render(order))
    print(f"\nSaved: {md}")


def cmd_report(args):
    cfg = _cfg(args)
    root = Path(args.run_root) if args.run_root else \
        cfg.artifacts / "autopilot" / "maestro-runs" / f"latest-{args.platform or 'ios'}"
    print(report.write(root.resolve(), compress=_compress_screenshots(cfg, args)))


def cmd_context(args):
    cfg = _cfg(args)
    print(knowledge.context(cfg.knowledge, tuple(args.scope) if args.scope else
                            ("platform", "product", "env")))


def cmd_lesson(args):
    cfg = _cfg(args)
    path, added = knowledge.add_lesson(
        cfg.knowledge, lesson_id=args.id, scope=args.scope, title=args.title,
        symptom=args.symptom, cause=args.cause, rule=args.rule, evidence=args.evidence or "")
    print(f"{'added to' if added else 'already present in'} {path}")


def cmd_bug(args):
    cfg = _cfg(args)
    path, added = knowledge.add_bug(
        cfg.knowledge, bug_id=args.id, title=args.title, flow=args.flow,
        symptom=args.symptom, suspected=args.suspected, repro=args.repro,
        evidence=args.evidence or "")
    print(f"{'added to' if added else 'already present in'} {path}")


def cmd_pr(args):
    """Nightly changes land on a branch and open a PR. Never on the default branch."""
    cfg = _cfg(args)
    if not cfg.get("pr.enabled", True):
        print("pr.enabled is false; leaving changes uncommitted.")
        return 0
    repo = cfg.root
    branch = f"{cfg.get('pr.branch_prefix', 'autopilot/')}{datetime.now():%Y%m%d-%H%M%S}"
    base = cfg.get("pr.base", "main")

    def git(*a, check=True):
        r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)
        if check and r.returncode != 0:
            raise ConfigError(f"git {' '.join(a)} failed: {r.stderr.strip()}")
        return r.stdout.strip()

    if not git("status", "--porcelain"):
        print("No changes to propose.")
        return 0
    git("checkout", "-b", branch)
    git("add", "-A")
    subprocess.run(["git", "-C", str(repo), "commit", "-m", args.title, "-m", args.body or ""],
                   capture_output=True, text=True)
    if args.push:
        git("push", "-u", cfg.get("pr.remote", "origin"), branch)
        gh = subprocess.run(["gh", "pr", "create", "--base", base, "--head", branch,
                             "--title", args.title, "--body", args.body or ""],
                            cwd=repo, capture_output=True, text=True)
        print(gh.stdout or gh.stderr)
    else:
        print(f"Committed to {branch}. Push with:\n  git -C {repo} push -u origin {branch}")
    return 0


# ---------------------------------------------------------------- parser
def main(argv=None):
    ap = argparse.ArgumentParser(prog="autopilot", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="path to autopilot.json (default: search upward)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("preflight"); p.add_argument("--platform"); p.add_argument("--check", action="store_true")
    p.add_argument("--skip-install", action="store_true"); p.set_defaults(fn=cmd_preflight)

    p = sub.add_parser("run"); p.add_argument("--platform", required=True)
    p.add_argument("--only", action="append"); p.add_argument("--exclude", action="append")
    p.add_argument("--family", action="append"); p.add_argument("--status", default=None)
    p.add_argument("--run-root"); p.add_argument("--no-seed", action="store_true")
    p.add_argument("--no-compress-screenshots", action="store_true")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("list"); p.add_argument("--platform", required=True); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("plan"); p.add_argument("--since-hours", type=int, default=24); p.set_defaults(fn=cmd_plan)
    p = sub.add_parser("report"); p.add_argument("--run-root"); p.add_argument("--platform")
    p.add_argument("--no-compress-screenshots", action="store_true"); p.set_defaults(fn=cmd_report)
    p = sub.add_parser("context"); p.add_argument("--scope", action="append"); p.set_defaults(fn=cmd_context)

    p = sub.add_parser("lesson")
    for f in ("id", "scope", "title", "symptom", "cause", "rule"):
        p.add_argument(f"--{f}", required=True)
    p.add_argument("--evidence"); p.set_defaults(fn=cmd_lesson)

    p = sub.add_parser("bug")
    for f in ("id", "title", "flow", "symptom", "suspected"):
        p.add_argument(f"--{f}", required=True)
    p.add_argument("--repro", action="append", required=True); p.add_argument("--evidence")
    p.set_defaults(fn=cmd_bug)

    p = sub.add_parser("pr"); p.add_argument("--title", required=True); p.add_argument("--body")
    p.add_argument("--push", action="store_true"); p.set_defaults(fn=cmd_pr)

    args = ap.parse_args(argv)
    try:
        return args.fn(args) or 0
    except ConfigError as e:
        print(f"\n[autopilot] {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
