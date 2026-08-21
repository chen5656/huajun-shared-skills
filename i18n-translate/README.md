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

## Why the stop rule exists

Writing "use the cheap model for translation" in a deploy checklist does not work. The
orchestrating agent is capable, the task is right there, and being helpful is what it
does — so it translates the strings itself and the saving quietly evaporates. Nobody
notices, because the output is fine.

So the routing is enforced in the skill rather than requested: an agent reading `SKILL.md`
that was **not** launched as the worker is told, in the first section, that it may not run
extraction, the helpers, the translation, the audit, the apply, or the compile. Its only
move is to launch the worker and get on with the rest of the release.

It is stated as a role check rather than a model name, so the same file works whether your
worker is Gemini, a local model, or the same agent you started from. Naming a specific
model there was my first version and it was wrong — it broke the moment the setup changed.

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

## Requirements

- A project using Lingui with `lingui:extract` / `lingui:compile` scripts and a
  `src/locales` catalog directory.
- Any agent CLI that can run a single prompt non-interactively and write files in the
  repo. The launch snippet in the skill is written generically — substitute your own.
- Python 3 for the helper. No third-party dependencies.

## Install

```bash
cp -R i18n-translate ~/.claude/skills/
```

Copy `translate_helper.py` along with `SKILL.md` — the workflow calls it directly. Then adapt the
"Launching the worker" snippet in [`SKILL.md`](SKILL.md) to your own agent CLI and model.
