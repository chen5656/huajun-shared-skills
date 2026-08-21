---
name: i18n-translate
description: Lingui i18n translation runbook, from extraction through compile and final catalog checks. Covers requests such as "translate", "update locales", "翻译", and "更新语言". Contains both the command that launches the translation worker and the worker workflow itself; an agent that was not launched as the worker only launches it.
---
# i18n Translation Skill

A runbook for bulk Lingui catalog translation. It contains two parts that must not be mixed: the command an orchestrating agent uses to *launch* the translation worker, and the workflow the worker itself follows.

## Stop rule: only act when you were launched as the worker

This runbook has one role. Unless the prompt that started your session explicitly
names you as the translation worker, **you are not the worker**. Do not run
extraction, the Python helpers, translation, audit, apply, compile, or the catalog
checks, and do not translate any string.

The orchestrating agent's job is to *launch* the worker (see "Launching the worker"
below) and then continue with the rest of the task. This separation is deliberate:
the worker step is bulk, bounded, mechanical work, and it is routed to a cheap model
on purpose. An orchestrator that helpfully does the translation itself silently
throws that saving away — hence a hard rule rather than a preference.

If the user asked only for translations and no deploy runbook is in play, say that
this work runs as a separate worker process and let the user decide whether to start
it.

## Launching the worker

Run one worker for the whole job, from the target repo root, in the background.
Adapt this to whatever non-interactive agent CLI you use — the only requirements are
that it can run a single prompt to completion, write files in the repo, and reach the
skill directory:

```bash
TRANSLATE_SKILL_DIR="<path-to-this-skill>" <your-agent-cli> \
  --model <cheap-model> \
  --mode accept-edits \
  --add-dir "<path-to-this-skill>" \
  --print-timeout 30m \
  --print "Act as the translation worker for this repo. First read <path-to-this-skill>/SKILL.md in full. Follow its Worker workflow from start to finish. Do not launch another worker process. Run extraction, use the bundled Python helper, translate every session yourself, audit, apply, compile, and run the final catalog check. Fix translation validation failures before applying. Do not stop after planning. Return a short summary with counts, checks, changed files, and any blocker."
```

Rules for this step:

- Run **one** worker for the whole job. Do not split locales or sessions across
  several workers, and do not start a second worker while one is running.
- The orchestrator does not translate any string and does not run `lingui:extract`,
  `lingui:compile`, or the Python helpers itself.
- A full run can take 20-30 minutes. Start it in the background, tell the user it is
  running, and wait for it to exit rather than polling.
- On success, relay its counts, checks, and changed files. Every locale must finish
  with 0 missing entries; a subset is a failure.

## Worker workflow

Follow this section only when the launch prompt names you as the translation worker. Do not delegate and do not launch another agent process; complete every step yourself.

The helper script is `<SKILL_DIR>/translate_helper.py`. Store session files at `.translation/<project>/<locale>/session_N.json` in the target repo.

### 1. Inspect and extract

Confirm that the repo uses Lingui and locate `lingui.config.ts`, `src/locales`, and the package scripts. Then run:

```bash
npm run lingui:extract
```

Treat `en` as the source locale unless the config says otherwise. Preserve PO headers, comments, references, and `msgid` values.

### 2. Create JSON sessions with Python

Derive a short project name from the repo directory, then run:

```bash
python3 <SKILL_DIR>/translate_helper.py extract \
  --po-dir src/locales \
  --project <PROJECT_NAME> \
  --sessions-dir .translation \
  --session-size 50
```

If the helper reports zero missing entries, skip to compile and final checks. Otherwise, process every locale and every generated session.

### 3. Translate every session

Read each session JSON file and fill every empty `msgstr` yourself. Do not call another model or CLI.

For each entry:

- Translate into the locale named in the JSON file.
- Change only `msgstr`.
- Use the source comments as UI context.
- Use short, natural app text with the right tone.
- Preserve leading and trailing newlines, placeholders such as `{0}` and `{count}`, markup, escapes, and plural keys.
- Preserve JSON keys and entry order.

Process one session at a time. Save valid UTF-8 JSON after each session.

Before moving on, parse every session with Python and confirm:

- every `msgstr` is non-empty;
- placeholder sets match the source;
- plural objects keep the required keys;
- no field other than `msgstr` changed.

Fix all failures yourself before applying the sessions.

### 4. Audit text length and UI risk

Run:

```bash
python3 <SKILL_DIR>/translate_helper.py audit \
  --project <PROJECT_NAME> \
  --sessions-dir .translation \
  --locale es \
  --locale fr \
  --locale it
```

Review flagged button labels, tabs, headers, badges, fixed-height cards, and other tight UI text through the source references. Shorten a translation when that keeps the meaning and avoids likely clipping. Do not make unrelated UI changes.

### 5. Apply with Python

Run:

```bash
python3 <SKILL_DIR>/translate_helper.py apply \
  --po-dir src/locales \
  --project <PROJECT_NAME> \
  --sessions-dir .translation
```

Check the helper summary. Treat missing sessions, empty translations, parse errors, or unmatched entries as failures and fix them before continuing.

### 6. Compile and check catalogs

Run:

```bash
npm run lingui:compile
npm run lingui:extract
```

Confirm that compile succeeds. Capture Lingui's final catalog statistics, including each locale's total and missing counts. Inspect the final diff for accidental changes outside translation catalogs, compiled catalogs, and `.translation` session files.

### 7. Return the result

Return a short report with:

- locales and translated entry counts;
- final missing counts;
- audit or validation fixes;
- compile status;
- changed files;
- any blocker with the failed command and error.

Do not claim success if compile fails or expected translated locales still have missing entries.
