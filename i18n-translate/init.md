# Init: first-time setup

Only read this file when `<SKILL_DIR>/.init-config.json` does not exist yet.

Ask the user:

- Agent CLI — which non-interactive CLI to launch the worker with, and any special
  flags it needs (e.g. `codex exec`, `claude -p`).
- Model — which model to run the worker on, and any special requirements (it should
  be a cheap/fast model; that's the point of routing this to a worker).
- Path — the absolute path to this skill directory (`TRANSLATE_SKILL_DIR`).

Save the answers to `<SKILL_DIR>/.init-config.json`:

```json
{
  "agent_cli": "codex exec",
  "model": "gpt-5-mini",
  "skill_dir": "/absolute/path/to/i18n-translate"
}
```

This file is machine-local, not project config, so it is gitignored (see this
folder's `.gitignore`). Re-run init (delete the file, or just ask again) if the
setup ever needs to change.

Once saved, go to "Launching the worker" in `SKILL.md`.
