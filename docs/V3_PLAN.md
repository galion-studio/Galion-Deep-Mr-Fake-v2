# V3 plan — video, paid API, GPU island

**Status:** documented only. V2 (this release) does not implement any of it.

V2 is the image job: upload, active consent, CPU generate, gallery, and the session sidecar. The shell leaves an empty mount (`#mode-switch`) for a future **Images | Video** switcher. Do not render that bar, encode video, bill anyone, or rent GPUs in V2.

Maciej’s V3 plan, in his terms:

## 1. Video generation

V3 adds **video generation** as a new mode after images. The mode bar comes later: **Images | Video**.

Frame extract, the video pipeline, and remux are **TBD**. Consent and AI labelling extend to video the same way they cover stills (active agreement before a job, labelled output, sidecar metadata).

This does **not** become a MrDeepFakes-style non-consensual porn marketplace. No face-swap product, no non-consensual likeness tooling.

## 2. External Galion API — paid, pay-as-you-go only

The external Galion API is **paid pay-as-you-go only**.

Every job pays **per generation job**. That includes researchers, PhDs, lawyers, and anyone else. There is **no free unlimited generation** on the paid API.

(The local MIT studio in this repo stays the open image toolkit. The paid meter is the external API, not a silent change to the CPU demo.)

## 3. Compute split

- **Galion One / Voice / Hermes** agentic stack stays **CPU/RAM-friendly**.
- Heavy Deep Mr Fake jobs move to a **separate GPU island**.
- Plan **one big server** hosting about **4× NVIDIA B200** instances, rented **monthly / in perpetuity**, to sit with Galion infrastructure for VRAM.

Do not start that rental in V2. Do not add a GPU dependency to the image MVP.

## 4. Ecosystem branding

Do not rename products into the wrong layer:

| Name | Role |
|---|---|
| **Galion One** | Main agent product |
| **Galion Voice** | Belongs under Galion One (sherpa-onnx cascade). Current focus stream |
| **Hermes Research** (also called Galion Research) and the console stack | Become the **Linux desktop** layer on **Galion OS** |
| **Deep Mr Fake** | Same Galion OS visual and product family. Not a separate brand |

The V2 studio already uses that family: system fonts, calm light surfaces, responsive layout, Galion naming. V3 keeps the same language when the mode bar appears.

## 5. Later V3 work

Not in V2:

- Billing meters (per generation job)
- Job queue onto the B200 pool
- Video bar in the UI (`#mode-switch`)
- API keys
- Rate limits

## Phase line

| Phase | Ships | Does not ship |
|---|---|---|
| **V2** | Image MVP UX, active consent, `/consent`, session sidecars, empty mode-switch hook | Video encode, billing, GPU rental, API keys |
| **V3** | Video mode, paid pay-as-you-go API, B200 capacity, queue, keys, rate limits | A non-consensual face-swap marketplace |
