# Worker workflow

You are the translation worker. Complete every step yourself; do not delegate and do
not launch another agent process.

The helper script is `<SKILL_DIR>/translate_helper.py`. Store session files at
`.translation/<project>/<locale>/session_N.json` in the target repo.

## 1. Inspect and extract

Confirm that the repo uses Lingui and locate `lingui.config.ts`, `src/locales`, and the package scripts. Then run:

```bash
npm run lingui:extract
```

Treat `en` as the source locale unless the config says otherwise. Preserve PO headers, comments, references, and `msgid` values.

## 2. Create JSON sessions with Python

Derive a short project name from the repo directory, then run:

```bash
python3 <SKILL_DIR>/translate_helper.py extract \
  --po-dir src/locales \
  --project <PROJECT_NAME> \
  --sessions-dir .translation \
  --session-size 50
```

If the helper reports zero missing entries, skip to compile and final checks. Otherwise, process every locale and every generated session.

## 3. Translate every session

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

## 4. Audit text length and UI risk

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

## 5. Apply with Python

Run:

```bash
python3 <SKILL_DIR>/translate_helper.py apply \
  --po-dir src/locales \
  --project <PROJECT_NAME> \
  --sessions-dir .translation
```

Check the helper summary. Treat missing sessions, empty translations, parse errors, or unmatched entries as failures and fix them before continuing.

## 6. Compile and check catalogs

Run:

```bash
npm run lingui:compile
npm run lingui:extract
```

Confirm that compile succeeds. Capture Lingui's final catalog statistics, including each locale's total and missing counts. Inspect the final diff for accidental changes outside translation catalogs, compiled catalogs, and `.translation` session files.

## 7. Return the result

Return a short report with:

- locales and translated entry counts;
- final missing counts;
- audit or validation fixes;
- compile status;
- changed files;
- any blocker with the failed command and error.

Do not claim success if compile fails or expected translated locales still have missing entries.
