"""Local vector index for consented image-job metadata.

Files stay under ``web/data/vectors/``. Nothing is sent to a vector SaaS,
an embedding API, or a model host. The vector is a deterministic local
feature hash of the label, preset, edit params, and an optional descriptor.
It is not a face embedding and it does not read pixels.

The Phase-1 sidecar remains the provenance record. This index does not copy
``client_ip`` and it refuses fingerprint, cookie, geolocation, ISP, timezone,
user-agent, EXIF, and telemetry fields.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_WEB = Path(__file__).resolve().parent
DIM = 256
MAX_RECORDS = 200
MAX_DESCRIPTOR = 500
EMBED_ID = "local-hash-v1"
_LOCK_WAIT_S = 5.0

_SESSION_RE = re.compile(r"^[a-f0-9]{32}$")
_SOURCE_RE = re.compile(r"^[a-f0-9]{12}$")
_RECORD_RE = re.compile(r"^[a-f0-9]{12}_[a-f0-9]{8}$")
_OUTPUT_RE = re.compile(r"^[a-f0-9]{12}_[a-f0-9]{8}\.png$")
_CREATED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_PARAM_KEY_RE = re.compile(r"^[a-z_]{1,32}$")

# Structured fields the index will not accept. Free-text descriptors are not
# scanned for these words; the ban is on identity and telemetry columns.
FORBIDDEN_FIELDS = frozenset(
    {
        "fingerprint",
        "browser_fingerprint",
        "canvas_hash",
        "cookie",
        "cookies",
        "geolocation",
        "geo",
        "latitude",
        "longitude",
        "lat",
        "lon",
        "gps",
        "isp",
        "timezone",
        "time_zone",
        "tz",
        "user_agent",
        "useragent",
        "telemetry",
        "exif",
        "client_ip",
        "ip",
        "ip_address",
    }
)

ALLOWED_FIELDS = frozenset(
    {
        "record_id",
        "session_id",
        "created_at",
        "user_id",
        "consent_agreed",
        "consent_attested",
        "source_id",
        "output",
        "preset",
        "label",
        "ai_generated",
        "params",
        "descriptor",
        "width",
        "height",
    }
)


def _default_root() -> Path:
    override = os.environ.get("GDMF_VECTOR_ROOT")
    if override:
        return Path(override)
    return _WEB / "data" / "vectors"


VECTOR_ROOT = _default_root()


class PrivacyError(ValueError):
    """Raised when a write would store a field this index does not keep."""


def _field_name(key: object) -> str:
    return str(key).strip().lower().replace("-", "_")


def reject_invasive(value: object) -> None:
    """Walk structured input and refuse invasive field names."""
    if isinstance(value, dict):
        for key, item in value.items():
            if _field_name(key) in FORBIDDEN_FIELDS:
                raise PrivacyError(f"Refusing field '{key}'. It is not collected.")
            reject_invasive(item)
    elif isinstance(value, list):
        for item in value:
            reject_invasive(item)


def validate_descriptor(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise PrivacyError("descriptor must be a string")
    text = " ".join(value.split())
    if len(text) > MAX_DESCRIPTOR:
        raise PrivacyError(f"descriptor must be at most {MAX_DESCRIPTOR} characters")
    return text


def embed_text(text: str) -> list[float]:
    """Local feature hash. Same text always yields the same unit vector.

    Character trigrams are bucketed with SHA-256. No model file is loaded
    and no socket is opened.
    """
    buckets = [0.0] * DIM
    folded = " ".join((text or "").lower().split())
    if not folded:
        return buckets
    tokens: list[tuple[str, float]] = [(word, 3.0) for word in folded.split(" ") if word]
    padded = f"  {folded}  "
    tokens.extend((padded[index : index + 3], 1.0) for index in range(len(padded) - 2))
    for token, weight in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        slot = int.from_bytes(digest[:4], "big") % DIM
        sign = 1.0 if digest[4] & 1 else -1.0
        buckets[slot] += sign * weight
    norm = math.sqrt(sum(value * value for value in buckets))
    if norm == 0.0:
        return buckets
    return [value / norm for value in buckets]


def _embed_source(record: dict[str, Any]) -> str:
    parts = [
        str(record.get("label") or ""),
        str(record.get("preset") or ""),
        str(record.get("descriptor") or ""),
        json.dumps(record.get("params") or {}, sort_keys=True, ensure_ascii=False),
    ]
    return "\n".join(parts)


def _round_embedding(vector: list[float]) -> list[float]:
    return [round(value, 6) for value in vector]


def _clean_params(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise PrivacyError("params must be an object")
    if len(value) > 40:
        raise PrivacyError("params has too many fields")
    clean: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not _PARAM_KEY_RE.fullmatch(key):
            raise PrivacyError(f"Refusing param '{key}'")
        if _field_name(key) in FORBIDDEN_FIELDS:
            raise PrivacyError(f"Refusing field '{key}'. It is not collected.")
        if isinstance(item, bool) or item is None or isinstance(item, (int, str)):
            if isinstance(item, str) and len(item) > 256:
                raise PrivacyError(f"param '{key}' is too long")
            clean[key] = item
            continue
        if isinstance(item, float):
            if not math.isfinite(item):
                raise PrivacyError(f"param '{key}' must be a finite number")
            clean[key] = item
            continue
        raise PrivacyError(f"param '{key}' must be a plain value")
    return clean


def _optional_size(value: object, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise PrivacyError(f"{name} must be a whole number of pixels")
    if value < 1 or value > 8192:
        raise PrivacyError(f"{name} is out of range")
    return value


def _prepare(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise PrivacyError("record must be an object")
    reject_invasive(record)
    unknown = set(record) - ALLOWED_FIELDS
    if unknown:
        names = ", ".join(sorted(str(name) for name in unknown))
        raise PrivacyError(f"Refusing fields that are not part of the local index: {names}")
    if record.get("consent_agreed") is not True:
        raise PrivacyError("Refusing to index a job without consent_agreed")

    session_id = record.get("session_id")
    if not isinstance(session_id, str) or not _SESSION_RE.fullmatch(session_id):
        raise PrivacyError("session_id must be a 32-character hex id")
    source_id = record.get("source_id")
    if not isinstance(source_id, str) or not _SOURCE_RE.fullmatch(source_id):
        raise PrivacyError("source_id must be a 12-character hex id")
    record_id = record.get("record_id")
    if not isinstance(record_id, str) or not _RECORD_RE.fullmatch(record_id):
        raise PrivacyError("record_id must be the output stem")
    output = record.get("output")
    if not isinstance(output, str) or not _OUTPUT_RE.fullmatch(output):
        raise PrivacyError("output must be the generated PNG filename")
    if Path(output).stem != record_id:
        raise PrivacyError("record_id must match the output filename")
    created_at = record.get("created_at")
    if not isinstance(created_at, str) or not _CREATED_RE.fullmatch(created_at):
        raise PrivacyError("created_at must be a UTC timestamp ending in Z")

    user_id = record.get("user_id", "anonymous")
    if user_id != "anonymous":
        raise PrivacyError("user_id stays anonymous")
    if record.get("ai_generated") is not True:
        raise PrivacyError("ai_generated must be true")

    preset = record.get("preset")
    if preset is not None and (not isinstance(preset, str) or len(preset) > 64):
        raise PrivacyError("preset must be a short string or null")
    label = record.get("label")
    if not isinstance(label, str) or not label.strip() or len(label) > 200:
        raise PrivacyError("label must be a short string")
    if not isinstance(record.get("consent_attested"), bool):
        raise PrivacyError("consent_attested must be a boolean")

    prepared: dict[str, Any] = {
        "record_id": record_id,
        "session_id": session_id,
        "created_at": created_at,
        "user_id": "anonymous",
        "consent_agreed": True,
        "consent_attested": record["consent_attested"],
        "source_id": source_id,
        "output": output,
        "preset": preset,
        "label": label,
        "ai_generated": True,
        "params": _clean_params(record.get("params")),
        "descriptor": validate_descriptor(record.get("descriptor")),
        "embed": EMBED_ID,
    }
    width = _optional_size(record.get("width"), "width")
    height = _optional_size(record.get("height"), "height")
    if width is not None:
        prepared["width"] = width
    if height is not None:
        prepared["height"] = height
    prepared["embedding"] = _round_embedding(embed_text(_embed_source(prepared)))
    return prepared


def _index_path(root: Path) -> Path:
    return root / "index.jsonl"


@contextmanager
def _file_lock(root: Path) -> Iterator[None]:
    """Exclusive lock across processes. A crash can leave ``.lock`` for a few seconds."""
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".lock"
    deadline = time.monotonic() + _LOCK_WAIT_S
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError("local vector index is busy") from None
            time.sleep(0.01)
    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def _read_rows(root: Path) -> list[dict[str, Any]]:
    path = _index_path(root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("embed") == EMBED_ID:
            rows.append(row)
    return rows


def _write_rows(root: Path, rows: list[dict[str, Any]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    target = _index_path(root)
    temporary = root / "index.jsonl.tmp"
    payload = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
        for row in rows
    )
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(target)


def _root(root: Path | None) -> Path:
    return root if root is not None else VECTOR_ROOT


def index_consented_job(record: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    """Insert or replace one consented job. Returns the stored record without the vector."""
    prepared = _prepare(record)
    directory = _root(root)
    with _file_lock(directory):
        rows = [
            row for row in _read_rows(directory) if row.get("record_id") != prepared["record_id"]
        ]
        rows.append(prepared)
        if len(rows) > MAX_RECORDS:
            rows = rows[-MAX_RECORDS:]
        _write_rows(directory, rows)
    return _public_row(prepared)


def search(
    query: str,
    *,
    session_id: str,
    limit: int = 5,
    root: Path | None = None,
) -> list[dict[str, Any]]:
    """Cosine search over one session's local records. Other sessions are skipped."""
    if not isinstance(session_id, str) or not _SESSION_RE.fullmatch(session_id):
        raise PrivacyError("session_id must be a 32-character hex id")
    text = " ".join((query or "").split())
    if not text:
        raise PrivacyError("query is required")
    if len(text) > MAX_DESCRIPTOR:
        raise PrivacyError(f"query must be at most {MAX_DESCRIPTOR} characters")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 20:
        raise PrivacyError("limit must be from 1 to 20")

    query_vector = embed_text(text)
    hits: list[tuple[float, dict[str, Any]]] = []
    for row in _read_rows(_root(root)):
        if row.get("session_id") != session_id:
            continue
        embedding = row.get("embedding")
        if not isinstance(embedding, list) or len(embedding) != DIM:
            continue
        score = float(sum(left * right for left, right in zip(query_vector, embedding)))
        if score <= 0.0:
            continue
        hits.append((score, row))
    hits.sort(key=lambda item: item[0], reverse=True)
    return [_public_row(row, score=round(score, 6)) for score, row in hits[:limit]]


def _public_row(row: dict[str, Any], *, score: float | None = None) -> dict[str, Any]:
    shown = {key: value for key, value in row.items() if key != "embedding"}
    if score is not None:
        shown["score"] = score
    return shown
