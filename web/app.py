"""
Galion Deep Mr Fake v2 — minimal CPU-only image edit + generate web UI.
FastAPI + Pillow. No GPU dependency.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
OUTPUTS = BASE / "outputs"
TEMPLATES = BASE / "templates"
STATIC = BASE / "static"
GALLERY_INDEX = OUTPUTS / "gallery.json"

UPLOADS.mkdir(exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_BYTES = 12 * 1024 * 1024  # 12 MB

app = FastAPI(
    title="Galion Deep Mr Fake v2",
    description="CPU/RAM-only image edit + lightweight transform demo",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_gallery() -> list[dict[str, Any]]:
    if not GALLERY_INDEX.exists():
        return []
    try:
        return json.loads(GALLERY_INDEX.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_gallery(items: list[dict[str, Any]]) -> None:
    GALLERY_INDEX.write_text(json.dumps(items[:50], indent=2), encoding="utf-8")


def _safe_ext(filename: str | None) -> str:
    name = (filename or "image.png").lower()
    ext = Path(name).suffix
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Use JPEG, PNG, or WebP")
    return ext


def _apply_edits(
    img: Image.Image,
    *,
    crop: str | None,
    max_width: int | None,
    brightness: float,
    contrast: float,
    filter_name: str,
) -> Image.Image:
    out = img.convert("RGB")

    if crop:
        try:
            parts = [int(p.strip()) for p in crop.split(",")]
            if len(parts) == 4:
                x, y, w, h = parts
                x2, y2 = x + max(w, 1), y + max(h, 1)
                x, y = max(0, x), max(0, y)
                x2 = min(out.width, x2)
                y2 = min(out.height, y2)
                if x2 > x and y2 > y:
                    out = out.crop((x, y, x2, y2))
        except ValueError:
            pass

    if max_width and max_width > 0 and out.width > max_width:
        ratio = max_width / float(out.width)
        out = out.resize(
            (max_width, max(1, int(out.height * ratio))),
            Image.Resampling.LANCZOS,
        )

    if abs(brightness - 1.0) > 1e-3:
        out = ImageEnhance.Brightness(out).enhance(max(0.1, min(3.0, brightness)))
    if abs(contrast - 1.0) > 1e-3:
        out = ImageEnhance.Contrast(out).enhance(max(0.1, min(3.0, contrast)))

    fname = (filter_name or "none").lower()
    if fname == "grayscale":
        out = ImageOps.grayscale(out).convert("RGB")
    elif fname == "blur":
        out = out.filter(ImageFilter.GaussianBlur(radius=2))
    elif fname == "sharpen":
        out = out.filter(ImageFilter.SHARPEN)
    elif fname == "edge":
        out = out.filter(ImageFilter.FIND_EDGES).convert("RGB")

    return out


def _cpu_generate(img: Image.Image) -> Image.Image:
    """Lightweight CPU transform placeholder (auto-contrast + mild unsharp)."""
    out = ImageOps.autocontrast(img, cutoff=1)
    out = out.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=2))
    return out


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
    ext = _safe_ext(file.filename)
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 12 MB)")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    job_id = uuid.uuid4().hex[:12]
    dest = UPLOADS / f"{job_id}{ext}"
    dest.write_bytes(data)

    try:
        with Image.open(dest) as im:
            w, h = im.size
            fmt = im.format or ext.lstrip(".")
    except OSError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Not a valid image") from exc

    return {
        "id": job_id,
        "filename": dest.name,
        "url": f"/media/uploads/{dest.name}",
        "width": w,
        "height": h,
        "format": fmt,
        "label": "source",
    }


@app.post("/api/generate")
async def generate(
    source_id: str = Form(...),
    crop: str = Form(""),
    max_width: int = Form(0),
    brightness: float = Form(1.0),
    contrast: float = Form(1.0),
    filter: str = Form("none"),
) -> dict[str, Any]:
    matches = list(UPLOADS.glob(f"{source_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Source image not found — upload first")
    src_path = matches[0]

    try:
        with Image.open(src_path) as im:
            edited = _apply_edits(
                im,
                crop=crop or None,
                max_width=max_width or None,
                brightness=brightness,
                contrast=contrast,
                filter_name=filter,
            )
            result = _cpu_generate(edited)
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Could not process image") from exc

    out_name = f"{source_id}_out.png"
    out_path = OUTPUTS / out_name
    result.save(out_path, format="PNG", optimize=True)

    entry = {
        "id": source_id,
        "created": _utc_now(),
        "before": f"/media/uploads/{src_path.name}",
        "after": f"/media/outputs/{out_name}",
        "label": "AI-assisted / transformed (CPU)",
        "params": {
            "crop": crop or None,
            "max_width": max_width or None,
            "brightness": brightness,
            "contrast": contrast,
            "filter": filter,
        },
    }
    gallery = _load_gallery()
    gallery.insert(0, entry)
    _save_gallery(gallery)

    return entry


@app.get("/api/gallery")
def gallery() -> dict[str, Any]:
    return {"items": _load_gallery()}


@app.get("/media/uploads/{name}")
def media_upload(name: str) -> FileResponse:
    path = UPLOADS / Path(name).name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path)


@app.get("/media/outputs/{name}")
def media_output(name: str) -> FileResponse:
    path = OUTPUTS / Path(name).name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "compute": "cpu"}
