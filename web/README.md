# Web UI — Galion Deep Mr Fake v2

Minimal **CPU/RAM-only** single-page app for image upload, Pillow edits, named presets, batch Generate, and a before/after gallery.

**Stack (recommended):** FastAPI + plain HTML/CSS/JS. No GPU. No Gradio required (Gradio remains an optional faster demo path in `docs/BUILD_PLAN.md`).

## Features

1. **Upload** — drag/drop or file picker for one image or a batch (JPEG/PNG/WebP, up to 16 files, 12 MB each)
2. **Edit** — crop, resize, brightness, contrast, saturation, sharpness, rotate, flip, blur radius, posterize, solarize, colorize, invert, equalize, and filters (none / grayscale / blur / sharpen / edge / contour / emboss / detail / smooth / edge enhance)
3. **Presets** — named parameter bundles: Document, Soft portrait, High contrast, Mono, Duotone, Poster, Solar, Negative. Choosing one fills the edit controls; a later tweak overrides that field. `GET /api/presets` is the source of the bundles.
4. **Generate** — applies the edits, then a CPU-only Pillow finish (default: autocontrast + mild unsharp). Presets may select a softer, document, or edits-only finish. **onnxruntime is not installed and is not required.** A CPU ONNX build can be added later; the default path must keep working without it.
5. **Batch** — one Generate call accepts `source_ids` (comma-separated or a JSON array) for images already uploaded, and returns one before/after entry per id. A single `source_id` still works.
6. **Gallery** — shows original vs result side by side; download result. Outputs are labelled **AI-assisted / transformed (CPU)**.

### Edit order

Crop → rotate (counter-clockwise; 90/180/270 are lossless) → flip → max-width resize → brightness, contrast, saturation, sharpness → extra blur → equalize → invert → posterize → solarize → colorize → named filter → CPU finish.

### Batch examples

```bash
# Several files in one upload (field name `file` or `files`)
curl -F "files=@a.png" -F "files=@b.png" http://127.0.0.1:8765/api/upload

# Preset on already-uploaded ids
curl -F "source_ids=ID_A,ID_B" -F "preset=document" http://127.0.0.1:8765/api/generate

# Single image, explicit ops (omitted fields keep the preset or the defaults)
curl -F "source_id=ID_A" -F "rotate=90" -F "flip=horizontal" \
  -F "saturation=0.2" -F "posterize=4" http://127.0.0.1:8765/api/generate
```

Generate responses always include `items` (before/after entries), `count`, and `errors`. A one-image success also repeats that entry's fields at the top level (`id`, `before`, `after`, `label`, `params`). Each item also includes `ai_generated: true`, `consent_attested`, `timestamp`, and `meta` (URL of that output's sidecar).

Optional form field `consent_attested` (`true` / `false`, default false) is recorded on every image in the request, including a batch. Omitted means false. Invalid values return 400, same as the other boolean edit flags.

## Run

From the repository root: `make install` then `make run`. CPU-only Docker: `docker compose up --build` (port 8765). Details: [../docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md).

Manual equivalent:

```bash
cd web
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765

## Layout

```
web/
  app.py              # FastAPI app + image pipeline
  mcp_server.py       # MCP stdio + loopback HTTP
  vectors.py          # local consented-job index
  requirements.txt
  requirements-dev.txt
  README.md
  tests/              # pytest suite (synthetic Pillow images)
  templates/index.html
  static/app.css
  static/app.js
  uploads/            # runtime (gitignored except .gitkeep)
  outputs/            # runtime (gitignored except .gitkeep)
  data/vectors/       # local index (gitignored except .gitkeep)
```

## Consent & labelling

Do not upload images of real people without their permission. The studio shows a short Accept control (unchecked, never auto-approved) and a link to `GET /consent`. Accept or Agree records a session. Until that happens, the UI blocks processing and `POST /api/generate` returns 403.

`consent_attested` is still the image-rights field (`true` / `false`, default false). The UI sends `true` after Accept. One answer covers every image in that generate call.

Each successful output writes a provenance sidecar beside the PNG:

`outputs/{source_id}_{suffix}.meta.json`

The sidecar records `timestamp`, `created_at`, `params`, the label **AI-assisted / transformed (CPU)**, `consent_attested`, `consent_agreed`, `session_id`, `client_ip` (the request’s connecting address), `user_id` (`anonymous` — no account is invented), `user_label` (`session:<id>`), responsibility flags, and `ai_generated: true`. The gallery entry carries `ai_generated: true` and the image-rights flag, and the card shows an AI-generated badge. This is a toolkit demo, not a face-swap product.

Phase 2 watermarking is not implemented. `embed_imperceptible_mark` in `app.py` is a hook only and is not called. See [`docs/V3_PLAN.md`](../docs/V3_PLAN.md) for video and paid GPU work, which is also not in this UI.

A consented generate also writes a local vector row under `data/vectors/`. The row keeps job and consent metadata. It does not copy `client_ip`. Agents use the MCP server instead of the browser: [`docs/MCP_AND_VECTOR_STORE.md`](../docs/MCP_AND_VECTOR_STORE.md). From the repo root, `make mcp` (stdio) or `make mcp-http` (loopback).

## API sketch

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Image studio shell (phone burger for Advanced; denser controls on wide screens) |
| GET | `/consent` | Full notice (MIT license, risks, agreement). Visiting does not agree |
| POST | `/consent/agree` | Form agreement, then redirect to `/?agreed=1` |
| GET | `/api/consent/status` | `{session_id, consent_agreed, user_id}` — starts false |
| POST | `/api/consent/agree` | Active session agreement. Not called on page load |
| GET | `/api/presets` | Preset bundles and edit defaults |
| POST | `/api/upload` | Store one image (`file`) or many (`files` / repeated `file`) |
| POST | `/api/generate` | Requires session agreement (403 otherwise). Optional `consent_attested` (default false). Returns before/after entries plus a sidecar per output |
| GET | `/api/gallery` | List recent before/after pairs |
| GET | `/media/{kind}/{name}` | Serve upload or output file |
| GET | `/health` | `{"status":"ok","compute":"cpu"}` |

## Tests

From the repository root (CPU only; tests build tiny images with Pillow and use temporary upload/output directories):

```bash
pip install -r web/requirements.txt -r web/requirements-dev.txt
python -m pytest web/tests -q
```

The same command is what [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on Ubuntu for Python 3.11 and 3.12.
