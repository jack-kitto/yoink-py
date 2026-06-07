# example

A walkthrough of yoink's core workflow using a fake server script that requires environment secrets to run.

## Prerequisites

```bash
pip install yoink-py
brew install age
```

## 1. First use — bootstrapping the vault

Run any yoink command from the repo root. If no vault exists it will be created automatically.

```bash
cd ..   # make sure you're at the repo root
yoink secrets
```

This will:

- Detect your git username
- Generate your identity keypair in `~/.yoink/`
- Create `.yoink/` with empty `dev`, `staging`, and `production` environments
- Print two vault-wide recovery keys — **copy these somewhere safe now**
- Open `$EDITOR` with the secrets buffer

Close the editor without saving for now (`:q` in vim, `Cmd+W` in VS Code).

## 2. Add the required secrets

The script `server.sh` needs three secrets: `DATABASE_URL`, `API_KEY`, and `JWT_SECRET`.

```bash
yoink secrets
```

Edit the `[dev]` section to look like this:

```
[dev]
DATABASE_URL=postgres://localhost:5432/myapp
API_KEY=sk_dev_abc123
JWT_SECRET=dev-jwt-secret-change-in-production
```

Save and quit. You should see:

```
  [dev] added: DATABASE_URL, API_KEY, JWT_SECRET
```

## 3. Verify the secrets are there

```bash
yoink secrets
```

You should see the values you just set. Close the editor without changing anything.

## 4. Run the failing script directly

```bash
bash example/server.sh
```

It will fail — the secrets are encrypted, not in the environment.

## 5. Run it through yoink

```bash
yoink run dev -- bash example/server.sh
```

Yoink decrypts `dev` and injects the secrets as environment variables before running the script. You should see all three values printed.

## 6. Try the access workflow

Simulate a second developer requesting access. Open a new terminal and pretend you're someone else:

```bash
# In a fresh shell with a different git username, or just observe the output:
GIT_AUTHOR_NAME=alice yoink access request
```

This writes `.yoink/requests/alice.json`. In a real team workflow, Alice would commit that file and open a PR. You'd pull it and run:

```bash
yoink access edit
```

The buffer will show Alice under `## requests`. Move her line above `## requests` and add the environments she needs:

```
## members
your-username    dev staging production
alice            dev

## requests
```

Save. Her key is added as a recipient on the `dev` vault file and her access is registered in the manifest.

## 7. Add staging secrets

Notice that `staging` is empty. Add secrets there too:

```bash
yoink secrets
```

Add a `[staging]` section:

```
[staging]
DATABASE_URL=postgres://staging-db:5432/myapp
API_KEY=sk_staging_xyz789
JWT_SECRET=staging-jwt-secret
```

Then run against staging:

```bash
yoink run staging -- bash example/server.sh
```

## 8. What's in the repo

After all this, `.yoink/` contains:

```
.yoink/
  manifest.json        # public keys and access mapping — safe to commit
  dev/.env.enc         # encrypted secrets
  staging/.env.enc
  production/.env.enc
  requests/            # any pending access requests
```

Everything in `.yoink/` should be committed. The `.key` files in `~/.yoink/` must never be committed (they're gitignored automatically).
