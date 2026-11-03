"""
Galion Deep Mr Fake v2 — CPU-only image edit + generate web UI.

FastAPI + Pillow. No GPU dependency. Generate stays on the CPU Pillow path
(autocontrast / unsharp, with a few extra finish modes). onnxruntime is not
required and is not imported.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
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
MAX_BATCH = 16
_ID_RE = re.compile(r"^[a-f0-9]{12}$")
_HEX_COLOR_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# Keys the UI may override after a preset. `finish` is preset/API-only so a
# named bundle can pick a CPU finish without the form clobbering it.
_ADJUST_KEYS = (
    "brightness",
    "contrast",
    "saturation",
    "sharpness",
    "rotate",
    "flip",
    "filter",
    "posterize",
    "solarize",
    "invert",
    "equalize",
    "colorize_black",
    "colorize_white",
    "blur_radius",
)

EDIT_DEFAULTS: dict[str, Any] = {
    "crop": None,
    "max_width": None,
    "brightness": 1.0,
    "contrast": 1.0,
    "saturation": 1.0,
    "sharpness": 1.0,
    "rotate": 0.0,
    "flip": "none",
    "filter": "none",
    "posterize": 0,
    "solarize": 0,
    "invert": False,
    "equalize": False,
    "colorize_black": "",
    "colorize_white": "",
    "blur_radius": 0.0,
    "finish": "default",
}

# Named bundles. Values overlay EDIT_DEFAULTS; omitted keys stay at defaults.
# `finish` selects the CPU Generate step (see `_cpu_generate`).
PRESETS: dict[str, dict[str, Any]] = {
    "document": {
        "label": "Document",
        "description": "Grayscale page scan: equalized, high contrast, sharpened.",
        "params": {
            "brightness": 1.10,
            "contrast": 1.65,
            "saturation": 0.0,
            "sharpness": 2.0,
            "filter": "grayscale",
            "equalize": True,
            "finish": "document",
        },
    },
    "soft-portrait": {
        "label": "Soft portrait",
        "description": "Slightly brighter, softer contrast, mild blur, light finish.",
        "params": {
            "brightness": 1.05,
            "contrast": 0.90,
            "saturation": 0.80,
            "sharpness": 0.75,
            "blur_radius": 0.8,
            "finish": "soft",
        },
    },
    "high-contrast": {
        "label": "High contrast",
        "description": "Strong contrast, richer color, extra sharpness.",
        "params": {
            "brightness": 1.0,
            "contrast": 1.85,
            "saturation": 1.35,
            "sharpness": 1.45,
        },
    },
    "mono": {
        "label": "Mono",
        "description": "Black and white with a modest contrast lift.",
        "params": {
            "saturation": 0.0,
            "contrast": 1.20,
            "sharpness": 1.10,
            "filter": "grayscale",
        },
    },
    "duotone": {
        "label": "Duotone",
        "description": "Map luminance onto a navy-to-sand colorize pair.",
        "params": {
            "contrast": 1.25,
            "sharpness": 1.10,
            "colorize_black": "#0d1b2a",
            "colorize_white": "#e0a96d",
            "finish": "soft",
        },
    },
    "poster": {
        "label": "Poster",
        "description": "Posterized color with a contrast bump.",
        "params": {
            "posterize": 3,
            "saturation": 1.60,
            "contrast": 1.35,
            "sharpness": 1.20,
        },
    },
    "solar": {
        "label": "Solar",
        "description": "Solarize midtones, then a small contrast lift.",
        "params": {
            "solarize": 140,
            "brightness": 1.05,
            "contrast": 1.30,
            "saturation": 1.15,
        },
    },
    "negative": {
        "label": "Negative",
        "description": "Invert colors. Skips autocontrast so the negative holds.",
        "params": {
            "invert": True,
            "contrast": 1.15,
            "finish": "none",
        },
    },
}

_FLIP_ALIASES = {
    "": "none",
    "none": "none",
    "h": "horizontal",
    "horizontal": "horizontal",
    "left-right": "horizontal",
    "v": "vertical",
    "vertical": "vertical",
    "top-bottom": "vertical",
    "both": "both",
    "hv": "both",
}

_FILTERS = {
    "none",
    "grayscale",
    "blur",
    "sharpen",
    "edge",
    "contour",
    "emboss",
    "detail",
    "smooth",
    "edge_enhance",
}

app = FastAPI(
    title="Galion Deep Mr Fake v2",
    description="CPU/RAM-only image edit, presets, batch, and lightweight transform",
    version="0.2.0",
)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

_FIELD_HELP = {
    "brightness": "Brightness must be a number between 0.1 and 3.0.",
    "contrast": "Contrast must be a number between 0.1 and 3.0.",
    "saturation": "Saturation must be a number between 0 and 3.",
    "sharpness": "Sharpness must be a number between 0 and 3.",
    "rotate": "Rotate must be a number of degrees.",
    "max_width": "Max width must be a whole number of pixels. Use 0 to keep the original width.",
    "posterize": "Posterize bits must be a whole number from 0 to 8. Use 0 to turn it off.",
    "solarize": "Solarize must be a whole number from 0 to 255. Use 0 to turn it off.",
    "blur_radius": "Blur radius must be a number of pixels from 0 to 30.",
    "preset": "Choose a preset from the list, or leave it on Custom.",
    "source_id": "Missing source image. Upload a file, or paste already-uploaded ids, before generating.",
    "source_ids": "Batch ids must be comma-separated upload ids.",
    "filter": "Filter must be one of the listed CPU filters.",
    "flip": "Flip must be none, horizontal, vertical, or both.",
}


def _validation_detail(exc: RequestValidationError) -> str:
    messages: list[str] = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", []) if part not in ("body", "query", "path")]
        field = loc[-1] if loc else ""
        help_text = _FIELD_HELP.get(field)
        if help_text:
            messages.append(help_text)
            continue
        msg = err.get("msg") or "invalid value"
        messages.append(f"{field}: {msg}" if field else str(msg))
    deduped = list(dict.fromkeys(messages))
    if not deduped:
        return "The request is missing required fields or has invalid values."
    return " ".join(deduped)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: object, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": _validation_detail(exc)})


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


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _safe_ext(filename: str | None) -> str:
    name = (filename or "image.png").strip().lower()
    ext = Path(name).suffix
    if ext not in ALLOWED_EXT:
        shown = ext or "no extension"
        label = (filename or "upload").strip() or "upload"
        raise HTTPException(
            status_code=400,
            detail=(
                f'"{label}" has {shown}, which is not supported. '
                "Upload a JPEG, PNG, or WebP image (max 12 MB)."
            ),
        )
    return ext


def _parse_color(value: str) -> tuple[int, int, int] | None:
    text = (value or "").strip()
    if not text:
        return None
    match = _HEX_COLOR_RE.fullmatch(text)
    if not match:
        raise HTTPException(
            status_code=400,
            detail=f'"{value}" is not a hex color. Use #rgb or #rrggbb, or leave it blank.',
        )
    hex_part = match.group(1)
    if len(hex_part) == 3:
        hex_part = "".join(ch * 2 for ch in hex_part)
    return tuple(int(hex_part[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _form_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text == "":
        return None
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise HTTPException(
        status_code=400,
        detail=f'"{value}" is not a yes/no value. Use 1 or 0 for invert and equalize.',
    )


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _resolve_params(preset: str, overrides: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Merge defaults, an optional named preset, then explicit overrides.

    A missing override (None) keeps the preset or default. Sent values win,
    which is how the form can start from a preset and then tweak one slider.
    """
    params = dict(EDIT_DEFAULTS)
    label = ""
    name = (preset or "").strip().lower()
    if name in {"", "custom", "none"}:
        name = ""
    elif name not in PRESETS:
        known = ", ".join(PRESETS)
        raise HTTPException(
            status_code=400,
            detail=f"Unknown preset '{preset}'. Known presets: {known}. Choose Custom to edit by hand.",
        )
    else:
        spec = PRESETS[name]
        params.update(spec["params"])
        label = str(spec["label"])

    for key, value in overrides.items():
        if value is not None:
            params[key] = value

    try:
        params["brightness"] = _clamp(float(params["brightness"]), 0.1, 3.0)
        params["contrast"] = _clamp(float(params["contrast"]), 0.1, 3.0)
        params["saturation"] = _clamp(float(params["saturation"]), 0.0, 3.0)
        params["sharpness"] = _clamp(float(params["sharpness"]), 0.0, 3.0)
        params["blur_radius"] = _clamp(float(params["blur_radius"]), 0.0, 30.0)
        params["rotate"] = float(params["rotate"]) % 360.0
        params["posterize"] = int(_clamp(int(params["posterize"]), 0, 8))
        params["solarize"] = int(_clamp(int(params["solarize"]), 0, 255))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Edit parameters must be numbers") from exc

    width = params.get("max_width")
    if width in (None, "", 0, "0"):
        params["max_width"] = None
    else:
        try:
            params["max_width"] = int(width)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail="Max width must be a whole number of pixels. Use 0 to keep the original width.",
            ) from exc
        if params["max_width"] <= 0:
            params["max_width"] = None
        else:
            params["max_width"] = min(params["max_width"], 8192)

    flip = _FLIP_ALIASES.get(str(params.get("flip") or "").strip().lower())
    if flip is None:
        raise HTTPException(
            status_code=400,
            detail="Flip must be none, horizontal, vertical, or both.",
        )
    params["flip"] = flip

    fname = str(params.get("filter") or "none").strip().lower()
    if fname not in _FILTERS:
        known = ", ".join(sorted(_FILTERS))
        raise HTTPException(
            status_code=400,
            detail=f"Unknown filter '{fname}'. Known filters: {known}.",
        )
    params["filter"] = fname

    params["invert"] = bool(params.get("invert"))
    params["equalize"] = bool(params.get("equalize"))
    params["colorize_black"] = str(params.get("colorize_black") or "").strip()
    params["colorize_white"] = str(params.get("colorize_white") or "").strip()
    # Validate colors early so a bad hex fails the request, not mid-pixel-loop.
    _parse_color(params["colorize_black"])
    _parse_color(params["colorize_white"])

    finish = str(params.get("finish") or "default").strip().lower()
    if finish not in {"default", "soft", "document", "none", "off", "edits"}:
        finish = "default"
    params["finish"] = finish

    crop = params.get("crop")
    params["crop"] = str(crop).strip() if crop else None
    return name, label, params


