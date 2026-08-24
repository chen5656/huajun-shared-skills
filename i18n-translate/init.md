# Init: first-time setup

Only read this file when `<SKILL_DIR>/.init-config.json` does not exist yet.

Ask the user:

- Agent CLI — which non-interactive CLI to launch the worker with, and any special
  flags it needs. Known options:
  - `codex exec` (OpenAI Codex CLI)
  - `claude -p` (Claude Code CLI, print mode)
  - `agy -p` (Gemini's non-interactive CLI; also supports `--mode accept-edits`,
    `--print-timeout`, `--add-dir`. It commonly also needs
    `--dangerously-skip-permissions` to run unattended — ask the user whether to
    include it and store it in `extra_flags` if so. 
- Model — which model to run the worker on, and any special requirements (it should
  be a cheap/fast model; that's the point of routing this to a worker). If the CLI
  has a `models` (or equivalent) listing subcommand, run it and confirm the choice
  is still valid rather than trusting a model name from memory.
- Path — the absolute path to this skill directory (`TRANSLATE_SKILL_DIR`).

Save the answers to `<SKILL_DIR>/.init-config.json`:

```json
{
  "agent_cli": "codex exec",
  "model": "gpt-5-mini",
  "skill_dir": "/absolute/path/to/i18n-translate",
  "extra_flags": ""
}
```

`extra_flags` is optional — a string of extra CLI flags inserted into the launch
command as-is (e.g. `"--dangerously-skip-permissions"` for `agy`). Omit it or leave
it empty if the CLI needs nothing extra.

This file is machine-local, not project config, so it is gitignored (see this
folder's `.gitignore`). Re-run init (delete the file, or just ask again) if the
setup ever needs to change.

Once saved, go to "Launching the worker" in `SKILL.md`.
