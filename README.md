# Yoink

Lean, repo-native secrets for developer teams.

Encrypted secrets live in your repo. Developers decrypt only what they have access to.

## Requirements

- Python 3.9+
- [age](https://github.com/FiloSottile/age) (`brew install age`)
- Git

## Install

```bash
pip install yoink-py
```

## Commands

```
yoink secrets              Edit all secrets in $EDITOR
yoink access edit          Review members and requests in $EDITOR
yoink access request       Request access to the vault (new developers)
yoink run <env> -- <cmd>   Run a command with secrets injected
```

## Quick start

```bash
cd your-repo
yoink secrets   # bootstraps vault on first run, then opens editor
```

The vault is created in `.yoink/` with `dev`, `staging`, and `production` environments.
Two vault-wide recovery keys are printed once — back them up in your team password manager.

## Secrets editor

`yoink secrets` opens a buffer like:

```
[dev]
DATABASE_URL=postgres://localhost/mydb
API_KEY=sk_test_abc

[staging]
DATABASE_URL=postgres://staging/mydb

[production]
DATABASE_URL=postgres://prod/mydb
```

- Edit values inline
- Add a key to add it
- Delete a line to remove a secret
- Add a new `[environment]` header to create a new environment
- Save and quit — changes are applied

## Access editor

`yoink access edit` opens a buffer like:

```
## members
jack    dev staging production
sarah   dev staging

## requests
bob     dev staging
```

- Edit the environment list on a member line to change their access
- Delete a member line to revoke their access
- Move a request line above `## requests` to approve it
- Delete a request line to reject it
- Save and quit — changes are applied

## New developer workflow

```bash
yoink access request   # generates keypair, writes .yoink/requests/<you>.json
git add .yoink/requests/<you>.json
git commit -m "access request: <you>"
# open a PR
```

A maintainer pulls the PR and runs `yoink access edit`. Moving your line above
`## requests` and saving approves you. The vault files are re-encrypted to include
your key.

## How it works

- Secrets are encrypted with [age](https://github.com/FiloSottile/age) and stored as `.enc` files in `.yoink/`
- Each developer has an identity keypair in `~/.yoink/`
- The manifest (`manifest.json`) tracks who has access to what
- Re-encryption happens automatically when access changes

## Limitations

- Git history is immutable — revoking access doesn't erase past exposure
- No runtime audit — who decrypted what and when is not tracked
- Best for small-to-medium teams