def _apply_crop(img: Image.Image, crop: str | None) -> Image.Image:
    if not crop:
        return img
    try:
        parts = [int(p.strip()) for p in crop.split(",")]
    except ValueError:
        return img
    if len(parts) != 4:
        return img
    x, y, w, h = parts
    x2, y2 = x + max(w, 1), y + max(h, 1)
    x, y = max(0, x), max(0, y)
    x2 = min(img.width, x2)
    y2 = min(img.height, y2)
    if x2 > x and y2 > y:
        return img.crop((x, y, x2, y2))
    return img


def _apply_rotate(img: Image.Image, degrees: float) -> Image.Image:
    deg = degrees % 360.0
    if deg < 1e-3:
        return img
    right = int(round(deg)) % 360
    if abs(deg - right) < 1e-3 and right in (90, 180, 270):
        # PIL transpose constants rotate counter-clockwise, matching Image.rotate.
        turns = {
            90: Image.Transpose.ROTATE_90,
            180: Image.Transpose.ROTATE_180,
            270: Image.Transpose.ROTATE_270,
        }
        return img.transpose(turns[right])
    return img.rotate(
        deg,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=(0, 0, 0),
    )


def _apply_flip(img: Image.Image, mode: str) -> Image.Image:
    if mode == "horizontal":
        return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if mode == "vertical":
        return img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if mode == "both":
        return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT).transpose(
            Image.Transpose.FLIP_TOP_BOTTOM
        )
    return img


