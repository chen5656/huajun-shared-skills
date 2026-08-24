---
name: i18n-translate
description: Lingui i18n translation runbook. Delegates the actual translation to a non-interactive agent CLI worker and only checks/loops/verifies the result. Covers requests such as "translate" and "update locales".
---
# i18n Translation Skill

Bulk Lingui catalog translation is done by an external agent CLI (configured via
init), not by you. Your job here is orchestration only: check whether translation is
needed, launch the worker, verify its result, and retry a bounded number of times.
Never translate strings yourself and never open `worker.md` — that file is the
worker's prompt, not yours.

## Init: first-time setup

Check whether `<SKILL_DIR>/.init-config.json` exists. If it doesn't, read
`<SKILL_DIR>/init.md` and follow it before continuing. If it does, read it for
`agent_cli`, `model`, `skill_dir`, and optional `extra_flags`.

## Orchestrator workflow

1. **Check.** From the target repo root, run `npm run lingui:extract`. If Lingui
   reports 0 missing entries across all locales, stop — there is nothing to
   translate.
2. **Call the worker (attempt 1 of 3).** Run, in the background:

   ```bash
   $AGENT_CLI --model "$MODEL" --mode accept-edits --add-dir "$SKILL_DIR" --print-timeout 30m $EXTRA_FLAGS \
     --print "Act as the translation worker for this repo. Read $SKILL_DIR/worker.md in full, then follow it to completion. Do not launch another worker."
   ```

   `$EXTRA_FLAGS` is the `extra_flags` value from `.init-config.json` (empty if
   unset) — e.g. for `agy` this is typically `--dangerously-skip-permissions`.

   Tell the user it's running and wait for it to exit rather than polling. A full
   run can take 20-30 minutes.
3. **Verify.** Run `npm run lingui:extract` again. If every locale now shows 0
   missing entries, report success with the counts and changed files — done.
4. **Retry or stop.** If entries are still missing:
   - If fewer than 3 worker attempts have run, go back to step 2. The worker's own
     extract step will pick up only what's still missing.
   - If 3 attempts have run and entries are still missing, stop. Report which
     locales/counts remain, the last worker output, and wait for a human — do not
     attempt the translation yourself and do not start a 4th attempt.

Rules:

- Run **one** worker at a time. Never run two workers concurrently, and never
  translate a string yourself under any circumstance — that defeats the point of
  routing this to a cheap model.
- Do not run `lingui:compile` or the Python helpers yourself; those belong to the
  worker.
