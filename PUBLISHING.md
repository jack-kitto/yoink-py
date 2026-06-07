# Publishing

Notes for maintainers on releasing to PyPI and deploying the landing page.

---

## PyPI

### One-time setup

1. Create an account at [pypi.org](https://pypi.org) if you don't have one.

2. Generate an API token at pypi.org → Account Settings → API tokens.
   Scope it to the `yoink-py` project (or "Entire account" for the first upload
   before the project exists).

3. Store the token. When `twine` prompts for credentials use:
   - Username: `__token__`
   - Password: the token (starts with `pypi-`)

   Or create `~/.pypirc`:

   ```ini
   [pypi]
   username = __token__
   password = pypi-your-token-here
   ```

4. Install build tools:
   ```bash
   pip install build twine
   ```

### Releasing

1. Bump the version in `yoink/__init__.py` and `pyproject.toml` to match.

2. Build:

   ```bash
   python -m build
   ```

   This produces `dist/yoink_py-<version>-py3-none-any.whl` and a `.tar.gz`.

3. Check the build:

   ```bash
   twine check dist/*
   ```

4. Upload to TestPyPI first:

   ```bash
   twine upload --repository testpypi dist/*
   ```

   Install from TestPyPI to verify it works:

   ```bash
   pip install --index-url https://test.pypi.org/simple/ yoink-py
   yoink --version
   ```

5. Upload to PyPI:

   ```bash
   twine upload dist/*
   ```

6. Tag the release:

   ```bash
   git tag -a v0.1.0 -m "v0.1.0"
   git push origin v0.1.0
   ```

7. Create a GitHub release from the tag. Paste the relevant section from
   ROADMAP.md as release notes.

---

## GitHub Pages (landing page)

No GitHub Action needed. GitHub handles it natively:

1. Push `docs/index.html` to the `main` branch.

2. Go to the repo on GitHub → **Settings** → **Pages**.

3. Under "Build and deployment":
   - Source: **Deploy from a branch**
   - Branch: `main`
   - Folder: `/docs`

4. Click **Save**. GitHub will deploy within a minute or two.

5. Your site will be live at:
   ```
   https://jack-kitto.github.io/yoink-py/
   ```

To update the landing page, just edit `docs/index.html` and push to `main`.
GitHub redeploys automatically on every push.

If you want a custom domain later, add a `docs/CNAME` file containing the
domain name and point your DNS to GitHub Pages.

---

## Commit and tag conventions

```
feat: short description       new capability
fix: short description        bug fix
docs: short description       readme, roadmap, comments
chore: short description      packaging, tooling, non-code
```

Release tags follow semver: `v0.1.0`, `v0.2.0`, etc.
