"""The knowledge base — what makes the loop self-improving instead of self-repeating.

Two stores, both in the TARGET repo (never in the engine):

  LESSONS.md  append-only, structured. One entry per durable fact learned from a
              real run: a trap, a platform behaviour, a selector rule. Entries are
              loaded back into the agent's context at the start of every run, so a
              cause diagnosed once is never re-diagnosed from scratch.
  BUGS.md     product bugs found by tests. Reported, never fixed by the agent.

The discipline that keeps this from rotting: a lesson records a *durable* fact, not
a change log. "X was renamed to Y on date Z" is worthless a month later; "an
accessibilityLabel on a container collapses its subtree" is true forever. When the
product changes, edit the affected lesson in place — do not append a correction.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

LESSON_HEADER = """# Lessons

Durable facts learned from real runs. Loaded into the agent's context before every
run. Edit entries in place when they stop being true; do not append corrections.

Scope: `platform` (true of iOS/Android/Maestro itself and worth upstreaming),
`product` (true of this app only), `env` (true of this machine or account).

---
"""

BUG_HEADER = """# Bugs found by tests

Reported, never fixed by the agent. The owner is the auditor.

---
"""

LESSON_RE = re.compile(r"^## \[(?P<id>[^\]]+)\]", re.MULTILINE)


def _ensure(path: Path, header: str) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(header)
    return path


def lessons_path(knowledge_dir: Path) -> Path:
    return _ensure(knowledge_dir / "LESSONS.md", LESSON_HEADER)


def bugs_path(knowledge_dir: Path) -> Path:
    return _ensure(knowledge_dir / "BUGS.md", BUG_HEADER)


def existing_ids(path: Path) -> set[str]:
    return set(LESSON_RE.findall(path.read_text())) if path.exists() else set()


def add_lesson(knowledge_dir: Path, *, lesson_id: str, scope: str, title: str,
               symptom: str, cause: str, rule: str, evidence: str = "") -> tuple[Path, bool]:
    """Append one lesson. Returns (path, added). Duplicate ids are refused, not
    silently appended — a knowledge base that accumulates near-duplicates stops
    being read, which is the same as having none."""
    path = lessons_path(knowledge_dir)
    if lesson_id in existing_ids(path):
        return path, False
    if scope not in ("platform", "product", "env"):
        raise ValueError("scope must be platform | product | env")
    entry = f"""
## [{lesson_id}] {title}

- **Scope:** {scope}
- **Learned:** {date.today().isoformat()}
- **Symptom:** {symptom}
- **Cause:** {cause}
- **Rule:** {rule}
"""
    if evidence:
        entry += f"- **Evidence:** {evidence}\n"
    with path.open("a") as fh:
        fh.write(entry)
    return path, True


def add_bug(knowledge_dir: Path, *, bug_id: str, title: str, flow: str, symptom: str,
            suspected: str, repro: list[str], evidence: str = "") -> tuple[Path, bool]:
    path = bugs_path(knowledge_dir)
    if bug_id in existing_ids(path):
        return path, False
    steps = "\n".join(f"  {i}. {s}" for i, s in enumerate(repro, 1))
    entry = f"""
## [{bug_id}] {title}

- **Found:** {date.today().isoformat()} by `{flow}`
- **Symptom:** {symptom}
- **Suspected root cause:** {suspected}
- **Reproduction:**
{steps}
"""
    if evidence:
        entry += f"- **Evidence:** {evidence}\n"
    with path.open("a") as fh:
        fh.write(entry)
    return path, True


def context(knowledge_dir: Path, scopes: tuple[str, ...] = ("platform", "product", "env")) -> str:
    """Render the lessons an agent should read before touching anything."""
    path = lessons_path(knowledge_dir)
    text = path.read_text()
    blocks = re.split(r"\n(?=## \[)", text)
    kept = [b for b in blocks[1:] if any(f"**Scope:** {s}" in b for s in scopes)]
    if not kept:
        return "No lessons recorded yet."
    return blocks[0].split("---")[0] + "\n---\n" + "\n".join(kept)