def _apply_filter(img: Image.Image, name: str, blur_radius: float) -> Image.Image:
    if name == "grayscale":
        return ImageOps.grayscale(img).convert("RGB")
    if name == "blur":
        radius = blur_radius if blur_radius > 0 else 2.0
        return img.filter(ImageFilter.GaussianBlur(radius=radius))
    if name == "sharpen":
        return img.filter(ImageFilter.SHARPEN)
    if name == "edge":
        return img.filter(ImageFilter.FIND_EDGES).convert("RGB")
    if name == "contour":
        return img.filter(ImageFilter.CONTOUR).convert("RGB")
    if name == "emboss":
        return img.filter(ImageFilter.EMBOSS).convert("RGB")
    if name == "detail":
        return img.filter(ImageFilter.DETAIL)
    if name == "smooth":
        return img.filter(ImageFilter.SMOOTH_MORE)
    if name == "edge_enhance":
        return img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    return img


def _apply_edits(img: Image.Image, params: dict[str, Any]) -> Image.Image:
    """Geometry first, then tone, then the named filter.

    Order: crop → rotate → flip → max-width resize → brightness/contrast/
    saturation/sharpness → optional pre-filter blur → equalize → invert →
    posterize → solarize → colorize → named filter.
    """
    out = img.convert("RGB")
    out = _apply_crop(out, params.get("crop"))
    out = _apply_rotate(out, float(params["rotate"]))
    out = _apply_flip(out, str(params["flip"]))

    max_width = params.get("max_width")
    if max_width and out.width > int(max_width):
        ratio = int(max_width) / float(out.width)
        out = out.resize(
            (int(max_width), max(1, int(out.height * ratio))),
            Image.Resampling.LANCZOS,
        )

    if abs(float(params["brightness"]) - 1.0) > 1e-3:
        out = ImageEnhance.Brightness(out).enhance(float(params["brightness"]))
    if abs(float(params["contrast"]) - 1.0) > 1e-3:
        out = ImageEnhance.Contrast(out).enhance(float(params["contrast"]))
    if abs(float(params["saturation"]) - 1.0) > 1e-3:
        out = ImageEnhance.Color(out).enhance(float(params["saturation"]))
    if abs(float(params["sharpness"]) - 1.0) > 1e-3:
        out = ImageEnhance.Sharpness(out).enhance(float(params["sharpness"]))

    blur_radius = float(params["blur_radius"])
    # The blur *filter* consumes blur_radius itself (default 2px). An extra
    # radius applies only when the named filter is something else, so a soft
    # preset does not blur twice.
    if blur_radius > 0 and params["filter"] != "blur":
        out = out.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    if params["equalize"]:
        out = ImageOps.equalize(out)
    if params["invert"]:
        out = ImageOps.invert(out)
    if int(params["posterize"]) >= 1:
        out = ImageOps.posterize(out, int(params["posterize"]))
    if int(params["solarize"]) > 0:
        out = ImageOps.solarize(out, threshold=int(params["solarize"]))

    black = _parse_color(str(params["colorize_black"]))
    white = _parse_color(str(params["colorize_white"]))
    if black or white:
        out = ImageOps.colorize(
            out.convert("L"),
            black or (0, 0, 0),
            white or (255, 255, 255),
        ).convert("RGB")

    out = _apply_filter(out, str(params["filter"]), blur_radius)
    return out.convert("RGB")


