# Contributing

This is a proof-of-concept project. Contributions are welcome with that context in mind.

## What's useful

- **Bug reports** — if something breaks, open an issue with your OS, Python version, age version, and what you ran
- **Edge cases** — the parser for the secrets and access buffers is hand-rolled and likely has gaps
- **Correctness fixes** — especially around re-encryption and access management
- **Documentation** — if something in the README is unclear

## What's probably out of scope for this repo

- Large new features — this is intentionally minimal
- Performance improvements — it's a POC, not optimised
- Packaging improvements beyond what's needed to install and run it

If you have a bigger idea, open an issue first so we can discuss whether it fits here or belongs in a future rewrite.

## Running locally

```bash
git clone https://github.com/jackbcodes/yoink
cd yoink
pip install -e .
brew install age   # if not already installed
yoink --version
```

## Code style

Plain Python. No formatter enforced, but the existing code uses:

- Type hints throughout
- Docstrings on modules and public functions
- No external dependencies beyond `click`

## Before opening a PR

- Test manually against a real git repo
- Keep changes focused — one thing per PR
