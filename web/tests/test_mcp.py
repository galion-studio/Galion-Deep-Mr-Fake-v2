"""MCP stdio and loopback HTTP. Consent gates image tools. No extra collection."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

import mcp_server
import vectors
from images import image_bytes

WEB_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = WEB_ROOT.parent
CTX = mcp_server.CallContext(transport="stdio", client_ip="local")


@pytest.fixture
def ready(app_module):
    mcp_server.reset_protocol()
    response = mcp_server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        },
        CTX,
    )
    assert response["result"]["protocolVersion"] == "2025-06-18"
    assert response["result"]["serverInfo"]["name"] == "galion-deep-mr-fake"
    assert "face-swap" in response["result"]["instructions"]
    return app_module


def _call(name: str, arguments: dict | None = None, msg_id: int = 2) -> dict:
    response = mcp_server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        },
        CTX,
    )
    assert response["id"] == msg_id
    assert "error" not in response
    return response["result"]


def _payload(result: dict) -> dict:
    return result["structuredContent"]


def test_tools_require_initialize() -> None:
    mcp_server.reset_protocol()
    response = mcp_server.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        CTX,
    )
    assert response["error"]["code"] == -32600


def test_tool_list_and_ungated_tools(ready) -> None:
    listed = mcp_server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, CTX)
    names = [tool["name"] for tool in listed["result"]["tools"]]
    assert names == [
        "health",
        "consent_status",
        "consent_agree",
        "presets",
        "upload",
        "generate",
        "gallery",
        "vector_search",
    ]
    health = _payload(_call("health"))
    assert health == {"status": "ok", "compute": "cpu", "transport": "stdio"}
    presets = _payload(_call("presets", msg_id=3))
    assert "document" in {item["id"] for item in presets["presets"]}
    assert presets == ready._preset_payload()
    assert (
        mcp_server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}, CTX)
        is None
    )


def test_image_tools_wait_for_consent(ready) -> None:
    unknown = "ab" * 16
    status = _payload(_call("consent_status", {"session_id": unknown}))
    assert status["consent_agreed"] is False
    assert unknown not in ready._SESSIONS

    for name, arguments in (
        ("upload", {"session_id": unknown, "filename": "a.png", "data_base64": "YQ=="}),
        ("generate", {"session_id": unknown, "source_id": "abc123abc123"}),
        ("gallery", {"session_id": unknown}),
        ("vector_search", {"session_id": unknown, "query": "scan"}),
    ):
        result = _call(name, arguments, msg_id=4)
        assert result["isError"] is True
        assert "consent" in _payload(result)["detail"].lower()
    assert list(ready.UPLOADS.iterdir()) == []
    assert list(ready.OUTPUTS.glob("*.png")) == []


def test_agent_can_agree_upload_generate_and_search(ready) -> None:
    agreed = _payload(_call("consent_agree"))
    session_id = agreed["session_id"]
    assert agreed["user_id"] == "anonymous"
    assert agreed["consent_agreed"] is True
    status = _payload(_call("consent_status", {"session_id": session_id}, msg_id=3))
    assert status["consent_agreed"] is True

    png = base64.b64encode(image_bytes("PNG", (16, 10), (20, 40, 60))).decode("ascii")
    uploaded = _payload(
        _call(
            "upload",
            {"session_id": session_id, "filename": "scan.png", "data_base64": png},
            msg_id=4,
        )
    )
    generated = _payload(
        _call(
            "generate",
            {
                "session_id": session_id,
                "source_id": uploaded["id"],
                "preset": "document",
                "consent_attested": True,
                "descriptor": "skan dokumentu żółty",
            },
            msg_id=5,
        )
    )
    assert generated["count"] == 1
    assert generated["ai_generated"] is True
    assert generated["consent_attested"] is True
    assert generated["descriptor"] == "skan dokumentu żółty"
    meta_name = Path(generated["meta"]).name
    sidecar = json.loads((ready.OUTPUTS / meta_name).read_text(encoding="utf-8"))
    assert sidecar["client_ip"] == "local"
    assert sidecar["user_id"] == "anonymous"
    assert sidecar["session_id"] == session_id
    assert "descriptor" not in sidecar
    assert "żółty" not in (ready.OUTPUTS / meta_name).read_text(encoding="utf-8")

    other = _payload(_call("consent_agree", msg_id=6))
    assert _payload(_call("gallery", {"session_id": other["session_id"]}, msg_id=7)) == {
        "items": []
    }
    own = _payload(_call("gallery", {"session_id": session_id}, msg_id=8))
    assert len(own["items"]) == 1
    assert own["items"][0]["id"] == uploaded["id"]

    hits = _payload(
        _call(
            "vector_search",
            {"session_id": session_id, "query": "dokument żółty"},
            msg_id=9,
        )
    )
    assert hits["items"][0]["record_id"] == generated["vector_record_id"]
    assert "embedding" not in hits["items"][0]
    missed = _payload(
        _call(
            "vector_search",
            {"session_id": other["session_id"], "query": "dokument"},
            msg_id=10,
        )
    )
    assert missed["items"] == []
    ready._SESSIONS.clear()
    blocked = _call("vector_search", {"session_id": session_id, "query": "dokument"}, msg_id=11)
    assert blocked["isError"] is True
    _call("consent_agree", {"session_id": session_id}, msg_id=12)
    revived = _payload(
        _call("vector_search", {"session_id": session_id, "query": "dokument"}, msg_id=13)
    )
    assert revived["items"][0]["record_id"] == generated["vector_record_id"]
    index_text = (vectors.VECTOR_ROOT / "index.jsonl").read_text(encoding="utf-8")
    assert "client_ip" not in index_text
    assert "skan dokumentu żółty" in index_text


def test_forbidden_argument_is_refused(ready) -> None:
    agreed = _payload(_call("consent_agree"))
    result = _call(
        "generate",
        {
            "session_id": agreed["session_id"],
            "source_id": "abc123abc123",
            "timezone": "Europe/Warsaw",
            "fingerprint": "nope",
        },
        msg_id=3,
    )
    assert result["isError"] is True
    assert "not collected" in _payload(result)["detail"].lower()
    assert list(ready.OUTPUTS.glob("*.png")) == []


def test_unknown_tool_is_a_jsonrpc_error(ready) -> None:
    del ready
    response = mcp_server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "face_swap", "arguments": {}},
        },
        CTX,
    )
    assert response["error"]["code"] == -32602


def test_loopback_host_refuses_public_binds() -> None:
    assert mcp_server.loopback_host("127.0.0.1") == "127.0.0.1"
    assert mcp_server.loopback_host("localhost") == "localhost"
    assert mcp_server.loopback_host("::1") == "::1"
    with pytest.raises(ValueError):
        mcp_server.loopback_host("0.0.0.0")
    with pytest.raises(ValueError):
        mcp_server.loopback_host("8.8.8.8")


@pytest.fixture
def mcp_http(app_module):
    del app_module
    httpd = mcp_server.make_server("127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _post(port: int, payload: dict, extra_headers: dict | None = None) -> tuple[int, dict, dict]:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if extra_headers:
        headers.update(extra_headers)
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request("POST", "/mcp", body=body, headers=headers)
    response = connection.getresponse()
    raw = response.read()
    parsed = json.loads(raw.decode("utf-8")) if raw else {}
    header_map = {key.lower(): value for key, value in response.getheaders()}
    connection.close()
    return response.status, parsed, header_map


def test_http_transport_gates_consent_and_ignores_forwarded_ip(ready, mcp_http) -> None:
    port = mcp_http.server_address[1]
    health = HTTPConnection("127.0.0.1", port, timeout=5)
    health.request("GET", "/health")
    health_response = health.getresponse()
    assert health_response.status == 200
    assert json.loads(health_response.read())["compute"] == "cpu"
    assert "set-cookie" not in {key.lower() for key, _value in health_response.getheaders()}
    health.close()

    missing = HTTPConnection("127.0.0.1", port, timeout=5)
    missing.request("GET", "/mcp")
    denied = missing.getresponse()
    assert denied.status == 405
    missing.close()

    status, body, headers = _post(
        port,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
        },
    )
    assert status == 200
    assert body["result"]["protocolVersion"] == "2024-11-05"
    assert "set-cookie" not in headers

    status, blocked, _headers = _post(
        port,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
        },
        {"Origin": "https://evil.example"},
    )
    assert status == 403
    assert "local" in blocked["detail"].lower()

    status, foreign, _headers = _post(
        port,
        {"jsonrpc": "2.0", "id": 2, "method": "ping"},
        {"Host": "evil.example"},
    )
    assert status == 403
    assert "local" in foreign["detail"].lower()

    status, agreed, _headers = _post(
        port,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "consent_agree", "arguments": {}},
        },
        {"X-Forwarded-For": "203.0.113.50", "X-Real-IP": "198.51.100.20"},
    )
    assert status == 200
    session_id = agreed["result"]["structuredContent"]["session_id"]
    png = base64.b64encode(image_bytes()).decode("ascii")
    status, uploaded, _headers = _post(
        port,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "upload",
                "arguments": {
                    "session_id": session_id,
                    "filename": "loop.png",
                    "data_base64": png,
                },
            },
        },
        {"X-Forwarded-For": "203.0.113.50"},
    )
    assert status == 200
    source_id = uploaded["result"]["structuredContent"]["id"]
    status, generated, _headers = _post(
        port,
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "generate",
                "arguments": {
                    "session_id": session_id,
                    "source_id": source_id,
                    "finish": "none",
                    "descriptor": "loopback page",
                },
            },
        },
        {"X-Forwarded-For": "203.0.113.50"},
    )
    assert status == 200
    assert generated["result"]["isError"] is False
    payload = generated["result"]["structuredContent"]
    assert payload["count"] == 1
    meta_name = Path(payload["meta"]).name
    sidecar = json.loads((ready.OUTPUTS / meta_name).read_text(encoding="utf-8"))
    assert sidecar["client_ip"] == "127.0.0.1"
    assert "203.0.113.50" not in json.dumps(sidecar)


def test_http_sse_accept_returns_one_event(mcp_http) -> None:
    port = mcp_http.server_address[1]
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
        }
    ).encode("utf-8")
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(
        "POST",
        "/mcp",
        body=body,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    response = connection.getresponse()
    raw = response.read().decode("utf-8")
    assert response.status == 200
    assert response.getheader("Content-Type") == "text/event-stream"
    assert raw.startswith("event: message\ndata: ")
    parsed = json.loads(raw.split("data: ", 1)[1].strip())
    assert parsed["result"]["serverInfo"]["name"] == "galion-deep-mr-fake"
    connection.close()


def test_stdio_process_roundtrip(tmp_path) -> None:
    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    vector_dir = tmp_path / "vectors"
    env = os.environ.copy()
    env.update(
        {
            "GDMF_UPLOADS": str(uploads),
            "GDMF_OUTPUTS": str(outputs),
            "GDMF_VECTOR_ROOT": str(vector_dir),
            "PYTHONUNBUFFERED": "1",
        }
    )
    err_path = tmp_path / "stderr.txt"
    err_file = err_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(WEB_ROOT / "mcp_server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=err_file,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    def send(message: dict) -> None:
        proc.stdin.write(json.dumps(message).encode("utf-8") + b"\n")
        proc.stdin.flush()

    def read() -> dict:
        holder: dict[str, bytes] = {}

        def _read() -> None:
            holder["line"] = proc.stdout.readline()

        thread = threading.Thread(target=_read)
        thread.start()
        thread.join(timeout=15)
        if thread.is_alive():
            proc.kill()
            err_file.close()
            raise AssertionError(err_path.read_text(encoding="utf-8"))
        line = holder.get("line") or b""
        assert line, err_path.read_text(encoding="utf-8")
        return json.loads(line.decode("utf-8"))

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
            }
        )
        initial = read()
        assert initial["result"]["serverInfo"]["version"]
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "health", "arguments": {}},
            }
        )
        health = read()
        assert health["result"]["structuredContent"]["transport"] == "stdio"
        send(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "consent_agree", "arguments": {}},
            }
        )
        agreed = read()["result"]["structuredContent"]
        png = base64.b64encode(image_bytes("PNG", (8, 8))).decode("ascii")
        send(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "upload",
                    "arguments": {
                        "session_id": agreed["session_id"],
                        "filename": "stdio.png",
                        "data_base64": png,
                    },
                },
            }
        )
        uploaded = read()["result"]["structuredContent"]
        send(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "generate",
                    "arguments": {
                        "session_id": agreed["session_id"],
                        "source_id": uploaded["id"],
                        "descriptor": "stdio scan",
                        "finish": "none",
                    },
                },
            }
        )
        generated = read()["result"]["structuredContent"]
        assert generated["count"] == 1
        meta = next(outputs.glob("*.meta.json"))
        sidecar = json.loads(meta.read_text(encoding="utf-8"))
        assert sidecar["client_ip"] == "local"
        assert sidecar["user_id"] == "anonymous"
        index = (vector_dir / "index.jsonl").read_text(encoding="utf-8")
        assert "stdio scan" in index
        assert "client_ip" not in index
        assert not any(path.name != ".gitkeep" for path in (WEB_ROOT / "uploads").iterdir())
        assert not any(path.name != ".gitkeep" for path in (WEB_ROOT / "outputs").iterdir())
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        err_file.close()
