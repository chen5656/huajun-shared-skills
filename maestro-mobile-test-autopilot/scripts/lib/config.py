"""Load and validate the target repo's autopilot config.

Everything product-specific lives in this file inside the *target* repo.
The engine never hardcodes an app id, a device, or a path.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

CONFIG_NAMES = ("autopilot.json", ".autopilot.json", "config/autopilot.json")


class ConfigError(RuntimeError):
    pass


def find_config(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for d in [start, *start.parents]:
        for name in CONFIG_NAMES:
            p = d / name
            if p.is_file():
                return p
    raise ConfigError(
        "No autopilot.json found. Copy config/autopilot.example.json into the "
        "test repo root and fill it in (see docs/CONFIGURATION.md)."
    )


class Config:
    def __init__(self, path: Path):
        self.path = path
        # config/autopilot.json means the repo root is one level up
        self.root = path.parent.parent if path.parent.name == "config" else path.parent
        try:
            self.data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise ConfigError(f"{path} is not valid JSON: {e}") from e
        self._validate()

    # ---- accessors -------------------------------------------------
    def get(self, dotted: str, default=None):
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def platform(self, name: str) -> dict:
        p = self.get(f"platforms.{name}")
        if not p:
            raise ConfigError(f"Platform '{name}' is not declared in {self.path}")
        if not p.get("enabled", True):
            raise ConfigError(f"Platform '{name}' is disabled in {self.path}")
        return p

    def enabled_platforms(self) -> list[str]:
        return [k for k, v in (self.get("platforms") or {}).items() if v.get("enabled", True)]

    def resolve(self, relative: str | None) -> Path | None:
        if not relative:
            return None
        p = Path(relative)
        return p if p.is_absolute() else (self.root / p).resolve()

    @property
    def artifacts(self) -> Path:
        d = self.resolve(self.get("artifacts_dir", "artifacts"))
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def knowledge(self) -> Path:
        d = self.resolve(self.get("knowledge_dir", "knowledge"))
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ---- validation ------------------------------------------------
    def _validate(self) -> None:
        missing = [k for k in ("project_id", "platforms") if k not in self.data]
        if missing:
            raise ConfigError(f"{self.path} is missing required keys: {', '.join(missing)}")
        for name, p in self.data["platforms"].items():
            if not p.get("enabled", True):
                continue
            for k in ("app_id", "manifest"):
                if k not in p:
                    raise ConfigError(f"platforms.{name} is missing '{k}'")


def java_env(cfg: Config) -> dict:
    """Resolve a usable JDK without asking the user to install one.

    Probes the configured Homebrew formulae in order; falls back to whatever
    `java` is already on PATH. Only reports 'no JDK' when both fail.
    """
    env = dict(os.environ)
    for formula in cfg.get("java_home_candidates", ["openjdk@17", "openjdk"]):
        try:
            prefix = subprocess.run(
                ["brew", "--prefix", formula], capture_output=True, text=True, timeout=20
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if not prefix:
            continue
        home = Path(prefix) / "libexec" / "openjdk.jdk" / "Contents" / "Home"
        if (home / "bin" / "java").is_file():
            env["JAVA_HOME"] = str(home)
            env["PATH"] = f"{home / 'bin'}{os.pathsep}{env['PATH']}"
            return env
    if shutil.which("java"):
        return env
    raise ConfigError(
        "No usable JDK found. Install one (e.g. `brew install openjdk@17`) or add "
        "its formula name to java_home_candidates."
    )
