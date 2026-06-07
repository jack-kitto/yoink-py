"""Yoink CLI."""

import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

import click

from . import __version__
from .store import (
    Manifest, get_git_username, vault_dir, requests_dir,
    DEFAULT_ENVS, RECOVERY_KEY_COUNT, YOINK_DIR,
)
from .identity import create_identity, create_recovery_identity, load_current_identity
from .crypto import encrypt_file
from .secrets import render_buffer as render_secrets, parse_buffer as parse_secrets_buf, apply_secrets
from .access import render_buffer as render_access, parse_buffer as parse_access_buf, apply_access, create_request, load_requests


# ---------------------------------------------------------------------------
# Auto-init
# ---------------------------------------------------------------------------

def _ensure_vault() -> tuple[Manifest, object]:
    """Load or create the vault. Returns (manifest, identity).

    Prints recovery keys on first init and exits if setup is incomplete.
    """
    manifest = Manifest()

    if not manifest.exists():
        _bootstrap(manifest)

    manifest.load()

    identity = load_current_identity()
    if not identity:
        username = get_git_username()
        if not username:
            click.echo("Could not detect git username. Set up git credentials first.", err=True)
            sys.exit(1)
        click.echo(f"Creating identity for {username}...")
        identity = create_identity(username)
        manifest.add_identity(username, identity.public_key)
        manifest.save()

    return manifest, identity


def _bootstrap(manifest: Manifest) -> None:
    """First-time vault setup. Prints recovery keys."""
    username = get_git_username()
    if not username:
        click.echo("Could not detect git username. Set up git credentials first.", err=True)
        sys.exit(1)

    click.echo(f"Initialising vault for {username}...")

    identity = load_current_identity()
    if not identity:
        identity = create_identity(username)

    # Vault-wide recovery keys
    recovery_keys = []
    recovery_secrets = []
    for i in range(1, RECOVERY_KEY_COUNT + 1):
        rec, secret = create_recovery_identity(f"recovery-{i}")
        recovery_keys.append(rec.public_key)
        recovery_secrets.append((i, secret))

    # Create environments
    vdir = vault_dir()
    vdir.mkdir(parents=True, exist_ok=True)
    all_recipients = [identity.public_key] + recovery_keys

    for env in DEFAULT_ENVS:
        enc = vdir / env / ".env.enc"
        enc.parent.mkdir(parents=True, exist_ok=True)
        encrypt_file(enc, "", all_recipients)
        manifest.add_env(env, all_recipients)

    manifest.add_identity(username, identity.public_key)
    manifest.set_recovery_keys(recovery_keys)
    manifest.save()

    # .gitignore
    gitignore = Path.cwd() / ".gitignore"
    entry = "*.key"
    if gitignore.exists():
        if entry not in gitignore.read_text():
            gitignore.write_text(gitignore.read_text().rstrip() + f"\n{entry}\n")
    else:
        gitignore.write_text(f"# yoink — never commit key files\n{entry}\n")

    click.echo()
    click.echo("⚠️  BACK UP YOUR RECOVERY KEYS — shown once, store in team password manager:")
    click.echo()
    for i, secret in recovery_secrets:
        click.echo(f"  recovery-{i}: {secret}")
    click.echo()
    click.echo(f"Vault ready at {YOINK_DIR}/")
    click.echo()


# ---------------------------------------------------------------------------
# Editor helper
# ---------------------------------------------------------------------------

def _open_editor(content: str, suffix: str = ".env") -> str | None:
    """Write content to a temp file, open editor, return edited content.

    Returns None if the file was unchanged.
    """
    editor = os.environ.get("EDITOR")
    if not editor:
        try:
            subprocess.run(["code", "--version"], capture_output=True, timeout=5)
            editor = "code --wait"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            editor = "vi"

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, prefix="yoink-", delete=False,
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        subprocess.run(shlex.split(editor) + [tmp_path], check=True)
        edited = Path(tmp_path).read_text()
        return edited if edited != content else None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _open_editor_with_retry(content: str, parse_fn, suffix: str = ".env"):
    """Open editor, re-opening with error annotations on parse failure."""
    current = content
    while True:
        edited = _open_editor(current, suffix=suffix)
        if edited is None:
            return None  # No changes
        try:
            result = parse_fn(edited)
            return edited, result
        except ValueError as e:
            # Annotate the buffer and re-open
            current = f"# ERROR: {e}\n# Fix the issue above and save again, or quit without saving.\n\n" + edited
            click.echo(f"Parse error: {e} — re-opening editor...")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="yoink")
