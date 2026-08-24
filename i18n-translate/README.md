# i18n-translate

Bulk [Lingui](https://lingui.dev) catalog translation, routed to a cheap model on purpose: extract
missing entries into batched JSON sessions, translate, audit for UI overflow, apply, compile, verify.

**Output:** updated `.po` files, compiled catalogs, 0 missing entries per locale.

---

## What problem it solves

Shipping a release with three locales means several hundred `msgstr` entries that need
translating, checking for placeholder damage, and checking that the Spanish version of a
button still fits on the button. It is real work with real failure modes — and almost
none of it needs frontier-model reasoning.

## The actual design decision: pay less for this

I run the translation worker on a cheap Gemini plan (`gemini-3.5-flash-low` in my setup),
launched as a separate non-interactive process by whichever agent is orchestrating the
release. That plan is inexpensive and the model is limited in what it can do well — but
this task is bounded, mechanical, and heavily validated downstream, so the fit is close to
ideal. Bulk translation is exactly the kind of work you should not be paying frontier
prices for.

The interesting part is what it takes to make that stick.

## Why the split into SKILL.md / worker.md exists

Writing "use the cheap model for translation" in a deploy checklist does not work. The
orchestrating agent is capable, the task is right there, and being helpful is what it
does — so it translates the strings itself and the saving quietly evaporates. Nobody
notices, because the output is fine.

My first version enforced this with a role check: one file, with a "stop rule" telling
an agent that wasn't launched as the worker not to touch extraction, translation, or
compile. That worked, but it meant the full translation runbook — every instruction
meant only for the worker — was loaded into the orchestrator's context on every single
invocation, just to be told "not you."

The current version enforces it structurally instead. [`SKILL.md`](SKILL.md) is what
the orchestrating agent reads, and it only contains orchestration: check whether
translation is needed, launch the worker CLI, verify the result, retry up to 3 times,
then hand off to a human. The actual translation runbook — sessions, audit, apply,
compile — lives in [`worker.md`](worker.md), which the orchestrator is told never to
open. Only the worker's launch prompt points at it. The orchestrator physically cannot
drift into doing the translation itself, because those instructions never enter its
context in the first place — and it costs nothing on the runs where a human never even
touches the deploy checklist.

The launch command names no specific model or CLI, so the same files work whether your
worker is Gemini, a local model, or the same agent you started from — see Init below.

## Init: one-time, machine-local setup

The first time the skill runs in a given checkout, it doesn't yet know which agent CLI
and model to launch as the worker. Rather than bake that into `SKILL.md` — which would
mean paying to load setup instructions on every run, forever, even after setup is done
— that detail lives in a third file, [`init.md`](init.md), read exactly once.

On first use, `SKILL.md` checks for `.init-config.json` in the skill folder. If it's
missing, it reads `init.md`, which asks three questions (agent CLI, model, and the
skill's own absolute path) and writes the answers to `.init-config.json`. Every run
after that skips straight past the check — the config is machine-local, so it's
gitignored, and it never needs to be re-answered unless you delete it.

## The context tax nobody notices

There is a second, less obvious waste, and it is the one that actually costs the most.
Translation almost never comes first. It comes at the end of a long session — the agent
just finished a feature, debugged it, ran the tests, and is now sitting on a very large
context window. Then it does the natural thing: "while I'm here, let me update the
catalogs too."

Now every single one of those ~50-entry batches gets billed against that entire
accumulated context. The feature diff, the test output, the files read three hours ago —
all of it rides along on every translation turn, for work that needs to know nothing
except the source string and the target locale. The per-token price never changed; the
number of tokens per unit of work quietly went up by an order of magnitude.

A separate worker process fixes this by construction. It starts cold, sees only the
catalogs and the skill, and exits when it's done. That is why the skill insists on
launching a *new* process rather than "switching to a cheaper model" mid-session —
changing the model does nothing about the context you are dragging behind you.

## Why a Python helper instead of "translate this .po file"

[`translate_helper.py`](translate_helper.py) does the parts a language model should not be trusted
with:

- **Batching.** Missing entries are extracted into `session_N.json` files of ~50 entries.
  A model handed a 700-entry catalog degrades badly toward the end; 50 at a time does not.
- **Structural safety.** Only `msgstr` is writable. Placeholders (`{0}`, `{count}`),
  plural keys, escapes, and leading/trailing whitespace are verified against the source
  before anything is written back, so a plausible-looking translation cannot silently
  break interpolation at runtime.
- **UI overflow audit.** Flags translations that grew past what tight surfaces — buttons,
  tabs, badges, fixed-height cards — can display. German and French routinely run 30%
  longer than English, and this is otherwise found by a user, in production, on a phone.
- **Verification that means something.** The run is only successful if `lingui:compile`
  passes *and* every locale reports 0 missing. A subset is a failure, not partial credit.

The division is the point: the cheap model does judgment about language, the deterministic
script does everything where being wrong is expensive.

## The retry loop

Verification isn't a one-shot check. After the worker exits, the orchestrator re-runs
`lingui:extract` and only accepts 0 missing entries across every locale as success. If
entries remain, it launches the worker again — up to 3 attempts total — since the
worker's own extract step naturally picks up only what's still missing each time. If
attempt 3 still leaves entries missing, the skill stops and reports the remainder to a
human instead of silently retrying forever or claiming a partial result as done.

## Requirements

- A project using Lingui with `lingui:extract` / `lingui:compile` scripts and a
  `src/locales` catalog directory.
- Any agent CLI that can run a single prompt non-interactively and write files in the
  repo — named once, at init, not hardcoded in the skill.
- Python 3 for the helper. No third-party dependencies.

## Install

```bash
cp -R i18n-translate ~/.claude/skills/
```

Copy `SKILL.md`, `init.md`, `worker.md`, and `translate_helper.py` together — the
workflow reads and calls all of them. The first run in a new checkout will ask you for
your agent CLI, model, and this skill's path (see Init above); nothing needs to be
hand-edited in the files themselves.
