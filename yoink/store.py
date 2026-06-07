"""Store — paths, constants, and manifest read/write."""

import json
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

YOINK_DIR = ".yoink"
MANIFEST_FILE = "manifest.json"
REQUESTS_DIR = "requests"
DEFAULT_ENVS = ["dev", "staging", "production"]
RECOVERY_KEY_COUNT = 2


def vault_dir() -> Path:
    return Path.cwd() / YOINK_DIR


def manifest_path() -> Path:
    return vault_dir() / MANIFEST_FILE


def requests_dir() -> Path:
    return vault_dir() / REQUESTS_DIR


def global_dir() -> Path:
    return Path.home() / ".yoink"


def find_enc_files(env: str | None = None) -> list[Path]:
    vdir = vault_dir()
    if not vdir.exists():
        return []
    files = sorted(vdir.rglob("*.enc"))
    if env:
        files = [f for f in files if f.relative_to(vdir).parts[0] == env]
    return files


def get_git_username() -> str | None:
    """Detect username from gh CLI or git config."""
    try:
        r = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
        for line in (r.stdout + r.stderr).splitlines():
            if "Logged in to" in line and " as " in line:
                return line.split(" as ")[-1].split()[0].strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        r = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

class Manifest:
    """Thin wrapper around manifest.json."""

    def __init__(self, data: dict | None = None):
        self.data = data or {
            "version": 1,
            "environments": {},   # {env: {recipients: [...]}}
            "identities": {},     # {name: {public_key, recovery_key?}}
            "recovery": [],       # [public_key, ...]
        }

    # --- persistence ---

    def exists(self) -> bool:
        return manifest_path().exists()

    def load(self) -> "Manifest":
        if not self.exists():
            raise FileNotFoundError("No vault found. Run any yoink command inside a git repo to initialise.")
        self.data = json.loads(manifest_path().read_text())
        return self

    def save(self) -> None:
        manifest_path().write_text(json.dumps(self.data, indent=2) + "\n")

    # --- environments ---

    def get_envs(self) -> dict:
        return self.data.get("environments", {})

    def get_recipients(self, env: str) -> list[str]:
        return self.data.get("environments", {}).get(env, {}).get("recipients", [])

    def set_recipients(self, env: str, recipients: list[str]) -> None:
        self.data.setdefault("environments", {})[env] = {"recipients": recipients}

    def add_env(self, env: str, recipients: list[str]) -> None:
        self.set_recipients(env, recipients)

    def remove_env(self, env: str) -> None:
        self.data.get("environments", {}).pop(env, None)

    # --- identities ---

    def get_identities(self) -> dict:
        return self.data.get("identities", {})

    def add_identity(self, name: str, public_key: str, recovery_key: str | None = None) -> None:
        entry = {"public_key": public_key}
        if recovery_key:
            entry["recovery_key"] = recovery_key
        self.data.setdefault("identities", {})[name] = entry

    def remove_identity(self, name: str) -> None:
        self.data.get("identities", {}).pop(name, None)

    def has_identity(self, name: str) -> bool:
        return name in self.data.get("identities", {})

    def get_identity_key(self, name: str) -> str | None:
        return self.data.get("identities", {}).get(name, {}).get("public_key")

    # --- recovery ---

    def get_recovery_keys(self) -> list[str]:
        return self.data.get("recovery", [])

    def set_recovery_keys(self, keys: list[str]) -> None:
        self.data["recovery"] = keys
