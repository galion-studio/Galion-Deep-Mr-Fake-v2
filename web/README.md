# Web UI — Galion Deep Mr Fake v2

Minimal **CPU/RAM-only** single-page app for image upload, basic editing, a lightweight Generate step, and a before/after gallery.

**Stack (recommended):** FastAPI + plain HTML/CSS/JS. No GPU. No Gradio required (Gradio remains an optional faster demo path in `docs/BUILD_PLAN.md`).

## Features (v1 MVP)

1. **Upload** — drag/drop or file picker for a source image (JPEG/PNG/WebP)
2. **Edit** — crop box (x/y/w/h), resize (max width), brightness, contrast, filters (none / grayscale / blur / sharpen)
3. **Generate** — applies edits then a simple CPU transform (Pillow; hook ready for a small ONNX CPU model later)
4. **Gallery** — shows original vs result side by side; download result

## Run

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
  README.md
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
| POST | `/api/upload` | Store source image |
| POST | `/api/generate` | Apply edits + transform; return paths |
| GET | `/api/gallery` | List recent before/after pairs |
| GET | `/media/{kind}/{name}` | Serve upload or output file |