def _cpu_generate(img: Image.Image, finish: str = "default") -> Image.Image:
    """CPU Pillow finish. No onnxruntime and no GPU.

    default — original stub: autocontrast + mild unsharp.
    document — stronger autocontrast and unsharp for scans.
    soft — light unsharp only, so a soft preset is not re-contrasted.
    none — edits only.
    """
    mode = (finish or "default").lower()
    if mode in {"none", "off", "edits"}:
        return img
    if mode == "soft":
        return img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=40, threshold=3))
    if mode == "document":
        out = ImageOps.autocontrast(img, cutoff=2)
        return out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=160, threshold=1))
    out = ImageOps.autocontrast(img, cutoff=1)
    return out.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=2))


def _find_upload(source_id: str) -> Path:
    if not _ID_RE.fullmatch(source_id):
        raise HTTPException(
            status_code=400,
            detail=(
                f'Invalid image id: "{source_id}". '
                "Upload an image first, or paste a 12-character id."
            ),
        )
    matches = sorted(UPLOADS.glob(f"{source_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail=f"Source image not found: {source_id}")
    return matches[0]


def _parse_id_list(source_id: str, source_ids: str) -> list[str]:
    raw: list[str] = []
    text = (source_ids or "").strip()
    if text:
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="Batch ids must be comma-separated upload ids, or a JSON array of ids.",
                ) from exc
            if not isinstance(parsed, list):
                raise HTTPException(status_code=400, detail="Batch ids JSON must be an array of upload ids.")
            raw.extend(str(item).strip() for item in parsed)
        else:
            raw.extend(part.strip() for part in text.replace("\n", ",").split(","))
    elif (source_id or "").strip():
        raw.append(source_id.strip())

    ids: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not item or item in seen:
            continue
        seen.add(item)
        ids.append(item)
    if not ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "Provide source_id or source_ids. "
                "Upload a JPEG, PNG, or WebP, or paste already-uploaded ids, then generate."
            ),
        )
    if len(ids) > MAX_BATCH:
        raise HTTPException(
            status_code=400,
            detail=f"Batch limit is {MAX_BATCH} images. Remove some ids and try again.",
        )
    return ids


