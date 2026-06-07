"""Access — request workflow and the access editor buffer."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .crypto import reencrypt_file, encrypt_file
from .identity import Identity, create_identity, create_recovery_identity
from .store import Manifest, find_enc_files, get_git_username, requests_dir, vault_dir, global_dir

# ---------------------------------------------------------------------------
# Request creation (run by new dev)
# ---------------------------------------------------------------------------

def create_request(username: str, environments: list[str]) -> tuple[str, str]:
    """Generate keypair + recovery key, write request JSON.

    Returns (request_path, recovery_secret_key) so CLI can print the key.
    """
    from .store import YOINK_DIR
    identity = create_identity(username)
    recovery, recovery_secret = create_recovery_identity(f"{username}-recovery")

    data = {
        "identity": username,
        "public_key": identity.public_key,
        "recovery_public_key": recovery.public_key,
        "environments": environments,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }

    rdir = requests_dir()
    rdir.mkdir(parents=True, exist_ok=True)
    path = rdir / f"{username}.json"
    path.write_text(json.dumps(data, indent=2) + "\n")

    return str(path), recovery_secret


def load_requests() -> list[dict]:
    rdir = requests_dir()
    if not rdir.exists():
        return []
    return [
        json.loads(f.read_text()) | {"_path": str(f)}
        for f in sorted(rdir.glob("*.json"))
    ]


# ---------------------------------------------------------------------------
# Buffer render / parse
# ---------------------------------------------------------------------------

HEADER = """\
# Access management
# members: edit environment list to change access, delete line to revoke
# requests: move a line above '## requests' to approve, delete to reject
"""


def render_buffer(manifest: Manifest) -> str:
    lines = [HEADER, "## members"]

    for name, info in sorted(manifest.get_identities().items()):
        envs = _envs_for_identity(name, manifest)
        lines.append(f"{name}    {' '.join(sorted(envs))}")

    lines += ["", "## requests"]

    for req in load_requests():
        envs = " ".join(req.get("environments", []))
        lines.append(f"{req['identity']}    {envs}")

    return "\n".join(lines) + "\n"


def _envs_for_identity(name: str, manifest: Manifest) -> list[str]:
    pk = manifest.get_identity_key(name)
    if not pk:
        return []
    return [
        env for env, info in manifest.get_envs().items()
        if pk in info.get("recipients", [])
    ]


# ---------------------------------------------------------------------------
# Parse buffer
# ---------------------------------------------------------------------------

def parse_buffer(text: str) -> tuple[dict[str, list[str]], list[str]]:
    """Parse access buffer.

    Returns:
        members: {username: [env, ...]}
        rejected: [username, ...]  — requests that were deleted
    """
    members: dict[str, list[str]] = {}
    in_members = False
    in_requests = False
    seen_requests: set[str] = set()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip comment lines but not section headers
        if stripped.startswith("#") and stripped not in ("## members", "## requests"):
            continue
        if stripped == "## members":
            in_members = True
            in_requests = False
            continue
        if stripped == "## requests":
            in_members = False
            in_requests = True
            continue

        parts = stripped.split()
        if not parts:
            continue
        name = parts[0]
        envs = parts[1:]

        if in_members:
            members[name] = envs
        elif in_requests:
            seen_requests.add(name)

    # Requests not present in buffer were deleted → rejected
    all_requests = {r["identity"] for r in load_requests()}
    rejected = [r for r in all_requests if r not in seen_requests and r not in members]

    return members, rejected


# ---------------------------------------------------------------------------
# Apply buffer changes
# ---------------------------------------------------------------------------

def apply_access(
    members: dict[str, list[str]],
    rejected: list[str],
    manifest: Manifest,
    identity: Identity,
) -> list[str]:
    """Reconcile parsed buffer against current manifest state.

    - New member (was a request, now in members) → approve
    - Removed member → revoke
    - Changed envs → re-encrypt accordingly
    - Rejected requests → delete request file
    Returns list of changes made.
    """
    changes = []
    requests_by_name = {r["identity"]: r for r in load_requests()}
    vdir = vault_dir()
    all_envs = list(manifest.get_envs())

    # --- Approvals: name in members but not yet in manifest identities ---
    for name, envs in members.items():
        if not manifest.has_identity(name):
            req = requests_by_name.get(name)
            if not req:
                changes.append(f"WARNING: no request found for '{name}', skipping")
                continue
            _approve(name, req, envs, manifest, identity, vdir)
            changes.append(f"approved {name} → {' '.join(envs) or '(no envs)'}")

    # --- Revocations: name in manifest but not in new members ---
    for name in list(manifest.get_identities()):
        if name not in members:
            _revoke(name, manifest, identity, vdir)
            changes.append(f"revoked {name}")

    # --- Env changes: name in both, but envs differ ---
    for name, new_envs in members.items():
        if not manifest.has_identity(name):
            continue  # just approved above
        old_envs = set(_envs_for_identity(name, manifest))
        new_set = set(new_envs)
        if old_envs == new_set:
            continue
        pk = manifest.get_identity_key(name)
        user_info = manifest.get_identities()[name]
        recovery_key = user_info.get("recovery_key")

        # Grant access to added envs
        for env in new_set - old_envs:
            recipients = manifest.get_recipients(env)
            if pk not in recipients:
                recipients = recipients + [pk]
                if recovery_key and recovery_key not in recipients:
                    recipients.append(recovery_key)
                enc = vdir / env / ".env.enc"
                if enc.exists():
                    reencrypt_file(enc, recipients, identity.key_file)
                manifest.set_recipients(env, recipients)
            changes.append(f"granted {name} access to [{env}]")

        # Revoke access from removed envs
        for env in old_envs - new_set:
            recipients = [
                r for r in manifest.get_recipients(env)
                if r != pk and r != recovery_key
            ]
            enc = vdir / env / ".env.enc"
            if enc.exists():
                reencrypt_file(enc, recipients, identity.key_file)
            manifest.set_recipients(env, recipients)
            changes.append(f"revoked {name} from [{env}]")

    # --- Rejections ---
    for name in rejected:
        req = requests_by_name.get(name)
        if req and req.get("_path"):
            Path(req["_path"]).unlink(missing_ok=True)
            changes.append(f"rejected request from {name}")

    manifest.save()
    return changes


def _approve(
    name: str,
    req: dict,
    envs: list[str],
    manifest: Manifest,
    identity: Identity,
    vdir: Path,
) -> None:
    pk = req["public_key"]
    recovery_key = req.get("recovery_public_key")

    for env in envs:
        recipients = manifest.get_recipients(env)
        if pk not in recipients:
            recipients = recipients + [pk]
        if recovery_key and recovery_key not in recipients:
            recipients.append(recovery_key)
        enc = vdir / env / ".env.enc"
        if enc.exists():
            reencrypt_file(enc, recipients, identity.key_file)
        manifest.set_recipients(env, recipients)

    manifest.add_identity(name, pk, recovery_key=recovery_key)

    # Remove request file
    if req.get("_path"):
        Path(req["_path"]).unlink(missing_ok=True)


def _revoke(name: str, manifest: Manifest, identity: Identity, vdir: Path) -> None:
    user_info = manifest.get_identities().get(name, {})
    pk = user_info.get("public_key")
    recovery_key = user_info.get("recovery_key")

    for env, info in manifest.get_envs().items():
        recipients = info.get("recipients", [])
        updated = [r for r in recipients if r != pk and r != recovery_key]
        if updated != recipients:
            enc = vdir / env / ".env.enc"
            if enc.exists():
                reencrypt_file(enc, updated, identity.key_file)
            manifest.set_recipients(env, updated)

    manifest.remove_identity(name)
