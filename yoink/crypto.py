"""
crypto.py — thin wrappers around the age binary.

Yoink delegates all cryptography to age (https://github.com/FiloSottile/age).
It doesn't implement any crypto itself. Install age with: brew install age
"""

import subprocess
from pathlib import Path


def encrypt(plaintext: str, recipients: list[str]) -> bytes:
    """Encrypt plaintext for one or more age public key recipients."""
    if not recipients:
        raise ValueError("Cannot encrypt with no recipients")
    args = ["age"]
    for r in recipients:
        args += ["-r", r]
    result = subprocess.run(args, input=plaintext.encode(), capture_output=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"age encrypt failed: {result.stderr.decode(errors='replace')}")
    return result.stdout


def decrypt(ciphertext: bytes, key_file: Path) -> str:
    """Decrypt age-encrypted bytes using a secret key file."""
    result = subprocess.run(
        ["age", "-d", "-i", str(key_file)],
        input=ciphertext, capture_output=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"age decrypt failed: {result.stderr.decode(errors='replace')}")
    return result.stdout.decode()


def encrypt_file(path: Path, plaintext: str, recipients: list[str]) -> None:
    """Encrypt plaintext and write to path atomically.

    Writes to a .tmp sibling first, then renames over the target. This means
    a crash or disk-full mid-write leaves the original file intact rather than
    producing a corrupt or zero-byte ciphertext with the plaintext gone.
    """
    ciphertext = encrypt(plaintext, recipients)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_bytes(ciphertext)
        tmp.replace(path)  # atomic on POSIX — either old or new, never corrupt
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def decrypt_file(path: Path, key_file: Path) -> str:
    """Read and decrypt a vault file."""
    return decrypt(path.read_bytes(), key_file)


def reencrypt_file(path: Path, new_recipients: list[str], key_file: Path) -> None:
    """Decrypt and re-encrypt a vault file with a new recipient list.

    Used when access changes — adding or revoking a member.
    """
    plaintext = decrypt_file(path, key_file)
    encrypt_file(path, plaintext, new_recipients)
