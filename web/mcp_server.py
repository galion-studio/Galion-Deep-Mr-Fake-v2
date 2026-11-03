"""CPU MCP server for Galion Deep Mr Fake v2.

Speaks MCP JSON-RPC over stdio and over loopback HTTP (``POST /mcp``).
Tools drive the same consent, upload, and CPU generate path as the web UI.

This process does not open a connection to Galion One, Hermes Research, or
Galion Voice. Those products connect here as MCP clients when an operator
points them at the command or the loopback URL.

Stdout on stdio is protocol only. The server does not set cookies and does
not read forwarding headers, fingerprints, or client timezones.
"""

from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import sys
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

_WEB = Path(__file__).resolve().parent
if str(_WEB) not in sys.path:
    sys.path.insert(0, str(_WEB))

import app  # noqa: E402
import vectors  # noqa: E402

SERVER_NAME = "galion-deep-mr-fake"
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
MAX_BODY = 18 * 1024 * 1024
INSTRUCTIONS = (
    "Galion Deep Mr Fake v2 is a consent-first CPU image toolkit. "
    "It is not a face-swap product. "
    "Call consent_agree before upload, generate, gallery, or vector_search. "
    "user_id stays anonymous. "
    "Do not send fingerprints, cookies, geolocation, ISP, timezone, or telemetry. "
    "Images and the vector index stay on this machine."
)

_initialized = False


class ToolError(Exception):
    """A tool ran and refused the request. Returned as an MCP tool error."""


@dataclass(frozen=True)
class CallContext:
    transport: str
    client_ip: str


def reset_protocol() -> None:
    """Forget the MCP handshake. Consent sessions live on the app, not here."""
    global _initialized
    _initialized = False


def _rpc_result(msg_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _rpc_error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _tool_result(payload: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2) + "\n"}],
        "structuredContent": payload,
        "isError": is_error,
    }