def _store_upload(filename: str | None, data: bytes) -> dict[str, Any]:
    label = Path(filename or "image").name
    ext = _safe_ext(filename)
    if not data:
        raise HTTPException(
            status_code=400,
            detail=(
                f'Empty file: "{label}". '
                "Choose a JPEG, PNG, or WebP image that contains image data."
            ),
        )
    if len(data) > MAX_BYTES:
        if MAX_BYTES >= 1024 * 1024:
            limit = f"{MAX_BYTES / (1024 * 1024):.0f} MB"
            size_mb = len(data) / (1024 * 1024)
            shown = f"{size_mb:.1f} MB" if size_mb >= (MAX_BYTES / (1024 * 1024)) + 0.05 else f"just over {limit}"
        else:
            limit = f"{MAX_BYTES} bytes"
            shown = f"{len(data)} bytes"
        raise HTTPException(
            status_code=400,
            detail=(
                f'File too large: "{label}" is {shown}, over the {limit} limit. '
                "Choose a smaller JPEG, PNG, or WebP."
            ),
        )

    job_id = uuid.uuid4().hex[:12]
    dest = UPLOADS / f"{job_id}{ext}"
    dest.write_bytes(data)
    try:
        with Image.open(dest) as im:
            im.load()
            w, h = im.size
            fmt_name = (im.format or "").upper()
            if fmt_name == "MPO":
                fmt_name = "JPEG"
            if fmt_name not in {"JPEG", "PNG", "WEBP"}:
                dest.unlink(missing_ok=True)
                shown = fmt_name or "an unsupported format"
                raise HTTPException(
                    status_code=400,
                    detail=(
                    f'"{label}" is not a valid image. It decoded as {shown}. '
                    "Upload a JPEG, PNG, or WebP."
                ),
                )
            fmt = fmt_name
    except HTTPException:
        raise
    except (OSError, Image.DecompressionBombError) as exc:
        dest.unlink(missing_ok=True)
        detail = (
            f'"{label}" is not a valid image. '
            "It may be corrupt, or not a real JPEG, PNG, or WebP."
        )
        if isinstance(exc, Image.DecompressionBombError):
            detail = (
                f'"{label}" is too large to process safely. '
                "Resize it and upload a JPEG, PNG, or WebP under 12 MB."
            )
        raise HTTPException(status_code=400, detail=detail) from exc

    return {
        "id": job_id,
        "filename": dest.name,
        "url": f"/media/uploads/{dest.name}",
        "width": w,
        "height": h,
        "format": fmt,
        "label": "source",
    }


def _is_upload(item: object) -> bool:
    # FastAPI and Starlette have shipped distinct UploadFile types. Accept either.
    filename = getattr(item, "filename", None)
    return bool(filename) and callable(getattr(item, "read", None))


async def _uploads_from_request(request: Request) -> list[Any]:
    """Accept one `file`, repeated `file` parts, or repeated `files` parts."""
    form = await request.form()
    incoming: list[Any] = []
    for key in ("file", "files"):
        for item in form.getlist(key):
            if _is_upload(item):
                incoming.append(item)
    return incoming


def _process_one(
    source_id: str,
    params: dict[str, Any],
    preset_name: str,
    preset_label: str,
) -> dict[str, Any]:
    src_path = _find_upload(source_id)
    try:
        with Image.open(src_path) as im:
            im.load()
            edited = _apply_edits(im, params)
            result = _cpu_generate(edited, str(params.get("finish") or "default"))
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Could not process image {source_id}. "
                "Upload it again, or try a different JPEG, PNG, or WebP."
            ),
        ) from exc

    out_name = f"{source_id}_{uuid.uuid4().hex[:8]}.png"
    out_path = OUTPUTS / out_name
    result.save(out_path, format="PNG", optimize=True)

    label = "AI-assisted / transformed (CPU)"
    if preset_label:
        label = f"{label} · {preset_label}"
    return {
        "id": source_id,
        "created": _utc_now(),
        "before": f"/media/uploads/{src_path.name}",
        "after": f"/media/outputs/{out_name}",
        "label": label,
        "preset": preset_name or None,
        "params": params,
    }


