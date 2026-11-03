# Build plan — Galion Deep Mr Fake v2

**Owner:** Maciej Grajczyk (autor / voditelj razvoja) · **License:** MIT · **Repo:** [galion-studio/Galion-Deep-Mr-Fake-v2](https://github.com/galion-studio/Galion-Deep-Mr-Fake-v2)

## Product intent (open decision + recommended default)

**Open:** detection/labelling toolkit vs. licensed synthetic personas vs. creative CPU filters.

**Recommended default:** consent-first **authenticity / labelling + lightweight CPU image edit & transform** toolkit that Galion One and Galion Voice can call — **not** a MrDeepFakes-style non-consensual face-swap product.

Hard locks (same as Galion Voice):

- Explicit consent before ingest of a real person’s likeness
- No zero-shot cloning of arbitrary real people
- AI-generated / transformed content labelling (EU AI Act)
- CPU/RAM-only default fleet (no GPU dependency)

## Deliverables

| # | Deliverable | Status | Notes |
|---|---|---|---|
| D0 | Public MIT scaffold (LICENSE, README, CoC, CONTRIBUTING, this plan) | done (MVP) | This repo |
| D1 | **Web interface** (`web/`) — upload, edit, generate, before/after gallery | done (MVP) | FastAPI UI: upload, edits, presets, batch generate, gallery |
| D2 | CPU image pipeline (Pillow + optional onnxruntime CPU) | done (MVP) | Pillow ops, presets, batch, and CPU finish modes ship. onnxruntime stays optional and is not imported |
| D3 | Consent / provenance metadata hooks on outputs | done | Per-output sidecar beside each PNG, consent checkbox, `ai_generated: true` on the sidecar and gallery |
| D4 | Galion One / Voice API client stub | planned | HTTP or local IPC |
| D5 | Docs: threat model, AI Act labelling checklist | planned | `docs/` |

## V2 release checklist

**v2.0.0** is the working release of this consent-first CPU image toolkit. The items below are that gate. The FastAPI app and the README status line report **0.2.0**.

- [x] **Runnable web UI** — upload, edit, generate, and a before/after gallery (`web/`)
- [x] **CPU pipeline** — Generate is a CPU/RAM Pillow path (presets, extra ops, batch). No GPU dependency
- [x] **Tests / CI** — pytest suite and GitHub Actions for the web app (`.github/workflows/ci.yml`, `web/tests`)
- [x] **Docker / DX** — CPU-only image, Compose, and `make` / dev scripts (`Dockerfile`, `docs/DEVELOPMENT.md`)
- [x] **Consent sidecar** — every successful generate output writes a sibling `web/outputs/{source_id}_{suffix}.meta.json` (batch-safe form of `{id}_out.meta.json`) with `timestamp`, `params`, label `AI-assisted / transformed (CPU)`, and boolean `consent_attested` (optional form field, default false; one value covers the whole batch)
- [x] **Labelling** — sidecar and gallery include `ai_generated: true`, and the UI shows the AI-assisted label plus an AI-generated badge

## D1 — Web interface (recommended tech)

**Recommended for MVP:** **FastAPI** backend + **plain HTML/CSS/JS** frontend (single page served by FastAPI).

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **FastAPI + plain HTML/JS** | Tiny deps, easy to host on Galion One CPU nodes, full control, no Gradio lock-in | Slightly more glue than Gradio | **Recommended** |
| Gradio | Fastest demo | Heavier, less “product” feel, harder to embed | Acceptable alt MVP |
| Flask + Jinja | Familiar | Slightly more boilerplate than FastAPI for async uploads | Fine alternative |

**Scope (keep deliberately simple):**

1. Upload area for source image(s)
2. Basic edits: crop, resize, brightness, contrast, simple filters (grayscale, blur, sharpen)
3. **Generate** → lightweight CPU transform (Pillow filters / optional small ONNX CPU model later)
4. Results gallery with before / after
5. No GPU; no complex timelines, video, or face-swap in v1

**Run:** see `web/README.md` and `web/requirements.txt`.

## Phased roadmap

1. **Phase 0:** scaffold + web MVP — done
2. **Phase 1:** CPU transform (Pillow ops, presets, batch) + output labelling — Pillow path and labelling done; onnxruntime still optional
3. **Phase 2:** consent record + provenance sidecar — done in 0.2.0; Voice/One hook still open (D4). **Not** the image-watermark phase: an imperceptible PNG mark is a later hook only (`embed_imperceptible_mark` in `web/app.py` is unimplemented and must not be called).
4. **Phase 3:** harden for Galion One demo rack (26 CPU nodes class) — Docker/DX packaging is in place; rate limits and the rack rollout are still open

**V2 vs V3:** this repo’s V2 ships the image job only (upload, active consent, CPU generate, gallery). Video generation, pay-as-you-go Galion API billing, and a separate B200 GPU island are specified in [`V3_PLAN.md`](V3_PLAN.md) and are not implemented here.

## Out of scope (v1)

- Non-consensual face swap / deepfake porn tooling
- GPU-only models
- Production multi-tenant SaaS billing (that lives with Galion One ops)

## Success criteria

- `uvicorn` starts on a laptop or EPYC/Xeon node without CUDA
- User can upload → edit → generate → see before/after in under a minute
- README documents consent + labelling expectations