def _object_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def _expect_keys(arguments: dict[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(arguments) - allowed)
    if unknown:
        raise ToolError("Unknown arguments: " + ", ".join(unknown))


def _require_session(arguments: dict[str, Any]) -> dict[str, Any]:
    session_id = arguments.get("session_id")
    if not isinstance(session_id, str) or not app._valid_sid(session_id):
        raise ToolError("session_id must be a 32-character hex id from consent_agree.")
    record = app._SESSIONS.get(session_id)
    if not record or not record.get("consent_agreed"):
        raise ToolError("Agree to the consent notice before this tool will run.")
    return record


def _decode_image(value: object) -> bytes:
    if not isinstance(value, str) or not value.strip():
        raise ToolError("data_base64 is required.")
    compact = "".join(value.split())
    max_chars = ((app.MAX_BYTES + 2) // 3) * 4 + 8
    if len(compact) > max_chars:
        limit = app.MAX_BYTES // (1024 * 1024)
        raise ToolError(f"File too large. Upload a JPEG, PNG, or WebP up to {limit} MB.")
    try:
        return base64.b64decode(compact, validate=True)
    except ValueError as exc:
        raise ToolError("data_base64 is not valid base64.") from exc


def _maybe_number(arguments: dict[str, Any], key: str) -> float | None:
    if key not in arguments or arguments[key] is None:
        return None
    value = arguments[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolError(f"{key} must be a number.")
    return float(value)


def _maybe_int(arguments: dict[str, Any], key: str) -> int | None:
    if key not in arguments or arguments[key] is None:
        return None
    value = arguments[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolError(f"{key} must be a whole number.")
    if isinstance(value, float) and not value.is_integer():
        raise ToolError(f"{key} must be a whole number.")
    return int(value)


def _maybe_str(arguments: dict[str, Any], key: str) -> str | None:
    if key not in arguments or arguments[key] is None:
        return None
    value = arguments[key]
    if not isinstance(value, str):
        raise ToolError(f"{key} must be a string.")
    return value


def _maybe_bool(arguments: dict[str, Any], key: str) -> bool | None:
    if key not in arguments or arguments[key] is None:
        return None
    value = arguments[key]
    if not isinstance(value, bool):
        raise ToolError(f"{key} must be a boolean.")
    return value


def tool_health(arguments: dict[str, Any], context: CallContext) -> dict[str, Any]:
    _expect_keys(arguments, set())
    return {"status": "ok", "compute": "cpu", "transport": context.transport}


def tool_consent_status(arguments: dict[str, Any], context: CallContext) -> dict[str, Any]:
    del context
    _expect_keys(arguments, {"session_id"})
    session_id = arguments.get("session_id")
    if session_id is None:
        return {"session_id": None, "consent_agreed": False, "user_id": "anonymous"}
    if not isinstance(session_id, str) or not app._valid_sid(session_id):
        raise ToolError("session_id must be a 32-character hex id.")
    record = app._SESSIONS.get(session_id)
    return {
        "session_id": session_id,
        "consent_agreed": bool(record and record.get("consent_agreed")),
        "user_id": "anonymous",
    }


def tool_consent_agree(arguments: dict[str, Any], context: CallContext) -> dict[str, Any]:
    del context
    _expect_keys(arguments, {"session_id"})
    session_id = arguments.get("session_id")
    if session_id is not None and (
        not isinstance(session_id, str) or not app._valid_sid(session_id)
    ):
        raise ToolError("session_id must be a 32-character hex id.")
    record = app.agree_session(session_id if isinstance(session_id, str) else None)
    return {
        "ok": True,
        "session_id": record["session_id"],
        "consent_agreed": True,
        "user_id": "anonymous",
    }


def tool_presets(arguments: dict[str, Any], context: CallContext) -> dict[str, Any]:
    del context
    _expect_keys(arguments, set())
    return app._preset_payload()


def tool_upload(arguments: dict[str, Any], context: CallContext) -> dict[str, Any]:
    del context
    _expect_keys(arguments, {"session_id", "filename", "data_base64"})
    _require_session(arguments)
    filename = arguments.get("filename")
    if not isinstance(filename, str) or not filename.strip():
        raise ToolError("filename is required.")
    return app._store_upload(filename, _decode_image(arguments.get("data_base64")))


def tool_generate(arguments: dict[str, Any], context: CallContext) -> dict[str, Any]:
    _expect_keys(
        arguments,
        {
            "session_id",
            "source_id",
            "source_ids",
            "preset",
            "crop",
            "max_width",
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
            "finish",
            "consent_attested",
            "descriptor",
        },
    )
    agreement = _require_session(arguments)
    descriptor = vectors.validate_descriptor(arguments.get("descriptor"))
    if "consent_attested" in arguments and not isinstance(arguments["consent_attested"], bool):
        raise ToolError("consent_attested must be a boolean.")
    attested = arguments.get("consent_attested") is True

    source_id = arguments.get("source_id") or ""
    source_ids = arguments.get("source_ids") or ""
    if isinstance(source_ids, list):
        if not all(isinstance(item, str) for item in source_ids):
            raise ToolError("source_ids must be strings.")
        source_ids = ",".join(source_ids)
    if not isinstance(source_id, str) or not isinstance(source_ids, str):
        raise ToolError("source_id and source_ids must be strings.")

    preset_name, preset_label, params = app._resolve_params(
        _maybe_str(arguments, "preset") or "",
        {
            "crop": _maybe_str(arguments, "crop"),
            "max_width": _maybe_int(arguments, "max_width"),
            "brightness": _maybe_number(arguments, "brightness"),
            "contrast": _maybe_number(arguments, "contrast"),
            "saturation": _maybe_number(arguments, "saturation"),
            "sharpness": _maybe_number(arguments, "sharpness"),
            "rotate": _maybe_number(arguments, "rotate"),
            "flip": _maybe_str(arguments, "flip"),
            "filter": _maybe_str(arguments, "filter"),
            "posterize": _maybe_int(arguments, "posterize"),
            "solarize": _maybe_int(arguments, "solarize"),
            "invert": _maybe_bool(arguments, "invert"),
            "equalize": _maybe_bool(arguments, "equalize"),
            "colorize_black": _maybe_str(arguments, "colorize_black"),
            "colorize_white": _maybe_str(arguments, "colorize_white"),
            "blur_radius": _maybe_number(arguments, "blur_radius"),
            "finish": _maybe_str(arguments, "finish"),
        },
    )
    ids = app._parse_id_list(source_id, source_ids)
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for source in ids:
        try:
            entries.append(
                app._process_one(
                    source,
                    params,
                    preset_name,
                    preset_label,
                    consent_attested=attested,
                    session=agreement,
                    client_ip=context.client_ip,
                    descriptor=descriptor,
                )
            )
        except app.HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "Could not process image"
            errors.append({"id": source, "detail": detail})
    if not entries:
        detail = errors[0]["detail"] if errors else "Could not process images"
        raise ToolError(detail)

    gallery = app._load_gallery()
    for entry in reversed(entries):
        gallery.insert(0, entry)
    app._save_gallery(gallery)

    shown: list[dict[str, Any]] = []
    for entry in entries:
        item = dict(entry)
        item["vector_record_id"] = Path(str(entry["after"])).name.removesuffix(".png")
        if descriptor:
            item["descriptor"] = descriptor
        shown.append(item)
    payload: dict[str, Any] = {"items": shown, "count": len(shown), "errors": errors}
    if len(shown) == 1:
        payload.update(shown[0])
    return payload


def tool_gallery(arguments: dict[str, Any], context: CallContext) -> dict[str, Any]:
    del context
    _expect_keys(arguments, {"session_id"})
    agreement = _require_session(arguments)
    session_id = agreement["session_id"]
    items: list[dict[str, Any]] = []
    for item in app._load_gallery():
        meta_name = Path(str(item.get("meta") or "")).name
        if not meta_name.endswith(".meta.json"):
            continue
        path = app.OUTPUTS / meta_name
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(document, dict) and document.get("session_id") == session_id:
            items.append(item)
    return {"items": items}


def tool_vector_search(arguments: dict[str, Any], context: CallContext) -> dict[str, Any]:
    del context
    _expect_keys(arguments, {"session_id", "query", "limit"})
    agreement = _require_session(arguments)
    query = arguments.get("query")
    if not isinstance(query, str):
        raise ToolError("query is required.")
    limit = arguments.get("limit", 5)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ToolError("limit must be a whole number.")
    hits = vectors.search(query, session_id=agreement["session_id"], limit=limit)
    return {"items": hits}


def tool_catalog() -> list[dict[str, Any]]:
    string = {"type": "string"}
    number = {"type": "number"}
    whole = {"type": "integer"}
    flag = {"type": "boolean"}
    return [
        {
            "name": "health",
            "description": "CPU server health. No consent required. No client profile.",
            "inputSchema": _object_schema({}),
        },
        {
            "name": "consent_status",
            "description": (
                "Read consent for a session id. Unknown ids are not agreed. "
                "user_id is anonymous. Does not set a cookie."
            ),
            "inputSchema": _object_schema({"session_id": string}),
        },
        {
            "name": "consent_agree",
            "description": (
                "Record an active agreement for this MCP process. "
                "Omit session_id to mint one. Page loads must not call this. "
                "The agreement is forgotten when the process exits."
            ),
            "inputSchema": _object_schema({"session_id": string}),
        },
        {
            "name": "presets",
            "description": "List CPU edit presets and defaults. No consent required.",
            "inputSchema": _object_schema({}),
        },
        {
            "name": "upload",
            "description": (
                "Store one JPEG, PNG, or WebP (max 12 MB) after consent_agree. "
                "Pass the file as base64. The bytes stay on this machine."
            ),
            "inputSchema": _object_schema(
                {
                    "session_id": string,
                    "filename": string,
                    "data_base64": string,
                },
                ["session_id", "filename", "data_base64"],
            ),
        },
        {
            "name": "generate",
            "description": (
                "CPU Pillow edit and finish for uploaded ids. Requires consent_agree. "
                "consent_attested records image rights and defaults to false. "
                "descriptor is an optional note stored only in the local vector index, "
                "not in the sidecar. Do not put personal data in it."
            ),
            "inputSchema": _object_schema(
                {
                    "session_id": string,
                    "source_id": string,
                    "source_ids": {
                        "anyOf": [{"type": "string"}, {"type": "array", "items": string}]
                    },
                    "preset": string,
                    "crop": string,
                    "max_width": whole,
                    "brightness": number,
                    "contrast": number,
                    "saturation": number,
                    "sharpness": number,
                    "rotate": number,
                    "flip": string,
                    "filter": string,
                    "posterize": whole,
                    "solarize": whole,
                    "invert": flag,
                    "equalize": flag,
                    "colorize_black": string,
                    "colorize_white": string,
                    "blur_radius": number,
                    "finish": string,
                    "consent_attested": flag,
                    "descriptor": string,
                },
                ["session_id"],
            ),
        },
        {
            "name": "gallery",
            "description": (
                "List this session's generated items. Other sessions' outputs are omitted. "
                "Requires consent_agree."
            ),
            "inputSchema": _object_schema({"session_id": string}, ["session_id"]),
        },
        {
            "name": "vector_search",
            "description": (
                "Search this session's local vector index by text. "
                "Requires consent_agree. Results stay on this machine."
            ),
            "inputSchema": _object_schema(
                {"session_id": string, "query": string, "limit": whole},
                ["session_id", "query"],
            ),
        },
    ]


TOOLS = {
    "health": tool_health,
    "consent_status": tool_consent_status,
    "consent_agree": tool_consent_agree,
    "presets": tool_presets,
    "upload": tool_upload,
    "generate": tool_generate,
    "gallery": tool_gallery,
    "vector_search": tool_vector_search,
}


def call_tool(name: str, arguments: dict[str, Any], context: CallContext) -> dict[str, Any]:
    try:
        vectors.reject_invasive(arguments)
        payload = TOOLS[name](arguments, context)
    except (ToolError, vectors.PrivacyError) as exc:
        return _tool_result({"detail": str(exc)}, is_error=True)
    except app.HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return _tool_result({"detail": detail}, is_error=True)
    return _tool_result(payload)


def _initialize_result(params: dict[str, Any]) -> dict[str, Any]:
    requested = params.get("protocolVersion")
    if requested in SUPPORTED_PROTOCOLS:
        version = requested
    else:
        version = SUPPORTED_PROTOCOLS[-1]
    return {
        "protocolVersion": version,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "version": app.app.version},
        "instructions": INSTRUCTIONS,
    }


def handle_message(message: object, context: CallContext) -> dict[str, Any] | None:
    """Handle one JSON-RPC message. Notifications return None."""
    global _initialized
    if not isinstance(message, dict):
        return _rpc_error(None, -32600, "Invalid Request")
    msg_id = message.get("id")
    if message.get("jsonrpc", "2.0") != "2.0":
        return _rpc_error(msg_id, -32600, "Invalid Request")
    method = message.get("method")
    if not isinstance(method, str):
        return _rpc_error(msg_id, -32600, "Invalid Request")
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    notification = "id" not in message or message.get("id") is None

    if method in {"notifications/initialized", "notifications/cancelled"}:
        return None
    if method == "initialize":
        if notification:
            return _rpc_error(None, -32600, "initialize requires an id")
        _initialized = True
        return _rpc_result(msg_id, _initialize_result(params))
    if method == "ping":
        if notification:
            return None
        return _rpc_result(msg_id, {})
    if not _initialized and not notification:
        return _rpc_error(msg_id, -32600, "Server not initialized")
    if not _initialized:
        return None
    if method == "tools/list":
        if notification:
            return None
        return _rpc_result(msg_id, {"tools": tool_catalog()})
    if method == "tools/call":
        if notification:
            return None
        if not isinstance(message.get("params"), dict):
            return _rpc_error(msg_id, -32602, "Invalid params")
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or name not in TOOLS:
            return _rpc_error(msg_id, -32602, "Unknown tool")
        if not isinstance(arguments, dict):
            return _rpc_error(msg_id, -32602, "arguments must be an object")
        try:
            return _rpc_result(msg_id, call_tool(name, arguments, context))
        except Exception:
            print("mcp tool failed: internal", file=sys.stderr, flush=True)
            return _rpc_error(msg_id, -32603, "Internal error")
    if notification:
        return None
    return _rpc_error(msg_id, -32601, "Method not found")


def serve_stdio() -> None:
    print("galion-deep-mr-fake mcp listening on stdio", file=sys.stderr, flush=True)
    context = CallContext(transport="stdio", client_ip="local")
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return
        if len(line) > MAX_BODY:
            response: dict[str, Any] | None = _rpc_error(None, -32600, "Message too large")
        else:
            try:
                incoming = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                response = _rpc_error(None, -32700, "Parse error")
            else:
                response = handle_message(incoming, context)
        if response is not None:
            encoded = json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
            sys.stdout.buffer.write(encoded + b"\n")
            sys.stdout.buffer.flush()


def loopback_host(host: str) -> str:
    """Refuse a public bind. localhost and loopback addresses only."""
    if host == "localhost":
        return host
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("MCP HTTP listens on loopback only.") from exc
    if not address.is_loopback:
        raise ValueError("MCP HTTP listens on loopback only.")
    return host


def _host_allowed(value: str | None) -> bool:
    if not value:
        return False
    host = value.strip()
    if host.startswith("["):
        end = host.find("]")
        name = host[1:end] if end != -1 else ""
    elif host.count(":") == 1:
        name = host.split(":", 1)[0]
    else:
        name = host
    return name in {"127.0.0.1", "localhost", "::1"}


def _origin_allowed(origin: str) -> bool:
    parsed = urllib.parse.urlparse(origin)
    if parsed.scheme not in {"http", "https"}:
        return False
    return parsed.hostname in {"127.0.0.1", "localhost", "::1"}


class MCPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        """Skip access logs. They would repeat client addresses for every call."""
        return

    def _send(self, status: int, body: bytes, content_type: str, allow: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if allow:
            self.send_header("Allow", allow)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict[str, Any], allow: str | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json", allow)

    def _send_sse(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        body = f"event: message\ndata: {encoded}\n\n".encode("utf-8")
        self._send(200, body, "text/event-stream")

    def _guard(self) -> bool:
        if not _host_allowed(self.headers.get("Host")):
            self._send_json(403, {"detail": "Host is not local."})
            return False
        origin = self.headers.get("Origin")
        if origin is not None and not _origin_allowed(origin):
            self._send_json(403, {"detail": "Origin is not local."})
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802
        if not self._guard():
            return
        path = urllib.parse.urlsplit(self.path).path
        if path == "/health":
            self._send_json(200, {"status": "ok", "compute": "cpu", "transport": "http"})
            return
        if path == "/mcp":
            self._send_json(405, {"detail": "POST JSON-RPC to /mcp."}, allow="POST")
            return
        self._send_json(404, {"detail": "Not found."})

    def do_POST(self) -> None:  # noqa: N802
        if not self._guard():
            return
        path = urllib.parse.urlsplit(self.path).path
        if path != "/mcp":
            self._send_json(404, {"detail": "Not found."})
            return
        content_type = self.headers.get("Content-Type", "")
        if content_type and "application/json" not in content_type.lower():
            self._send_json(415, _rpc_error(None, -32600, "Content-Type must be application/json"))
            return
        sse_only = False
        accept = self.headers.get("Accept")
        if accept:
            parts = [part.split(";", 1)[0].strip().lower() for part in accept.split(",")]
            has_json = "application/json" in parts or "*/*" in parts
            has_sse = "text/event-stream" in parts
            if not has_json and not has_sse:
                self._send_json(
                    406, _rpc_error(None, -32600, "Accept must include application/json")
                )
                return
            sse_only = has_sse and not has_json
        length_header = self.headers.get("Content-Length")
        if length_header is None or not length_header.isdigit():
            self._send_json(411, _rpc_error(None, -32600, "Content-Length is required"))
            return
        length = int(length_header)
        if length > MAX_BODY:
            self._send_json(413, _rpc_error(None, -32600, "Message too large"))
            return
        raw = self.rfile.read(length)
        try:
            incoming = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, _rpc_error(None, -32700, "Parse error"))
            return
        # TCP peer only. X-Forwarded-For and similar headers are ignored.
        peer = self.client_address[0] if self.client_address else "local"
        context = CallContext(transport="http", client_ip=str(peer))
        response = handle_message(incoming, context)
        if response is None:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if sse_only:
            self._send_sse(response)
            return
        self._send_json(200, response)


def make_server(host: str = "127.0.0.1", port: int = 8766) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((loopback_host(host), port), MCPHandler)


def serve_http(host: str = "127.0.0.1", port: int = 8766) -> None:
    httpd = make_server(host, port)
    shown_host, shown_port = httpd.server_address[:2]
    print(
        f"galion-deep-mr-fake mcp listening on http://{shown_host}:{shown_port}/mcp",
        file=sys.stderr,
        flush=True,
    )
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Galion Deep Mr Fake local MCP server")
    parser.add_argument(
        "--http", action="store_true", help="Listen on loopback HTTP instead of stdio"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Loopback host for --http")
    parser.add_argument("--port", type=int, default=8766, help="Port for --http")
    args = parser.parse_args(argv)
    try:
        if args.http:
            serve_http(args.host, args.port)
        else:
            serve_stdio()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