@click.pass_context
def cli(ctx):
    """Yoink — lean, git-native secrets for developer teams."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
def secrets():
    """Edit all secrets in $EDITOR."""
    manifest, identity = _ensure_vault()
    content = render_secrets(manifest, identity)

    result = _open_editor_with_retry(content, parse_secrets_buf)
    if result is None:
        click.echo("No changes.")
        return

    _, parsed = result
    changes = apply_secrets(parsed, manifest, identity)

    if changes:
        for c in changes:
            click.echo(f"  {c}")
    else:
        click.echo("No changes.")


@cli.group()
def access():
    """Manage vault access."""
    pass


@access.command("edit")
def access_edit():
    """Review members and requests in $EDITOR."""
    manifest, identity = _ensure_vault()
    content = render_access(manifest)

    result = _open_editor_with_retry(content, parse_access_buf, suffix=".txt")
    if result is None:
        click.echo("No changes.")
        return

    _, (members, rejected) = result
    changes = apply_access(members, rejected, manifest, identity)

    if changes:
        for c in changes:
            click.echo(f"  {c}")
    else:
        click.echo("No changes.")


@access.command("request")
def access_request():
    """Request access to the vault (run this as a new developer)."""
    username = get_git_username()
    if not username:
        click.echo("Could not detect git username.", err=True)
        sys.exit(1)

    manifest = Manifest()
    if manifest.exists():
        manifest.load()
        if manifest.has_identity(username):
            click.echo(f"You already have access as '{username}'.")
            return

        envs = list(manifest.get_envs().keys())
    else:
        click.echo("No vault found in this directory.", err=True)
        sys.exit(1)

    if not envs:
        click.echo("No environments found in vault.", err=True)
        sys.exit(1)

    # Let them select environments via editor or just default to all
    click.echo(f"Requesting access to: {', '.join(envs)}")
    if not click.confirm("Request access to all environments?", default=True):
        click.echo("Edit the list (space-separated):")
        raw = click.prompt("Environments", default=" ".join(envs))
        envs = [e.strip() for e in raw.split() if e.strip()]

    path, recovery_secret = create_request(username, envs)

    click.echo()
    click.echo(f"Request written to {path}")
    click.echo()
    click.echo("⚠️  Back up your recovery key (shown once):")
    click.echo(f"  {recovery_secret}")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  git add {YOINK_DIR}/requests/{username}.json")
    click.echo(f"  git commit -m 'access request: {username}'")
    click.echo(f"  # open a PR — a maintainer will run: yoink access edit")


@cli.command()
@click.argument("env")
@click.argument("command", nargs=-1, required=True)
def run(env, command):
    """Run a command with secrets injected as environment variables.

    Example: yoink run dev -- python app.py
    """
    manifest, identity = _ensure_vault()

    from .secrets import parse_env
    from .crypto import decrypt_file
    vdir = vault_dir()

    enc = vdir / env / ".env.enc"
    if not enc.exists():
        click.echo(f"Environment '{env}' not found.", err=True)
        sys.exit(1)

    try:
        content = decrypt_file(enc, identity.key_file)
    except Exception as e:
        click.echo(f"Could not decrypt {env}: {e}", err=True)
        sys.exit(1)

    env_vars = parse_env(content)
    full_env = os.environ.copy()
    full_env.update({k: str(v) for k, v in env_vars.items() if v is not None})

    result = subprocess.run(command, env=full_env)
    sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    cli()


if __name__ == "__main__":
    main()
