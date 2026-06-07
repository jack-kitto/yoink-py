"""Secrets — render/edit/apply dotenv-style secrets per environment."""

from __future__ import annotations

from .crypto import decrypt_file, encrypt_file
from .identity import Identity
from .store import Manifest, vault_dir


HEADER = """\
# Secrets management
# Edit values below. Lines are KEY=value.
# Section headers are environments.
"""


def parse_env(content: str) -> dict[str, str | None]:
    """Parse KEY=value lines into a dict.

    Blank lines and comment lines are ignored.
    """
    data: dict[str, str | None] = {}

    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid line (expected KEY=value): {raw}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Invalid key in line: {raw}")
        data[key] = value

    return data


def dump_env(data: dict[str, str | None]) -> str:
    lines = []
    for key in sorted(data):
        value = data[key]
        lines.append(f"{key}={'' if value is None else value}")
    return "\n".join(lines) + ("\n" if lines else "")


def render_buffer(manifest: Manifest, identity: Identity) -> str:
    """Render all env secrets into a single editor buffer."""
    vdir = vault_dir()
    chunks = [HEADER.rstrip(), ""]

    for env in sorted(manifest.get_envs()):
        enc = vdir / env / ".env.enc"
        plaintext = ""
        if enc.exists():
            try:
                plaintext = decrypt_file(enc, identity.key_file).rstrip()
            except Exception as e:
                raise RuntimeError(f"Could not decrypt environment '{env}': {e}") from e

        chunks.append(f"## {env}")
        if plaintext:
            chunks.append(plaintext)
        chunks.append("")

    return "\n".join(chunks).rstrip() + "\n"


def parse_buffer(text: str) -> dict[str, dict[str, str | None]]:
    """Parse editor buffer into {env: {KEY: value}}."""
    result: dict[str, dict[str, str | None]] = {}
    current_env: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_env, current_lines
        if current_env is None:
            return
        result[current_env] = parse_env("\n".join(current_lines))
        current_lines = []

    for raw in text.splitlines():
        stripped = raw.strip()

        if stripped.startswith("#") and not stripped.startswith("## "):
            continue

        if stripped.startswith("## "):
            flush()
            current_env = stripped[3:].strip()
            if not current_env:
                raise ValueError("Empty environment header")
            continue

        if current_env is None:
            if not stripped:
                continue
            raise ValueError(f"Content outside an environment section: {raw}")

        current_lines.append(raw)

    flush()
    return result


def apply_secrets(
    parsed: dict[str, dict[str, str | None]],
    manifest: Manifest,
    identity: Identity,
) -> list[str]:
    """Encrypt and write updated secrets for each environment."""
    vdir = vault_dir()
    changes: list[str] = []

    for env in sorted(manifest.get_envs()):
        if env not in parsed:
            continue

        enc = vdir / env / ".env.enc"
        recipients = manifest.get_recipients(env)
        new_plaintext = dump_env(parsed[env])

        old_plaintext = ""
        if enc.exists():
            try:
                old_plaintext = decrypt_file(enc, identity.key_file)
            except Exception as e:
                raise RuntimeError(f"Could not decrypt environment '{env}': {e}") from e

        if old_plaintext == new_plaintext:
            continue

        enc.parent.mkdir(parents=True, exist_ok=True)
        encrypt_file(enc, new_plaintext, recipients)
        changes.append(f"updated {env}")

    manifest.save()
    return changes
