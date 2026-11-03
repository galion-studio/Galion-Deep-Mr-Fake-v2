"""HTTP tests for upload validation, generate, presets, batch, gallery, and health."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from images import image_bytes

REPO_OUTPUTS = Path(__file__).resolve().parents[1] / "outputs"
REPO_UPLOADS = Path(__file__).resolve().parents[1] / "uploads"


def _upload(client, name: str = "tiny.png", content: bytes | None = None, content_type: str = "image/png"):
    payload = image_bytes("PNG") if content is None else content
    return client.post("/api/upload", files={"file": (name, payload, content_type)})


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "compute": "cpu"}


def test_index_serves_html(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert "I have rights/consent to process this image" in html
    marker = 'name="consent_attested"'
    assert marker in html
    tag_start = html.rfind("<input", 0, html.index(marker))
    tag = html[tag_start : html.index(">", tag_start) + 1]
    assert "checked" not in tag


def test_gallery_empty(client) -> None:
    response = client.get("/api/gallery")
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_gallery_missing_or_corrupt_index_reads_as_empty(app_module) -> None:
    assert app_module._load_gallery() == []
    app_module.GALLERY_INDEX.write_text("{not json", encoding="utf-8")
    assert app_module._load_gallery() == []


def test_gallery_index_keeps_latest_fifty(app_module) -> None:
    app_module._save_gallery([{"id": str(i)} for i in range(60)])
    loaded = app_module._load_gallery()
    assert [item["id"] for item in loaded] == [str(i) for i in range(50)]


@pytest.mark.parametrize(
    ("filename", "fmt", "content_type"),
    [
        ("photo.png", "PNG", "image/png"),
        ("PHOTO.PNG", "PNG", "image/png"),
        ("photo.jpg", "JPEG", "image/jpeg"),
        ("photo.jpeg", "JPEG", "image/jpeg"),
        ("photo.webp", "WEBP", "image/webp"),
    ],
)
def test_upload_accepts_allowed_types(client, app_module, filename: str, fmt: str, content_type: str) -> None:
    response = _upload(client, name=filename, content=image_bytes(fmt, (18, 9), (1, 2, 3)), content_type=content_type)
    assert response.status_code == 200
    body = response.json()
    assert len(body["id"]) == 12
    assert body["width"] == 18
    assert body["height"] == 9
    assert body["format"]
    assert body["label"] == "source"
    assert body["filename"].endswith(Path(filename).suffix.lower())
    assert body["url"] == f"/media/uploads/{body['filename']}"
    saved = app_module.UPLOADS / body["filename"]
    assert saved.is_file()
    served = client.get(body["url"])
    assert served.status_code == 200
    assert served.content == saved.read_bytes()


@pytest.mark.parametrize("filename", ["notes.txt", "anim.gif", "image", "image.bmp"])
def test_upload_rejects_disallowed_extension(client, filename: str) -> None:
    response = _upload(client, name=filename, content=b"not-an-image", content_type="application/octet-stream")
    assert response.status_code == 400
    assert "jpeg" in response.json()["detail"].lower()


def test_upload_rejects_empty_file(client) -> None:
    response = _upload(client, name="empty.png", content=b"")
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Empty file")


def test_upload_rejects_oversize_file(client, app_module, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "MAX_BYTES", 32)
    response = _upload(client, name="big.png", content=b"x" * 33)
    assert response.status_code == 400
    assert "too large" in response.json()["detail"].lower()
    assert list(app_module.UPLOADS.iterdir()) == []


def test_upload_rejects_invalid_image_bytes(client, app_module) -> None:
    response = _upload(client, name="bad.png", content=b"this is not a png")
    assert response.status_code == 400
    assert "not a valid image" in response.json()["detail"].lower()
    assert list(app_module.UPLOADS.iterdir()) == []


def test_generate_happy_path_updates_gallery_and_media(client, app_module) -> None:
    uploaded = _upload(client, content=image_bytes("PNG", (40, 30), (20, 80, 140)))
    assert uploaded.status_code == 200
    source_id = uploaded.json()["id"]

    response = client.post(
        "/api/generate",
        data={
            "source_id": source_id,
            "crop": "4,2,20,16",
            "max_width": "10",
            "brightness": "1.4",
            "contrast": "1.2",
            "filter": "sharpen",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == source_id
    assert body["count"] == 1
    assert body["errors"] == []
    assert body["preset"] is None
    assert body["label"] == "AI-assisted / transformed (CPU)"
    assert body["before"] == f"/media/uploads/{uploaded.json()['filename']}"
    assert body["after"].startswith(f"/media/outputs/{source_id}_")
    assert body["after"].endswith(".png")
    assert body["items"][0]["after"] == body["after"]
    assert body["params"]["crop"] == "4,2,20,16"
    assert body["params"]["max_width"] == 10
    assert body["params"]["brightness"] == 1.4
    assert body["params"]["contrast"] == 1.2
    assert body["params"]["filter"] == "sharpen"
    assert body["params"]["finish"] == "default"
    assert "created" in body

    out_path = app_module.OUTPUTS / body["after"].rsplit("/", 1)[-1]
    assert out_path.is_file()
    with Image.open(out_path) as result:
        assert result.format == "PNG"
        assert result.size == (10, 8)

    media = client.get(body["after"])
    assert media.status_code == 200
    assert media.content.startswith(b"\x89PNG\r\n\x1a\n")
    original = client.get(body["before"])
    assert original.status_code == 200

    gallery = client.get("/api/gallery")
    assert gallery.status_code == 200
    items = gallery.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == source_id
    assert items[0]["after"] == body["after"]

    assert not (REPO_OUTPUTS / "gallery.json").exists()
    assert not any(path.name != ".gitkeep" for path in REPO_UPLOADS.iterdir())
    assert not any(path.name != ".gitkeep" for path in REPO_OUTPUTS.iterdir())


def test_generate_defaults_keep_source_size(client) -> None:
    uploaded = _upload(client, content=image_bytes("PNG", (16, 11)))
    source_id = uploaded.json()["id"]
    response = client.post("/api/generate", data={"source_id": source_id})
    assert response.status_code == 200
    body = response.json()
    assert body["params"]["crop"] is None
    assert body["params"]["max_width"] is None
    assert body["params"]["brightness"] == 1.0
    assert body["params"]["contrast"] == 1.0
    assert body["params"]["filter"] == "none"

    media = client.get(body["after"])
    assert media.status_code == 200
    with Image.open(BytesIO(media.content)) as result:
        assert result.size == (16, 11)


def test_generate_rejects_bad_and_missing_sources(client) -> None:
    malformed = client.post("/api/generate", data={"source_id": "does-not-exist"})
    assert malformed.status_code == 400
    assert "invalid image id" in malformed.json()["detail"].lower()

    missing = client.post("/api/generate", data={"source_id": "abc123abc123"})
    assert missing.status_code == 400
    assert "not found" in missing.json()["detail"].lower()


def test_generate_requires_a_source(client) -> None:
    response = client.post("/api/generate", data={})
    assert response.status_code == 400
    assert "source_id" in response.json()["detail"].lower()


def test_generate_prepends_newest_gallery_item(client) -> None:
    first = _upload(client, content=image_bytes("PNG", (8, 8), (10, 10, 10))).json()["id"]
    second = _upload(client, content=image_bytes("PNG", (8, 8), (20, 20, 20))).json()["id"]
    assert client.post("/api/generate", data={"source_id": first}).status_code == 200
    assert client.post("/api/generate", data={"source_id": second, "filter": "grayscale"}).status_code == 200
    items = client.get("/api/gallery").json()["items"]
    assert [item["id"] for item in items] == [second, first]
    assert items[0]["params"]["filter"] == "grayscale"


def test_media_missing_is_404(client) -> None:
    assert client.get("/media/uploads/missing.png").status_code == 404
    assert client.get("/media/outputs/missing.png").status_code == 404


def test_media_path_does_not_escape_storage_dir(client) -> None:
    response = client.get("/media/uploads/..%2F..%2FREADME.md")
    assert response.status_code == 404
    assert b"Galion" not in response.content


def test_presets_lists_named_bundles(client) -> None:
    response = client.get("/api/presets")
    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["presets"]}
    assert {
        "document",
        "soft-portrait",
        "high-contrast",
        "mono",
        "duotone",
        "poster",
        "solar",
        "negative",
    } <= ids
    assert "brightness" in body["defaults"]
    assert "filter" in body["defaults"]


def test_generate_preset_and_field_override(client) -> None:
    source_id = _upload(client, content=image_bytes("PNG", (12, 12), (40, 90, 140))).json()["id"]
    response = client.post(
        "/api/generate",
        data={"source_id": source_id, "preset": "document", "contrast": "1.2"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["preset"] == "document"
    assert "Document" in body["label"]
    assert body["params"]["filter"] == "grayscale"
    assert body["params"]["equalize"] is True
    assert body["params"]["finish"] == "document"
    assert body["params"]["contrast"] == 1.2

    unknown = client.post("/api/generate", data={"source_id": source_id, "preset": "nope"})
    assert unknown.status_code == 400
    assert "unknown preset" in unknown.json()["detail"].lower()

    bad_filter = client.post("/api/generate", data={"source_id": source_id, "filter": "sepia"})
    assert bad_filter.status_code == 400
    assert "unknown filter" in bad_filter.json()["detail"].lower()


def test_generate_rotate_changes_output_size(client) -> None:
    source_id = _upload(client, content=image_bytes("PNG", (20, 10))).json()["id"]
    response = client.post("/api/generate", data={"source_id": source_id, "rotate": "90", "finish": "none"})
    assert response.status_code == 200
    body = response.json()
    assert body["params"]["rotate"] == 90.0
    assert body["params"]["finish"] == "none"
    with Image.open(BytesIO(client.get(body["after"]).content)) as result:
        assert result.size == (10, 20)


def test_upload_batch_and_generate_batch(client, app_module) -> None:
    uploaded = client.post(
        "/api/upload",
        files=[
            ("files", ("a.png", image_bytes("PNG", (8, 8), (10, 20, 30)), "image/png")),
            ("files", ("b.jpg", image_bytes("JPEG", (9, 7), (40, 50, 60)), "image/jpeg")),
        ],
    )
    assert uploaded.status_code == 200
    body = uploaded.json()
    assert body["count"] == 2
    assert "id" not in body
    ids = [item["id"] for item in body["items"]]

    generated = client.post(
        "/api/generate",
        data={"source_ids": f"{ids[0]}, {ids[1]}", "preset": "negative"},
    )
    assert generated.status_code == 200
    result = generated.json()
    assert result["count"] == 2
    assert result["errors"] == []
    assert [item["id"] for item in result["items"]] == ids
    assert "id" not in result
    assert all(item["preset"] == "negative" and item["params"]["invert"] is True for item in result["items"])
    for item in result["items"]:
        assert (app_module.OUTPUTS / item["after"].rsplit("/", 1)[-1]).is_file()

    gallery = client.get("/api/gallery").json()["items"]
    assert [item["id"] for item in gallery] == ids

    as_json = client.post(
        "/api/generate",
        data={"source_ids": json.dumps(list(reversed(ids))), "finish": "none"},
    )
    assert as_json.status_code == 200
    assert [item["id"] for item in as_json.json()["items"]] == list(reversed(ids))


def test_generate_batch_reports_partial_errors(client) -> None:
    source_id = _upload(client).json()["id"]
    response = client.post(
        "/api/generate",
        data={"source_ids": f"{source_id},deadbeefdead", "finish": "soft"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["id"] == source_id
    assert body["items"][0]["params"]["finish"] == "soft"
    assert body["errors"] == [{"id": "deadbeefdead", "detail": "Source image not found: deadbeefdead"}]


def _sidecar(client, item: dict) -> dict:
    response = client.get(item["meta"])
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    return response.json()


def test_generate_consent_sidecar_covers_each_batch_output(client, app_module) -> None:
    uploaded = client.post(
        "/api/upload",
        files=[
            ("files", ("a.png", image_bytes("PNG", (12, 8), (10, 20, 30)), "image/png")),
            ("files", ("b.png", image_bytes("PNG", (10, 10), (40, 50, 60)), "image/png")),
        ],
    )
    assert uploaded.status_code == 200
    ids = [item["id"] for item in uploaded.json()["items"]]

    omitted = client.post("/api/generate", data={"source_ids": ",".join(ids), "preset": "mono"})
    assert omitted.status_code == 200
    omitted_body = omitted.json()
    assert omitted_body["count"] == 2
    assert "id" not in omitted_body
    stems = set()
    for item in omitted_body["items"]:
        assert item["ai_generated"] is True
        assert item["consent_attested"] is False
        assert item["timestamp"]
        assert item["label"].startswith("AI-assisted / transformed (CPU)")
        doc = _sidecar(client, item)
        assert doc["id"] == item["id"]
        assert doc["label"] == "AI-assisted / transformed (CPU)"
        assert doc["consent_attested"] is False
        assert doc["ai_generated"] is True
        assert doc["timestamp"] == item["timestamp"]
        assert doc["params"] == item["params"]
        assert doc["preset"] == "mono"
        png_name = item["after"].rsplit("/", 1)[-1]
        meta_name = item["meta"].rsplit("/", 1)[-1]
        assert png_name == doc["output"]
        assert meta_name == png_name.replace(".png", ".meta.json")
        assert (app_module.OUTPUTS / meta_name).is_file()
        stems.add(meta_name)
    assert len(stems) == 2

    gallery = client.get("/api/gallery").json()["items"]
    assert [item["id"] for item in gallery] == ids
    assert all(
        item["ai_generated"] is True and item["consent_attested"] is False for item in gallery
    )

    attested = client.post(
        "/api/generate",
        data={"source_id": ids[0], "consent_attested": "true", "finish": "none"},
    )
    assert attested.status_code == 200
    attested_body = attested.json()
    assert attested_body["count"] == 1
    assert attested_body["consent_attested"] is True
    assert attested_body["ai_generated"] is True
    assert attested_body["items"][0]["consent_attested"] is True
    assert _sidecar(client, attested_body)["consent_attested"] is True

    for flag in ("false", "0", "off", "no"):
        response = client.post(
            "/api/generate",
            data={"source_id": ids[1], "consent_attested": flag, "finish": "none"},
        )
        assert response.status_code == 200
        assert response.json()["consent_attested"] is False

    invalid = client.post(
        "/api/generate",
        data={"source_id": ids[0], "consent_attested": "maybe"},
    )
    assert invalid.status_code == 400

    before = {path.name for path in app_module.OUTPUTS.iterdir()}
    mixed = client.post(
        "/api/generate",
        data={"source_ids": f"{ids[0]},deadbeefdead", "consent_attested": "yes"},
    )
    assert mixed.status_code == 200
    mixed_body = mixed.json()
    assert mixed_body["count"] == 1
    assert mixed_body["items"][0]["consent_attested"] is True
    assert mixed_body["errors"][0]["id"] == "deadbeefdead"
    assert _sidecar(client, mixed_body["items"][0])["consent_attested"] is True
    created = {path.name for path in app_module.OUTPUTS.iterdir()} - before
    assert any(name.endswith(".meta.json") for name in created)
    assert not any("deadbeefdead" in name for name in created)


def test_upload_batch_rolls_back_when_one_file_is_invalid(client, app_module) -> None:
    response = client.post(
        "/api/upload",
        files=[
            ("files", ("ok.png", image_bytes(), "image/png")),
            ("files", ("bad.png", b"not-an-image", "image/png")),
        ],
    )
    assert response.status_code == 400
    assert "not a valid image" in response.json()["detail"].lower()
    assert list(app_module.UPLOADS.iterdir()) == []


def test_upload_rejects_empty_request_and_over_batch_limit(client, app_module, monkeypatch) -> None:
    empty = client.post("/api/upload")
    assert empty.status_code == 400
    assert "no files" in empty.json()["detail"].lower()

    monkeypatch.setattr(app_module, "MAX_BATCH", 1)
    too_many = client.post(
        "/api/upload",
        files=[
            ("file", ("a.png", image_bytes("PNG", (4, 4)), "image/png")),
            ("file", ("b.png", image_bytes("PNG", (4, 4), (1, 2, 3)), "image/png")),
        ],
    )
    assert too_many.status_code == 400
    assert "batch limit" in too_many.json()["detail"].lower()
    assert list(app_module.UPLOADS.iterdir()) == []