def _preset_payload() -> dict[str, Any]:
    defaults = {key: EDIT_DEFAULTS[key] for key in _ADJUST_KEYS}
    presets = [
        {
            "id": key,
            "label": spec["label"],
            "description": spec["description"],
            "params": spec["params"],
        }
        for key, spec in PRESETS.items()
    ]
    return {"presets": presets, "defaults": defaults}


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/presets")
def presets() -> dict[str, Any]:
    return _preset_payload()


@app.post("/api/upload")
async def upload(request: Request) -> dict[str, Any]:
    incoming = await _uploads_from_request(request)
    if not incoming:
        raise HTTPException(
            status_code=400,
            detail=(
                "No files uploaded. "
                "Choose one or more JPEG, PNG, or WebP images (max 12 MB each)."
            ),
        )
    if len(incoming) > MAX_BATCH:
        raise HTTPException(
            status_code=400,
            detail=f"Batch limit is {MAX_BATCH} images. Choose fewer files and try again.",
        )

    stored: list[dict[str, Any]] = []
    try:
        for item in incoming:
            data = await item.read()
            stored.append(_store_upload(item.filename, data))
    except HTTPException:
        for entry in stored:
            (UPLOADS / entry["filename"]).unlink(missing_ok=True)
        raise

    payload: dict[str, Any] = {"items": stored, "count": len(stored)}
    if len(stored) == 1:
        payload.update(stored[0])
    return payload


@app.post("/api/generate")
async def generate(
    source_id: str = Form(""),
    source_ids: str = Form(""),
    preset: str = Form(""),
    crop: str | None = Form(None),
    max_width: int | None = Form(None),
    brightness: float | None = Form(None),
    contrast: float | None = Form(None),
    saturation: float | None = Form(None),
    sharpness: float | None = Form(None),
    rotate: float | None = Form(None),
    flip: str | None = Form(None),
    filter_name: Annotated[str | None, Form(alias="filter")] = None,
    posterize: int | None = Form(None),
    solarize: int | None = Form(None),
    invert: str | None = Form(None),
    equalize: str | None = Form(None),
    colorize_black: str | None = Form(None),
    colorize_white: str | None = Form(None),
    blur_radius: float | None = Form(None),
    finish: str | None = Form(None),
) -> dict[str, Any]:
    ids = _parse_id_list(source_id, source_ids)
    preset_name, preset_label, params = _resolve_params(
        preset,
        {
            "crop": _blank_to_none(crop),
            "max_width": max_width,
            "brightness": brightness,
            "contrast": contrast,
            "saturation": saturation,
            "sharpness": sharpness,
            "rotate": rotate,
            "flip": _blank_to_none(flip),
            "filter": _blank_to_none(filter_name),
            "posterize": posterize,
            "solarize": solarize,
            "invert": _form_bool(invert),
            "equalize": _form_bool(equalize),
            # Empty string is an explicit clear so a preset tint can be removed.
            "colorize_black": None if colorize_black is None else colorize_black.strip(),
            "colorize_white": None if colorize_white is None else colorize_white.strip(),
            "blur_radius": blur_radius,
            "finish": _blank_to_none(finish),
        },
    )

    entries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for sid in ids:
        try:
            entries.append(_process_one(sid, params, preset_name, preset_label))
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "Could not process image"
            errors.append({"id": sid, "detail": detail})

    if not entries:
        detail = errors[0]["detail"] if errors else "Could not process images"
        raise HTTPException(status_code=400, detail=detail)

    gallery = _load_gallery()
    for entry in reversed(entries):
        gallery.insert(0, entry)
    _save_gallery(gallery)

    payload: dict[str, Any] = {"items": entries, "count": len(entries), "errors": errors}
    if len(entries) == 1:
        payload.update(entries[0])
    return payload


@app.get("/api/gallery")
def gallery() -> dict[str, Any]:
    return {"items": _load_gallery()}


@app.get("/media/uploads/{name}")
def media_upload(name: str) -> FileResponse:
    path = UPLOADS / Path(name).name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="That uploaded image was not found.")
    return FileResponse(path)


@app.get("/media/outputs/{name}")
def media_output(name: str) -> FileResponse:
    path = OUTPUTS / Path(name).name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="That result image was not found.")
    return FileResponse(path)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "compute": "cpu"}
