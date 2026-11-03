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
| D0 | Public MIT scaffold (LICENSE, README, CoC, CONTRIBUTING, this plan) | done (scaffold) | This repo |
| D1 | **Web interface** (`web/`) — upload, edit, generate, before/after gallery | MVP shell | See below |
| D2 | CPU image pipeline (Pillow + optional onnxruntime CPU) | planned | Behind Generate |
| D3 | Consent / provenance metadata hooks on outputs | planned | Sidecar JSON + visible label |
| D4 | Galion One / Voice API client stub | planned | HTTP or local IPC |
| D5 | Docs: threat model, AI Act labelling checklist | planned | `docs/` |

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

1. **Phase 0 (now):** scaffold + web MVP shell with Pillow edits + stub Generate
2. **Phase 1:** real CPU transform (style / enhancement) + output labelling badge
3. **Phase 2:** consent record + provenance sidecar; optional Voice/One hook
4. **Phase 3:** harden for Galion One demo rack (26 CPU nodes class) — rate limits, health, packaging

## Out of scope (v1)

- Non-consensual face swap / deepfake porn tooling
- GPU-only models
- Production multi-tenant SaaS billing (that lives with Galion One ops)

## Success criteria

- `uvicorn` starts on a laptop or EPYC/Xeon node without CUDA
- User can upload → edit → generate → see before/after in under a minute
- README documents consent + labelling expectations
