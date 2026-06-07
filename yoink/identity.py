"""Identity — age keypairs stored in ~/.yoink/."""

import subprocess
from pathlib import Path

from .store import global_dir


class Identity:
    def __init__(self, name: str, public_key: str, key_dir: Path | None = None):
        self.name = name
        self.public_key = public_key
        self._key_dir = key_dir or global_dir()

    @property
    def key_file(self) -> Path:
        return self._key_dir / f"{self.name}.key"

    def write(self, secret_key: str) -> None:
        self._key_dir.mkdir(parents=True, exist_ok=True)
        self.key_file.write_text(f"{secret_key}\n")
        self.key_file.chmod(0o600)
        (self._key_dir / f"{self.name}.pub").write_text(f"{self.public_key}\n")

    def __repr__(self) -> str:
        return f"Identity({self.name}, {self.public_key[:20]}...)"


def _keygen(name: str, key_dir: Path | None = None) -> Identity:
    r = subprocess.run(["age-keygen"], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError("age-keygen failed. Install age: brew install age")

    public_key = secret_key = None
    for line in r.stdout.strip().splitlines():
        if "public key:" in line.lower():
            public_key = line.split(":", 1)[1].strip()
        elif line.startswith("AGE-SECRET-KEY-"):
            secret_key = line.strip()

    if not public_key or not secret_key:
        raise RuntimeError("Could not parse age-keygen output")

    identity = Identity(name, public_key, key_dir=key_dir)
    identity.write(secret_key)
    return identity


def create_identity(name: str, key_dir: Path | None = None) -> Identity:
    return _keygen(name, key_dir)


def load_identity(name: str, key_dir: Path | None = None) -> Identity | None:
    kdir = key_dir or global_dir()
    key_file = kdir / f"{name}.key"
    pub_file = kdir / f"{name}.pub"

    if not key_file.exists():
        return None

    if pub_file.exists():
        public_key = pub_file.read_text().strip()
    else:
        # Fallback: scan key file for public key line
        public_key = next(
            (l.strip() for l in key_file.read_text().splitlines() if l.startswith("age1")),
            None,
        )

    if not public_key:
        return None

    return Identity(name, public_key, key_dir=kdir)


def load_current_identity() -> Identity | None:
    from .store import get_git_username
    username = get_git_username()
    return load_identity(username) if username else None


def create_recovery_identity(name: str, key_dir: Path | None = None) -> tuple[Identity, str]:
    """Create a recovery identity. Returns (identity, secret_key)."""
    kdir = key_dir or global_dir()
    identity = _keygen(name, kdir)
    secret_key = next(
        l.strip() for l in identity.key_file.read_text().splitlines()
        if l.startswith("AGE-SECRET-KEY-")
    )
    return identity, secret_key
