# Galion Deep Mr Fake v2

**Public MIT side project** under the [Galion](https://galion.app) stack — open to everybody.

Galion Deep Mr Fake v2 is a **CPU/RAM-only**, consent-first toolkit for **simple image edit + lightweight transform** workflows that sit beside Galion One (hosted agents), Galion Voice (sherpa-onnx cascade), and the Poland operating company. It is **not** a non-consensual face-swap or celebrity deepfake product: synthetic media of real people requires **explicit consent before ingest**, **no zero-shot cloning of arbitrary real people**, and **AI-generated-content labelling** consistent with Galion Voice locks and the EU AI Act.

> **Open decision:** the long-term product surface (detection/labelling vs. licensed synthetic personas vs. creative filters) is not locked. **Recommended default:** a small open toolkit — image prep + CPU transforms + labelling hooks — that Galion Voice/One can call, with a minimal web UI for demos. See [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md).

## Status

**0.2.0** — runnable web UI, CPU pipeline, tests/CI, Docker/DX, consent sidecar, and AI labelling. Repo: [galion-studio/Galion-Deep-Mr-Fake-v2](https://github.com/galion-studio/Galion-Deep-Mr-Fake-v2).

## Install / usage (web MVP)

```bash
cd web
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765 — drop a photo, optionally attest consent, press **Generate**, and compare before/after. Crop, color, presets, and the other CPU edits live under **Advanced**.

Details: [`web/README.md`](web/README.md).

## Tests

CPU-only. From the repository root:

```bash
pip install -r web/requirements.txt -r web/requirements-dev.txt
python -m pytest web/tests -q
```

GitHub Actions runs that command on Ubuntu for Python 3.11 and 3.12.

## Stack fit

| Constraint | Choice |
|---|---|
| Compute | **CPU/RAM only** (no GPU dependency) |
| Voice adjacency | Compatible with sherpa-onnx Voice cascade; no zero-shot real-person clone |
| Fleet | Runs on Galion One EPYC/Xeon class nodes or a laptop |
| Legal seat | Poland operator · GDPR + AI Act labelling |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). PRs welcome.

## License

[MIT](LICENSE) © 2026 Galion Studio / Maciej Grajczyk
