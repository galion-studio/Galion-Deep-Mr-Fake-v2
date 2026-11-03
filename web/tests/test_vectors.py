"""Local vector index: consented metadata only, no network, no extra identity fields."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import vectors
from images import image_bytes

SIDECAR_KEYS = {
    "id",
    "output",
    "timestamp",
    "created_at",
    "params",
    "label",
    "consent_attested",
    "consent_agreed",
    "ai_generated",
    "preset",
    "session_id",
    "client_ip",
    "user_id",
    "user_label",
    "responsibility",
}


def _job(n: int = 1, **overrides):
    source = f"{n:012x}"
    suffix = f"{n:08x}"
    record = {
        "record_id": f"{source}_{suffix}",
        "session_id": "a" * 32,
        "created_at": "2026-11-03T10:41:00Z",
        "user_id": "anonymous",
        "consent_agreed": True,
        "consent_attested": True,
        "source_id": source,
        "output": f"{source}_{suffix}.png",
        "preset": "document",
        "label": "AI-assisted / transformed (CPU)",
        "ai_generated": True,
        "params": {"finish": "document", "filter": "grayscale", "brightness": 1.1},
        "descriptor": "skan dokumentu żółty",
        "width": 8,
        "height": 6,
    }
    record.update(overrides)
    return record


@pytest.fixture
def index_root(tmp_path, monkeypatch):
    monkeypatch.setattr(vectors, "VECTOR_ROOT", tmp_path)
    return tmp_path


def test_embed_text_is_local_and_deterministic() -> None:
    first = vectors.embed_text("skan dokumentu")
    second = vectors.embed_text("skan dokumentu")
    other = vectors.embed_text("blue ceramic tile")
    assert len(first) == vectors.DIM
    assert first == second
    assert first != other
    assert abs(sum(value * value for value in first) - 1.0) < 1e-6
    assert vectors.embed_text("   ") == [0.0] * vectors.DIM


def test_index_writes_consented_metadata_only(index_root) -> None:
    stored = vectors.index_consented_job(_job())
    assert stored["embed"] == "local-hash-v1"
    assert stored["user_id"] == "anonymous"
    assert "embedding" not in stored
    assert "client_ip" not in stored
    path = index_root / "index.jsonl"
    text = path.read_text(encoding="utf-8")
    assert "skan dokumentu żółty" in text
    assert "client_ip" not in text
    assert "fingerprint" not in text
    row = json.loads(text)
    assert len(row["embedding"]) == vectors.DIM
    assert not (index_root / ".lock").exists()


@pytest.mark.parametrize(
    "extra",
    [
        {"client_ip": "203.0.113.8"},
        {"fingerprint": "abc"},
        {"timezone": "Europe/Warsaw"},
        {"geolocation": {"lat": 52.2, "lon": 21.0}},
        {"cookie": "gdmf_session=secret"},
        {"isp": "Example ISP"},
        {"user_agent": "Mozilla/5.0"},
        {"telemetry": {"event": "view"}},
        {"exif": {"GPSLatitude": "52"}},
    ],
)
def test_refuses_invasive_fields(index_root, extra) -> None:
    with pytest.raises(vectors.PrivacyError):
        vectors.index_consented_job(_job(**extra))
    assert list(index_root.iterdir()) == []


def test_refuses_nested_timezone_and_non_anonymous_user(index_root) -> None:
    with pytest.raises(vectors.PrivacyError):
        vectors.index_consented_job(_job(params={"timezone": "UTC"}))
    with pytest.raises(vectors.PrivacyError):
        vectors.index_consented_job(_job(user_id="maciej"))
    with pytest.raises(vectors.PrivacyError):
        vectors.index_consented_job(_job(consent_agreed=False))
    with pytest.raises(vectors.PrivacyError):
        vectors.index_consented_job(_job(created_at="2026-11-03T11:41:00+01:00"))
    assert list(index_root.iterdir()) == []


def test_search_is_limited_to_the_session(index_root) -> None:
    keep = vectors.index_consented_job(_job(1, descriptor="amber quartz scan"))
    vectors.index_consented_job(_job(2, session_id="b" * 32, descriptor="amber quartz scan"))
    vectors.index_consented_job(_job(3, descriptor="blue ceramic tile"))
    hits = vectors.search("amber quartz", session_id="a" * 32)
    assert [hit["record_id"] for hit in hits] == [keep["record_id"]]
    assert "embedding" not in hits[0]
    assert hits[0]["score"] > 0
    assert vectors.search("amber quartz", session_id="b" * 32)[0]["record_id"].startswith(
        "000000000002_"
    )
    assert vectors.search("amber quartz", session_id="c" * 32) == []


def test_search_skips_a_corrupt_line(index_root) -> None:
    vectors.index_consented_job(_job())
    path = index_root / "index.jsonl"
    path.write_text("{not-json\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    hits = vectors.search("dokument", session_id="a" * 32)
    assert len(hits) == 1
    assert hits[0]["descriptor"] == "skan dokumentu żółty"


def test_index_keeps_the_newest_records(index_root, monkeypatch) -> None:
    monkeypatch.setattr(vectors, "MAX_RECORDS", 2)
    vectors.index_consented_job(_job(1, descriptor="first page"))
    vectors.index_consented_job(_job(2, descriptor="second page"))
    vectors.index_consented_job(_job(3, descriptor="third page"))
    rows = [json.loads(line) for line in (index_root / "index.jsonl").read_text().splitlines()]
    assert [row["descriptor"] for row in rows] == ["second page", "third page"]


def test_web_generate_indexes_without_changing_the_sidecar(client, app_module) -> None:
    agreed = client.post("/api/consent/agree").json()
    uploaded = client.post(
        "/api/upload",
        files={"file": ("page.png", image_bytes("PNG", (12, 8)), "image/png")},
    )
    source_id = uploaded.json()["id"]
    response = client.post(
        "/api/generate",
        data={"source_id": source_id, "preset": "mono", "consent_attested": "true"},
    )
    assert response.status_code == 200
    body = response.json()
    meta = client.get(body["meta"])
    sidecar = meta.json()
    assert set(sidecar) == SIDECAR_KEYS
    assert sidecar["client_ip"]
    assert sidecar["session_id"] == agreed["session_id"]
    assert sidecar["user_id"] == "anonymous"
    assert "descriptor" not in sidecar

    path = Path(vectors.VECTOR_ROOT) / "index.jsonl"
    text = path.read_text(encoding="utf-8")
    assert "client_ip" not in text
    assert agreed["session_id"] in text
    row = json.loads(text)
    assert row["consent_agreed"] is True
    assert row["consent_attested"] is True
    assert row["preset"] == "mono"
    assert row["descriptor"] == ""
    assert row["user_id"] == "anonymous"
    hits = vectors.search("mono", session_id=agreed["session_id"])
    assert hits[0]["source_id"] == source_id
    assert list(app_module.OUTPUTS.glob("*.meta.json"))


def test_unconsented_process_does_not_index(app_module) -> None:
    stored = app_module._store_upload("tiny.png", image_bytes())
    _name, _label, params = app_module._resolve_params("", {})
    app_module._process_one(
        stored["id"],
        params,
        "",
        "",
        consent_attested=False,
        session=None,
        client_ip="203.0.113.9",
    )
    assert not Path(vectors.VECTOR_ROOT).exists() or not any(Path(vectors.VECTOR_ROOT).glob("*"))
    sidecar = next(app_module.OUTPUTS.glob("*.meta.json"))
    document = json.loads(sidecar.read_text(encoding="utf-8"))
    assert document["consent_agreed"] is False
    assert document["client_ip"] == "203.0.113.9"
    assert set(document) == SIDECAR_KEYS
