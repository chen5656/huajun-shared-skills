---
name: maestro-autopilot
description: Use when running, repairing, extending, or scheduling Maestro black-box mobile tests for any app. Pins the device, runs a mandatory preflight, triages failures into environment/harness/test/app-bug, repairs only within a declared boundary, records durable lessons, and reports with evidence. Product-specific facts live in the target repo's autopilot.json and knowledge/, never in this skill.
---

# Maestro Autopilot

Agent-agnostic. Any coding agent may use this skill. It is the operating contract;
`scripts/autopilot.py` is the enforcement.

## 0. What this skill is, and what it deliberately is not

It is a way to run mobile black-box tests **unattended** and still trust the result.
Nearly everything here exists because a specific unattended run lied — reported green
while driving the wrong phone, or reported forty regressions that were one dead dev
server.

It is **not** a screen map of any app. The engine knows nothing about your product.
Everything product-specific lives in two places in the *target* repo:

| Product knowledge | Lives in |
|---|---|
| devices, app ids, manifests, build commands, seeding, coverage globs | `autopilot.json` |
| traps, platform behaviours, selector rules learned from real runs | `knowledge/LESSONS.md` |
| product bugs the tests found | `knowledge/BUGS.md` |
| project-specific failure patterns | `knowledge/TRIAGE.json` |

If you learn something during a run, it goes in the knowledge base. If you learn
something true of *Maestro or the platform itself*, it goes in this skill.

## 1. The boundary — read before touching anything

**You may edit:** Maestro YAML, the manifests, `autopilot.json`, the knowledge base,
this skill.

**You may edit in the app source — only this:** non-visible accessibility and test
metadata (`accessibilityLabel`, `accessibilityHint`, `accessibilityRole`,
`accessibilityState`, `testID`, or the platform equivalents).

Prefer fixing an ambiguous control at the source over writing a cleverer selector.
A numeric input whose label duplicates nearby visible text should become
`"L1 to L2 voltage input, volts"` — then a plain-string selector works *and* a screen
reader user gets real context. Test maintainability and accessibility are the same
work here; that is not a coincidence, it is the reason this is the one carve-out.

**You may not** change behaviour, layout, styling, visible text, calculations,
navigation, or state management.

**Bugs: report, never fix.** When a test exposes a real product bug, write it to
`knowledge/BUGS.md` (`autopilot.py bug`) with symptom, suspected cause, file, and
reproduction — then stop. The owner is the auditor. An agent that silently fixes the
product overnight has removed the only checkpoint in the loop.

**All unattended changes land on a branch and open a PR.** Never commit to the
default branch from a scheduled run.

## 2. Load context before acting

```sh
python3 scripts/autopilot.py context      # lessons learned by previous runs
```

Read it. A cause diagnosed once must never be re-diagnosed from scratch — that is the
whole difference between a loop that improves and a loop that repeats.

## 3. Preflight is mandatory and comes first

```sh
python3 scripts/autopilot.py preflight --platform ios
```

Preflight is the **only** step allowed to prepare the runtime: boot/pin the device,
start the dev server, install and verify the build, run a tiny smoke flow, and write a
readiness record. Every later command re-verifies that record and fails in seconds if
it no longer holds.

Never run the requested workflow first and preflight afterwards. Never skip it because
the simulator "looked fine". **If preflight fails, stop and fix the environment** —
do not start the batch.

What it protects against, all of which look identical to selector regressions:

- **No device pinned.** Maestro grabs whatever is attached. A connected Android phone
  silently drives an iOS suite: every `when: visible:` branch skips and the flow dies
  at the first hard assert. Tell: the failure screenshot has the wrong aspect ratio.
- **Wrong build variant.** A debug build installed over a release build fails every
  flow identically. Preflight reads the installed package back and aborts on mismatch.
- **App never launched.** Preflight polls for a live process in the foreground and
  screenshots the failure.
- **Dev server missing, or started with CI-style env.** CI flags suppress dev-server
  registration; the app finds no server and *every* flow fails in setup. Looks like a
  mass regression, is purely environmental.
- **A hung driver from an interrupted run.** Preflight kills stray processes first.
- **A stale readiness record.** It expires after 12 hours; a rebooted machine cannot
  be vouched for by yesterday's run.

## 4. Running

```sh
python3 scripts/autopilot.py run --platform ios                  # active flows
python3 scripts/autopilot.py run --platform ios --only <id>
python3 scripts/autopilot.py plan --since-hours 24               # commits -> work order
```

