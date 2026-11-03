# Development

Setup for the CPU-only FastAPI app in `web/`. Product rules (consent, no zero-shot cloning, labelling) stay in `CONTRIBUTING.md`. The feature overview stays in `web/README.md`. Video encode, pay-as-you-go billing, API keys, rate limits, and the GPU island are planned in [V3_PLAN.md](V3_PLAN.md) and are not part of this setup.

Requires Python 3.11+ (3.12 matches the Docker image) with the stdlib `venv` module. On Debian/Ubuntu that is the `python3-venv` package. Docker is optional.

## Install and run

From the repository root:

```bash
make install
make run
```

The same steps without Make:

```bash
web/scripts/install.sh
web/scripts/run.sh
```

`make install` creates `web/.venv` and installs `web/requirements.txt` plus the pinned dev tools in `requirements-dev.txt`. When `web/requirements-dev.txt` is present (pytest extras), it is installed too. `make run` starts uvicorn with reload on http://127.0.0.1:8765.

Override the interpreter or bind address when you need to:

```bash
make install PYTHON=python3.12
make run HOST=127.0.0.1 PORT=8765
```

Open http://127.0.0.1:8765. `GET /health` returns `{"status":"ok","compute":"cpu"}`.

## MCP server

The agent surface is a second process. It does not replace `make run`.

```bash
make mcp        # stdio, for an MCP client on this machine
make mcp-http   # http://127.0.0.1:8766/mcp
```

`MCP_PORT` overrides 8766. The HTTP listener stays on loopback. Consent, tools, and the local vector index are documented in [MCP_AND_VECTOR_STORE.md](MCP_AND_VECTOR_STORE.md).

## Docker

The image is `python:3.12-slim` and installs only `web/requirements.txt`. It does not use a GPU base image. The process listens on `0.0.0.0:8765` inside the container so the published port works. Local `make run` stays on `127.0.0.1`.

```bash
docker compose up --build
```

Or build and run the image directly:

```bash
make docker-build
docker run --rm -p 8765:8765 galion-deep-mr-fake-web:local
```

`make docker-run` builds, then runs in the foreground. `make down` stops the compose stack. Uploads and outputs live in the container filesystem (`web/uploads`, `web/outputs`) and are not copied from the host.

## Lint and format

Config is `ruff.toml`. Lint uses Ruff's default rules (`E4`, `E7`, `E9`, `F`) so the current app does not need a style rewrite to pass. The formatter is Ruff's formatter with Black-compatible style: line length 100, double quotes. Length 100 matches the current `web/app.py`, so formatting it does not rewrite the file.

```bash
make lint
make format
CHECK=1 make format
```

Dev pins:

| Package | Version | Role |
|---|---|---|
| ruff | 0.17.3 | `make lint`, `make format` |
| black | 26.10.1 | Optional. Use line length 100, same as `ruff.toml`. |

Black reads `[tool.black]` in `pyproject.toml` (line length 100, Python 3.11 and 3.12). It is not a second rewrite pass. To run it yourself:

```bash
web/.venv/bin/black web
```

`make format` does not invoke Black. Prefer `make format` for day-to-day edits. Both tools leave the current `web/app.py` unchanged.

Ruff is run with `--no-cache`, so it does not write `.ruff_cache/` into the tree.

## Tests

The pytest suite and GitHub Actions workflow are separate from this setup. When `web/tests` is in your checkout, `make install` also installs `web/requirements-dev.txt` if that file exists. From the repository root:

```bash
web/.venv/bin/python -m pytest web/tests -q
```
