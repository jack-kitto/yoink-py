# Roadmap

## What this is

A proof-of-concept Python CLI. It works, but it's not hardened. The code was written fast to test the concept, not to be a finished tool.

---

## The Go rewrite

If this concept proves useful to enough people, the plan is a rewrite in Go — mainly because Go is genuinely interesting to build with, and the [Charm Bracelet](https://charm.sh) stack ([Bubble Tea](https://github.com/charmbracelet/bubbletea), [Lip Gloss](https://github.com/charmbracelet/lipgloss), [Huh](https://github.com/charmbracelet/huh)) makes for beautiful CLI tooling. A single static binary, no Python dependency, proper TUI components rather than spawning `$EDITOR`.

The Go version would live in a separate repo. The vault format (`.yoink/` structure, `manifest.json` schema, `.enc` files) would stay compatible — a vault initialised with `yoink-py` would work with the Go binary without migration.

---

## Known gaps in this POC

**Security**

- Recovery key storage is naive — private keys live in `~/.yoink/` with no additional protection beyond file permissions
- No validation that a request file hasn't been tampered with before approval
- Error messages from age can leak path information
- Re-encryption is not fully atomic across multiple files — a crash mid-access-change could leave some files re-encrypted and others not

**UX**

- `$EDITOR` detection is best-effort — exotic editor configs may not work
- No diff preview before applying changes
- No way to see who has access without opening the access editor
- Multi-repo identity management is manual

**Reliability**

- Individual file writes are now atomic (write-then-rename), but a multi-file operation like revoking access is not — if it fails halfway, the manifest and vault files can get out of sync
- No integrity check on vault files at startup
- Large vaults are decrypted all at once

---

## Features for the Go version

These are out of scope for this POC but worth building properly:

**Vault configuration**

- Store the vault in a separate repo and reference it from multiple projects
- Multiple named vaults in one repo
- Folder-level organisation within environments
- Fine-grained access control per folder or file

**Quality of life**

- Auto PR creation on `yoink access request` via `gh` CLI
- Better recovery key management — encrypted backup, team password manager integration
- Multiple identity support for developers working across organisations
- Named vault profiles per project

**Operations**

- Atomic multi-file re-encryption using a write-ahead log or staging directory
- Integrity verification at startup
- Audit log (local, git-based)
- Secret rotation helpers

---

## Feedback

Open an [issue](https://github.com/jack-kitto/yoink-py/issues) if you hit a gap not listed here, or if something listed here is blocking you from using this.