Rules the runner enforces so you do not have to remember them: an explicit run root
(never the cwd, or named captures litter the repo), debug output always on (without it
a failure leaves no screenshot), a per-flow timeout (one hung process must not block
the batch forever), and a `PROGRESS.md` rewritten before every flow with a stable
`latest-<platform>` symlink.

**One Maestro invocation at a time.** Never run `hierarchy` and `test` concurrently —
shared daemon, corrupted state.

## 5. Failure triage — four classes, in this order

Inspect in order: **stdout/stderr → failure screenshots → debug output → hierarchy dump.**

| Class | Meaning | Action |
|---|---|---|
| `environment` | The runtime lied: wrong device, dead server, wrong build, exhausted quota. | Fix the machine. Change no test. |
| `harness` | Maestro/driver level: hung CLI, deadline, syntax. | Kill and retry once; fix the YAML if syntax. |
| `test` | Stale selector, missing modal gate, timing. | Repair within the boundary (§1). |
| `app_bug` | Flow sound, environment stable, product genuinely wrong. | Report and stop (§1). |
| `unknown` | Not classifiable from the evidence at hand. | Say so. Never guess a class. |

`autopilot.py` assigns a first-pass class from the log and marks it **unconfident**
when the log alone cannot distinguish causes. That flag matters: some of the most
expensive failure modes — a quota-exhaustion dialog, a permission sheet, an error
overlay — produce a log line **indistinguishable from an ordinary assertion timeout**.
Only the screenshot separates them. When the class is unconfident, look at the image
before claiming a cause.

**Read the batch, not the flow.** Mass failure is almost never mass regression. If
every flow failed with an environment/harness cause, that is *one incident*, and the
report must say so instead of headlining "40 failed".

**At most two repair loops per request.** If the environment is still unstable after
two, report `environment unresolved` — that is an honest outcome, not a failure to
finish. Classify something as an app bug only when the flow is sound, the environment
is stable, and the visible user behaviour genuinely fails the asserted outcome.

## 6. Selector rules

Priority: **plain string (accessibility label) → `text:` → `id:` (testID) → `point:`**.

- Matching is **full-string regex**, not substring. `"Type your question"` does not
  match `"Type your question..."`. Escape literal dots; a bare `.` is a wildcard.
- Match the string **as written in source**, not as it appears on screen — a native
  text transform can make the two disagree.
- Never `point:` into a text input. Tap its placeholder, or add one in source.
- When a match fails and the text is plainly on screen, **dump the hierarchy instead
  of guessing.** Guessing a selector produces a flow that passes for the wrong reason.

## 7. Durable platform behaviours

These stay true across redesigns. Fix a bullet in place when it stops being true;
never append a dated change log.

- **An explicit accessibility label on a container collapses its subtree on iOS.**
  Child text inside a labelled pressable is absent from the tree, so asserting on
  visible text can never match. Put a testID on the inner text node.
- **iOS concatenates a text input's label and placeholder** into `"<label> <placeholder>"`;
  neither alone matches.
- **RN reports below-the-fold rows as on-screen.** In clipped scroll views and bottom
  sheets, `assertVisible` and `scrollUntilVisible` pass *without scrolling*, and the
  following tap lands on whatever is behind. Swipe explicitly, then tap.
- **The keyboard physically covers elements that remain in the tree**, so taps are
  swallowed silently. Dismiss deliberately; a blind swipe often does nothing at all
  because the touch starts inside the keyboard's own bounds.
- **Native alerts leave the app's tree reachable behind them** — a tap can hit an
  identically-named node behind the modal. Select on text unique to the alert.
- **Dev-mode error overlays intercept the screen.** Guard with an optional dismissal
  before asserting.
- **A flow-level `env:` default beats `-e` on the command line.** A default silently
  masks the injected value, so a run with a deliberately wrong value still passes —
  the worst kind of green. Never give an injected variable a default.
- **A `when: visible:` gate whose alternatives are all dead never fires**, and the
  flow proceeds as if the screen were in another state. That reads as a stall, not a
  selector error. After any redesign, grep the removed strings across all flows.
- **State persists across flows** unless a flow clears it. Anything that changes a
  global preference must restore it at the end.
- **Manifest order can encode data setup.** Preserve relative order when editing.
- **Prefer freshly seeded data over one long-lived shared fixture.** Repeatedly
  mutating one record accumulates sync drift that surfaces as unrelated failures.

