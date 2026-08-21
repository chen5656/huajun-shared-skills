"""Failure triage.

Four classes, in the order that matters:

  environment  — the runtime lied to us (wrong device, dead dev server, wrong
                 build, exhausted quota, hung driver). Fix the machine, not the test.
  harness      — Maestro/driver level (syntax, timeout, hung CLI, deadline).
  test         — the flow is wrong (stale selector, missing modal gate, timing).
  app_bug      — the flow is sound, the environment is stable, and the product
                 genuinely does the wrong thing. REPORT, never fix.
  unknown      — not classifiable from the evidence at hand. Never guess.

Rules are patterns over the log and the run context. A rule may declare
`needs_screenshot: true` for the failure modes whose log line is indistinguishable
from an ordinary assertion timeout — the classifier then refuses to claim the class
without a human/agent looking at the image, rather than asserting it confidently.

Projects extend this from knowledge/TRIAGE.json; the engine ships only rules that
are true of Maestro itself.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

BUILTIN_RULES = [
    {
        "id": "no-device-pinned",
        "klass": "environment",
        "pattern": r"Detected connected iPhone|Apple account team ID must be specified",
        "explain": "Maestro grabbed a physical iPhone because no simulator was pinned.",
        "fix": "Boot the configured simulator and re-run preflight.",
    },
    {
        "id": "driver-deadline",
        "klass": "harness",
        "pattern": r"DEADLINE_EXCEEDED|Unable to launch app|Connection refused.*:7001",
        "explain": "A previous maestro.cli process is still holding the driver connection.",
        "fix": "Kill the leftover maestro.cli.AppKt pid, then retry once — it reconnects.",
    },
    {
        "id": "dev-server-missing",
        "klass": "environment",
        "pattern": r"No development servers found|http://.*:8081.*not found",
        "explain": "The app cannot reach the dev server, so every flow dies in setup.",
        "fix": "Start the dev server without CI-style env vars, then re-run preflight.",
    },
    {
        "id": "native-module-missing",
        "klass": "environment",
        "pattern": r"Base module not found|did you do a pod install|dyld.*Library not loaded",
        "explain": "The installed binary predates a new native dependency.",
        "fix": "Reinstall pods / rebuild the native app; a JS reload cannot fix this.",
    },
    {
        "id": "syntax",
        "klass": "test",
        "pattern": r"check-syntax|Invalid syntax|Unrecognized field|Failed to parse",
        "explain": "The flow YAML itself is invalid.",
        "fix": "Run maestro check-syntax on the flow.",
    },
    {
        "id": "assertion-timeout",
        "klass": "test",
        "pattern": r"Assertion is false|Element not found|did not appear",
        "explain": "A selector did not match. Usually stale text, an unhandled modal, or a "
                   "control the a11y tree reports as visible while it is covered.",
        "fix": "Dump the hierarchy before editing the selector; do not guess.",
        "needs_screenshot": True,
    },
    {
        "id": "timeout-killed",
        "klass": "harness",
        "pattern": r"AUTOPILOT_TIMEOUT",
        "explain": "The flow exceeded per_flow_timeout_seconds and was killed by the runner.",
        "fix": "Re-run the flow alone; a hung driver usually clears.",
    },
]


def load_rules(knowledge_dir: Path) -> list[dict]:
    rules = list(BUILTIN_RULES)
    extra = knowledge_dir / "TRIAGE.json"
    if extra.is_file():
        try:
            rules = json.loads(extra.read_text()).get("rules", []) + rules
        except json.JSONDecodeError:
            print(f"[warn] {extra} is not valid JSON; ignoring project triage rules")
    return rules


def classify(log_text: str, rules: list[dict]) -> dict:
    for rule in rules:
        if re.search(rule["pattern"], log_text, re.IGNORECASE | re.MULTILINE):
            return {
                "class": rule["klass"],
                "rule": rule["id"],
                "explain": rule.get("explain", ""),
                "fix": rule.get("fix", ""),
                "confident": not rule.get("needs_screenshot", False),
                "evidence": "log",
            }
    return {
        "class": "unknown",
        "rule": None,
        "explain": "No triage rule matched. Read the screenshots before assigning a cause.",
        "fix": "",
        "confident": False,
        "evidence": "none",
    }


def batch_verdict(results: list[dict]) -> str:
    """A whole-batch read, because mass failure is almost never mass regression."""
    failed = [r for r in results if not r["passed"]]
    if not failed:
        return "all passed"
    classes = {r["triage"]["class"] for r in failed}
    if len(failed) == len(results) and classes <= {"environment", "harness"}:
        return ("every flow failed with an environment/harness cause — treat as one "
                "environment incident, not N regressions")
    if classes == {"environment"}:
        return "all failures are environmental; no test or app change is warranted"
    return f"mixed failures across classes: {', '.join(sorted(classes))}"
