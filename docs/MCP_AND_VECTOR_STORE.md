# MCP server and local vector store

**Owner:** Maciej Grajczyk · Galion Studio
**Status:** local CPU server in this repository. Galion One, Hermes Research, and Galion Voice are not wired in from here.

This is the agent surface for the consent-first image toolkit. An MCP client can check health, record agreement, upload, run the CPU generate path, list that session’s gallery, and search a local index of consented job metadata.

The studio UI stays the FastAPI app. The MCP server is a second process that calls the same Python functions. Video encode, GPU rental, and pay-as-you-go billing stay in [`V3_PLAN.md`](V3_PLAN.md) and are not part of this server.

## Boundaries

- The product remains a consent-first CPU image toolkit. It is not a face-swap product and it does not clone a real person’s likeness.
- Image bytes stay in `web/uploads/` and `web/outputs/`. The vector file stores metadata and a local hash, and it does not upload those files anywhere.
- The Phase-1 sidecar is unchanged. It still holds `session_id`, `created_at`, `client_ip` from the connection, `user_id` (`anonymous`), and the consent flags. The index does not copy `client_ip`.
- The server does not collect browser fingerprints, cookies, geolocation, ISP, client timezone, user agent, EXIF, or other telemetry. Requests that include those field names are refused.
- There is no cloud vector database and no call to an embedding API. The vector is computed in this process.
- There is no API key in this version. V3 still owns keys, rate limits, and billing.

## Processes

| Process | Command | Role |
|---|---|---|
| Studio | `make run` | Browser UI on `127.0.0.1:8765` |
| MCP stdio | `make mcp` | One agent over stdin/stdout |
| MCP HTTP | `make mcp-http` | Loopback `POST /mcp` on `127.0.0.1:8766` |

`make mcp` and `make mcp-http` need `make install` first. The equivalent commands are:

```bash
python web/mcp_server.py
python web/mcp_server.py --http --host 127.0.0.1 --port 8766
```

Run them from the repository root. HTTP refuses any host that is not loopback (`127.0.0.1`, `::1`, or the name `localhost`). The CPU Docker image still serves the studio only. Run the MCP server on the host.

The studio and the MCP server share code and the on-disk folders. They do not share consent memory. Agreeing in the browser does not agree the MCP process. Agreeing over MCP does not agree the browser. A restart of either process forgets agreement on purpose. The PNG, the sidecar, and the index row stay on disk.

Optional path overrides, for a local data directory or a test run:

| Variable | Default |
|---|---|
| `GDMF_UPLOADS` | `web/uploads` |
| `GDMF_OUTPUTS` | `web/outputs` |
| `GDMF_VECTOR_ROOT` | `web/data/vectors` |

These are directory paths. They are not analytics settings.

## Tools

| Tool | Consent | What it does |
|---|---|---|
| `health` | no | `{status, compute: cpu, transport}` |
| `consent_status` | no | `{session_id, consent_agreed, user_id: anonymous}` |
| `consent_agree` | no | Records agreement for this process. Omit `session_id` to mint one |
| `presets` | no | The same preset list as `GET /api/presets` |
| `upload` | yes | One JPEG, PNG, or WebP, base64, max 12 MB |
| `generate` | yes | CPU Pillow edit. Same parameters as the studio form |
| `gallery` | yes | This session’s outputs only |
| `vector_search` | yes | Text search of this session’s local index |

`generate` takes `source_id` or `source_ids`, optional edit fields, `preset`, `consent_attested` (boolean, default false), and an optional `descriptor`.

`consent_attested` is the image-rights flag, same as the form. `descriptor` is a short note (500 characters) stored only in the vector index. It is not written to the sidecar. Do not put a person’s name or other personal data in it. The server does not read the pixels to invent a description.

`upload`, `generate`, `gallery`, and `vector_search` return a tool error until `consent_agree` has been called for that `session_id` in this process. The error tells the agent to agree first. Loading a page, or calling `consent_status`, does not agree.

The studio’s `GET /api/gallery` still lists recent results for the person at the keyboard. The MCP `gallery` tool is narrower: it returns items whose sidecar `session_id` matches the caller.

## Transports

Protocol versions accepted: `2025-06-18`, `2025-03-26`, and `2024-11-05`. The server answers with the client’s version when it is one of those, and with `2024-11-05` otherwise. Capabilities advertised: tools. There is no resources or prompts list.

### stdio

Newline-delimited JSON-RPC on stdin and stdout. Logs, if any, go to stderr. A banner on stderr says the server is listening. Stdout is protocol only.

`client_ip` on the sidecar is the literal `local`. There is no TCP peer on stdio, and the server does not look one up.

Client sketch:

```json
{
  "mcpServers": {
    "galion-deep-mr-fake": {
      "command": "python",
      "args": ["web/mcp_server.py"],
      "cwd": "/absolute/path/to/Galion-Deep-Mr-Fake-v2"
    }
  }
}
```