## 8. Knowing what NOT to automate

Some surfaces cannot be driven reliably, and the correct output is a written
limitation, not a flaky test.

The canonical example: a field the framework reports as on-screen while the keyboard
physically covers it. No selector fixes that. **Record it as a harness limitation with
the reason, and cover what you can.** A documented gap is engineering judgment; a
flaky test that fails one night in three is technical debt that trains everyone to
ignore the suite.

Write gaps into `knowledge/LESSONS.md` with scope `platform` or `product`, and list
them in the run report under "known coverage gaps".

## 9. The self-improving loop

Each run closes this cycle:

1. **context** — load `knowledge/LESSONS.md` before acting.
2. **plan** — `autopilot.py plan` turns the last N hours of product commits into a
   work order: changed surfaces that existing flows already cover, changed surfaces
   with no coverage, and files the coverage map does not know about. Propose flows for
   the uncovered ones; **never invent a flow silently** — a test nobody asked for that
   asserts the wrong thing is worse than a gap.
3. **preflight → run** (§3, §4).
4. **triage → repair**, within the boundary, at most two loops (§5).
5. **learn** — every diagnosis that took real work becomes a lesson:
   ```sh
   python3 scripts/autopilot.py lesson --id kb-014 --scope platform \
     --title "..." --symptom "..." --cause "..." --rule "..."
   ```
   Only durable facts. Duplicate ids are refused, because a knowledge base full of
   near-duplicates stops being read, which is the same as not having one.
6. **report** — `report.html` + `RUN-SUMMARY.md` (§10).
7. **propose** — `autopilot.py pr --title ... --push`. Branch and PR, never the
   default branch.

Scheduling is deliberately **not** part of this skill. Wire steps 1–7 to whatever
scheduler you already trust (launchd, cron, CI). Two things the schedule must respect:
an unattended run needs stdin closed and a wall-clock timeout, and a nightly run
should touch only what changed — full regression belongs on its own, rarer cadence.

## 10. Reporting — evidence or it did not happen

Write `RUN-SUMMARY.md` in the run root; `autopilot.py report` embeds it in
`report.html` above the per-flow evidence. A run with no narrative is not reported.

Structure it for someone who was not there:

1. **Environment / preflight** — what had to be fixed before tests could run. Say so
   explicitly if nothing was.
2. **What broke and why** — grouped by root cause, not flow by flow.
3. **What was fixed** — one line each. Call out **app-source metadata edits
   separately** so the auditor sees them without diffing.
4. **Failures that are NOT test bugs** — its own labelled section, with the evidence
   named per flow. If the headline count is mostly these, annotate it inline.
5. **Known open issues** — anything still flaky or worked around. Do not present a
   flaky flow as fixed.
6. **Bugs found** — reported, never fixed.

The report embeds **every** screenshot, grouped by flow. No cherry-picking a
representative image.

**Never report "everything is fine" without evidence gathered in this same turn.**
Not from the assumption that a process you started is still healthy. Minimum: has
`PROGRESS.md` moved; is the process alive; does a live screengrab show the app (not a
launcher, crash dialog, or lock screen). "It is running normally" is a claim about the
last minute, not the last hour. **If you have not looked, say you have not looked.**

**Check-in cadence scales with how much of the batch is left.** Read
`PROGRESS.md`'s `Flows: X/Y finished` line: while more than 5 flows remain, check in
every ~30 minutes; once 5 or fewer remain, tighten to every ~10 minutes — the tail is
where a hang is both more likely to matter (closest to done) and cheapest to catch
early. Whatever the cadence, if the counter has not moved since the last check, say so
immediately and start triage — do not wait to be asked.

## 11. Real-device etiquette

When the rig is someone's actual phone: batch offline scenarios contiguously and
**always restore connectivity, including on failure paths**. Re-enabling wifi and data
does not clear the system airplane-mode flag — clear that first, explicitly. Never
bypass a lock screen. Treat a serial mismatch as a stop condition, not an invitation
to use the other device.

## Defaults

- Read every device, id, and command from config. Never hardcode one in conversation.
- Prefer accessibility labels; coordinates only when no accessible text exists.
- If you find a problem with this skill during a run, fix the skill. At the end of the
  task, state explicitly every change you made to the skill, the config, the knowledge
  base, and the app source. The user is your auditor.
