# Contributing to Galion Deep Mr Fake v2

Thanks for helping. This is a **public MIT** Galion side project. Keep changes small, reversible, and CPU-friendly.

## Ground rules

1. **Consent first.** Do not add features that clone, swap, or impersonate a real person’s face or voice without an explicit, auditable consent path. Zero-shot cloning of arbitrary real people is **out of scope**.
2. **CPU/RAM only.** No hard GPU dependency. Optional accelerators must degrade cleanly to CPU.
3. **Label synthetic media.** UI and APIs must make AI-generated or transformed outputs identifiable (AI Act-style labelling).
4. **No non-consensual deepfake porn or harassment tooling.** Such PRs will be rejected; see the Code of Conduct.

## How to contribute

1. Fork the repo and create a branch from `main` (`feat/…`, `fix/…`, `docs/…`).
2. Prefer small PRs with a clear description and a way to verify (command or screenshot).
3. For the web app: keep the UI minimal; update `web/README.md` and `requirements.txt` if dependencies change.
4. Do not commit binary model weights larger than GitHub’s limits; document download steps instead.
5. By contributing, you agree your work is licensed under the MIT License.

## Development

From the repository root:

```bash
make install
make run
```

CPU-only Docker, publishing port 8765:

```bash
docker compose up --build
```

Lint and format with Ruff (`make lint`, `make format`). Black is pinned at the same line length in `requirements-dev.txt` and `pyproject.toml`.

Manual venv commands, image details, and how to run pytest when `web/tests` is present: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Questions

Open a GitHub issue. Product vision open decisions live in `docs/BUILD_PLAN.md`.
