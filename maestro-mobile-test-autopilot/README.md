# maestro-autopilot

A portable harness that lets an AI coding agent run [Maestro](https://maestro.mobile.dev)
mobile black-box tests **unattended** — and still produce a result you can trust.

It is built around one uncomfortable observation: an unattended mobile test run fails
in ways that all look the same. A dead dev server, a phone stolen by an unpinned
Maestro invocation, a debug build installed over a release build, and a genuinely stale
selector produce log output you cannot tell apart. So the default outcome of naive
automation is not a false negative — it is a **confident, detailed, wrong report**.

Everything here is a defence against that.

## What it does

- **Pins the target device** and refuses to run when it cannot prove which device it is on.
- **Mandatory preflight** — the only step allowed to prepare the runtime. Boots the
  device, starts the dev server, installs and *verifies the build variant*, runs a smoke
  flow, and writes an expiring readiness record. Every later command re-checks it and
  fails in seconds rather than burning an hour against nothing.
- **Triages failures into four classes** — environment / harness / test / app-bug — and
  marks a class *unconfident* when the log alone cannot prove it, so the agent looks at
  the screenshot instead of asserting a cause.
- **Repairs within a hard boundary.** Test YAML freely; in app source, only non-visible
  accessibility metadata. Product bugs get written up, never fixed.
- **Learns.** Every diagnosis that took real work becomes a durable lesson in the target
  repo's knowledge base, loaded back into the agent's context before the next run.
- **Turns commits into a work order.** `plan` maps the last N hours of product commits to
  the flows that cover them, and names the changed surfaces nothing covers.
- **Reports with evidence** — every screenshot, grouped by flow, with a batch-level
  verdict, because "40 failed" is a lie when it is one dead server.
- **Proposes, never pushes.** Unattended changes land on a branch and open a PR.

## What it is not

It contains **no knowledge of any app**. The engine ships zero screen maps, zero
selectors, zero product strings. All of that lives in the target repo:

```
your-test-repo/
  autopilot.json          # devices, app ids, manifests, build + seed commands, coverage globs
  knowledge/
    LESSONS.md            # durable traps learned from real runs
    BUGS.md               # product bugs found by tests — reported, never fixed
    TRIAGE.json           # project-specific failure patterns
  test-ios/ test-android/ # your Maestro flows and manifests
```

That split is the point. The engine is publishable; your product map stays private.

## Quick start

```bash
git clone https://github.com/huajunchen/maestro-autopilot ~/Code/maestro-autopilot
cp ~/Code/maestro-autopilot/config/autopilot.example.json /path/to/your-test-repo/autopilot.json
# edit it, then:
cd /path/to/your-test-repo
python3 ~/Code/maestro-autopilot/scripts/autopilot.py preflight --platform ios
python3 ~/Code/maestro-autopilot/scripts/autopilot.py run --platform ios
```

Point your agent at [`SKILL.md`](SKILL.md) — it is the operating contract the CLI enforces.

## Commands

| | |
|---|---|
| `preflight --platform ios [--check]` | prepare / re-verify the runtime |
| `run --platform ios [--only ID] [--family F]` | batch run with per-flow timeout + live PROGRESS.md |
| `plan --since-hours 24` | commits → work order (covered / uncovered / unmapped) |
| `context` | the lessons an agent should read before acting |
| `lesson` / `bug` | append to the knowledge base |
| `report [--run-root PATH]` | render `report.html` with all evidence |
| `pr --title ... [--push]` | branch, commit, open a PR |

## Scheduling

Not included, on purpose. Wire the loop to whatever scheduler you already trust —
launchd, cron, CI. Two requirements an unattended run has that an interactive one does
not: **stdin must be closed** and there must be a **wall-clock timeout**. A CLI that
quietly blocks on stdin will otherwise sit there for hours looking busy.

A sensible shape: nightly, run only what last night's commits touched; every other
week, run everything.

## Requirements

macOS, Python 3.10+ (stdlib only), the Maestro CLI, a JDK (auto-resolved from Homebrew),
Xcode command line tools for iOS, `adb` for Android, `gh` for PR creation.

## Docs

- [Configuration](docs/CONFIGURATION.md)
- [The knowledge base](docs/KNOWLEDGE-BASE.md)
- [Design notes](docs/DESIGN.md) — why each guard exists

MIT.
