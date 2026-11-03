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

Generate responses always include `items` (before/after entries), `count`, and `errors`. A one-image success also repeats that entry's fields at the top level (`id`, `before`, `after`, `label`, `params`).

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
  requirements.txt
  requirements-dev.txt
  README.md
  tests/              # pytest suite (synthetic Pillow images)
  templates/index.html
  static/app.css
  static/app.js
  uploads/            # runtime (gitignored except .gitkeep)
  outputs/            # runtime (gitignored except .gitkeep)
```

## Consent & labelling

Do not upload images of real people without their permission. Generated/transformed outputs are marked **AI-assisted / transformed** in the UI. This is a toolkit demo, not a face-swap product.

## API sketch

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | SPA shell |
| GET | `/api/presets` | Preset bundles and edit defaults |
| POST | `/api/upload` | Store one image (`file`) or many (`files` / repeated `file`) |
| POST | `/api/generate` | Apply edits or a `preset` to `source_id` or `source_ids`; return before/after entries |
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