Use the virtualenv interpreter (`web/.venv/bin/python`) when the system `python` does not have the web dependencies.

### Loopback HTTP

`POST http://127.0.0.1:8766/mcp` with `Content-Type: application/json`.

- A JSON body is returned when `Accept` includes `application/json` or is omitted.
- A single SSE `message` event is returned when `Accept` is only `text/event-stream`.
- Notifications receive `202` and an empty body.
- `GET /mcp` returns `405`. The server does not hold a server-initiated stream open.
- `GET /health` returns `{"status":"ok","compute":"cpu","transport":"http"}` for a local check.
- `Host` must be loopback. `Origin`, when a client sends it, must be loopback. This blocks a browser on another site from calling the port.
- The server does not set a cookie.
- `client_ip` on the sidecar is the TCP peer address. `X-Forwarded-For`, `X-Real-IP`, and similar headers are ignored.

```json
{
  "mcpServers": {
    "galion-deep-mr-fake": {
      "url": "http://127.0.0.1:8766/mcp"
    }
  }
}
```

Handshake, then a job:

```bash
curl -s http://127.0.0.1:8766/health

curl -s http://127.0.0.1:8766/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{}}}'

curl -s http://127.0.0.1:8766/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"consent_agree","arguments":{}}}'
```

Pass the returned `session_id` into `upload`, `generate`, `gallery`, and `vector_search`.

## How Galion One, Hermes Research, and Voice connect

These are client configurations for a person who runs the agent on the same machine as this repo. This repository does not register itself with a hosted control plane, and it does not open an outbound connection to those products.

| Client | How it connects |
|---|---|
| **Galion One** | Add the stdio command, or the loopback URL, in that agent’s MCP client settings. The hosted fleet is unchanged until an operator does this on a machine that has the checkout. |
| **Hermes Research** (Galion Research) | Same MCP client entry in the desktop agent. No Hermes plugin ships in this repo. |
| **Galion Voice** | If the Voice host can attach MCP tools, point it at this server. Send image jobs only. Do not send audio, speaker data, or transcripts. Voice’s sherpa-onnx cascade is not modified here. |

A typical agent turn is: `consent_agree`, `upload` with base64 image bytes, `generate` with a `source_id` and an optional descriptor, then `gallery` or `vector_search`. Call `consent_agree` again with the same `session_id` after a restart if the agent still holds that id. Until it does, the new process treats the id as not agreed, and the tools stay closed. Old index rows remain on disk under that id.

## Local vector index

Directory: `web/data/vectors/` (gitignored except `.gitkeep`).

| File | Role |
|---|---|
| `index.jsonl` | One JSON object per consented output |
| `.lock` | Short-lived lock while a write is in progress |
| `index.jsonl.tmp` | Replaced into `index.jsonl` at the end of a write |

The studio’s `POST /api/generate` and the MCP `generate` tool both index a job when `consent_agreed` is true and `session_id` is present. A direct call without agreement writes the sidecar only and skips the index.

Each row carries:

- `record_id`, `source_id`, `output`
- `session_id`, `created_at` (UTC `Z`), `user_id` (`anonymous`)
- `consent_agreed`, `consent_attested`, `ai_generated`
- `preset`, `label`, `params`, optional `width` and `height`
- `descriptor` (may be empty)
- `embed`: `local-hash-v1`
- `embedding`: 256 numbers

`user_id` other than `anonymous` is refused. `created_at` must already be UTC with a `Z` suffix. The server writes that timestamp. A client offset is not accepted, so the index is not a place to store a scraped timezone.

The embedding is a local feature hash: whole words plus character trigrams, SHA-256 buckets, L2-normalized, 256 dimensions. The same text always produces the same vector. No model file is downloaded. It is a small local index for this toolkit’s own jobs, on the order of the 200 newest rows. Older rows are dropped from the file when a write would pass that cap. It is not a neural face embedding and it does not hash the pixels.

Search is cosine similarity over the caller’s `session_id`. Other sessions’ rows are skipped. Scores at or below zero are omitted. `limit` is 1–20, default 5. The tool result leaves the raw vector out.

The JSONL file is plaintext on the machine that runs the toolkit. Anyone with access to that disk can read it. The MCP tools do not offer a cross-session dump.

### Refused fields

The index and the MCP tools reject these names, including nested ones: fingerprint, browser fingerprint, canvas hash, cookie, cookies, geolocation, geo, latitude, longitude, lat, lon, gps, isp, timezone, time zone, tz, user agent, telemetry, exif, client IP, ip, ip address.

`client_ip` remains on the sidecar, where Phase 1 already records the connection address. It is not copied into the searchable index.

## Tests

From the repository root:

```bash
python -m pytest web/tests -q
```

The suite covers the handshake, the consent gate, a stdio subprocess, loopback HTTP (including a refused public bind, a refused foreign `Origin` / `Host`, and an ignored `X-Forwarded-For`), sidecar keys, and the local index rules. No GPU and no network service are required.
