# V3 plan — video, paid API, GPU island

**Status: documentation only. Not implemented in V2.**

This file is the plan Maciej Grajczyk (Galion Studio) executes later. Merging it adds no encoder, no meter, no GPU rental, no API keys, and no rate-limit code. `make run`, pytest, and the local MCP server stay the CPU image toolkit.

**Owner:** Maciej Grajczyk · Galion Studio
**Local license:** MIT, unchanged
**Service:** the external Galion API is a paid Galion service. It does not narrow the MIT grant on this repository.

Read [`BUILD_PLAN.md`](BUILD_PLAN.md) for the V2 image gates, [`DEVELOPMENT.md`](DEVELOPMENT.md) for the CPU setup, and [`MCP_AND_VECTOR_STORE.md`](MCP_AND_VECTOR_STORE.md) for the local agent server. Those three describe software that exists. This file describes software that does not.

## Locked decisions

Defaults below are the plan of record. Maciej is the only person who changes a row. A change is a one-line edit in this table plus the section it points at. Silence means the default stands.

| ID | Decision | Default |
|---|---|---|
| D1 | Mode control | One top segmented control, **Images \| Video**, mounted in `#mode-switch`, every width. Images selected. Keyboard radiogroup. Changing mode does not submit a job and does not record consent. |
| D2 | Where video runs | Paid GPU island only. The MIT app stays CPU/RAM and does not encode. |
| D3 | First SKU | `video-6s-720p24`: silent clip, at most 6.0 s, 1280×720, 24 fps, from stills or one short clip the caller has rights to. |
| D4 | Model class | Short image-to-video, or a text-conditioned clip, with no face-identity embedding and no second reference person. Maciej accepts the weights in writing before any download. |
| D5 | Label | Human-visible “AI-generated” (end card or corner) plus sidecar `ai_generated: true`. `embed_imperceptible_mark` stays uncalled. |
| D6 | Charge | Authorize when the job is accepted. Capture on `ready`. Void on `refused` and on infrastructure `failed`. Cancel after `running` captures. |
| D7 | Price | **€2** per ready `video-6s-720p24` job. One public list. Floor €1. No €0 row. Recompute after 50 measured island jobs (section 6). |
| D8 | Who pays | Every paid-API caller, including PhDs, lawyers, and research groups. Same list. No unlimited key. No application form. |
| D9 | Island | One single-tenant server, about **4× NVIDIA B200**, rented monthly on a term that can be renewed in perpetuity. Quote gate before any order. |
| D10 | Slots | Four. One running job per GPU. No packing until an OOM-free measurement says otherwise. |
| D11 | Limits | 30 creates/min/key, 2 concurrent video jobs/key, queue 20 waiting/key and 40 waiting on the island, spend cap €25/day (customer may raise it), platform ceiling €500/day/key. |
| D12 | Identity | Paid API: account email + processor payment token + key id. Local studio: session id, `user_id` `anonymous`. No geo, ISP, browser fingerprint, or analytics cookie. |
| D13 | MCP | Local CPU MCP stays as documented. This repository opens no connection to Galion One, Hermes, or Voice. The paid API is a separate keyed HTTPS surface. |
| D14 | Names | Voice stays under Galion One. Hermes Research and the console become the Galion OS Linux desktop. Deep Mr Fake stays in that family. |
| D15 | Landing | Hosted Galion surface. Light iOS surfaces, navy-rose wash, system font, almost no text. The MIT studio is not paywalled. |
| D16 | Video index | Video rows do not enter `web/data/vectors/`. The local index stays consented image metadata. |

CPU-rack rate limits in [`BUILD_PLAN.md`](BUILD_PLAN.md) Phase 3 are a different gate. They are not D11.

## Product locks

V2 is a consent-first CPU image toolkit: upload, active agreement, Pillow generate, gallery, Phase-1 sidecar, local MCP. It is a labelling and lightweight transform tool.

The following stay closed for V2 and for V3:

- A MrDeepFakes-style marketplace of non-consensual sexual images.
- Face-swap as a product, a preset, an endpoint, or a parameter.
- Zero-shot cloning of an arbitrary real person’s face or voice.
- A public feed of other people’s outputs.
- Training on customer media.
- Any path that makes `make run` or pytest depend on a GPU.

Synthetic media of a real person still requires rights the caller actually has, an active agreement before the job, and a label a person and a machine can both read. The EU AI Act labelling duty is why the sidecar and the visible mark both ship. This file is not the legal opinion. Before the first public charge (gate V3-6), Maciej and the Poland operator write a short confirmation that the visible mark plus the sidecar meet that duty for the first SKU. V3-6 stays shut until that note exists.

The local program remains public MIT software for research, study, PhD work, and ordinary lawful use. That freedom is the program on the caller’s machine. It is not a free hosted GPU.

## What V2 already finished

Leave this behaviour in place.

| Piece | Where it lives |
|---|---|
| Image studio | `web/templates/index.html`, `web/static/app.css`, `web/static/app.js` |
| Empty mode mount | `#mode-switch`, `hidden`, `aria-hidden="true"`. The HTML comment forbids a video bar in V2. |
| Wide layout | CSS breakpoint `min-width: 801px` |
| Active consent | `GET /consent`, `POST /consent/agree`, `POST /api/consent/agree`. Page load does not agree. Restart forgets agreement. |
| Session | Cookie `gdmf_session`, HttpOnly, no `Max-Age`. It is the consent session. It is not an analytics cookie. |
| Image-rights flag | `consent_attested`, default false, one value per generate call |
| Sidecar | `web/outputs/{source_id}_{suffix}.meta.json` |
| CPU label | `AI-assisted / transformed (CPU)`, `ai_generated: true` |
| Imperceptible mark | `embed_imperceptible_mark` in `web/app.py` is a hook. Generate does not call it. |
| Local MCP | `make mcp`, `make mcp-http` on `127.0.0.1:8766`. See [`MCP_AND_VECTOR_STORE.md`](MCP_AND_VECTOR_STORE.md). |
| Palette in the studio | Grouped background `#f2f2f7`, card `#ffffff`, text `#1c1c1e`, muted `#8e8e93`, action `#007aff`, radius 20px, system font. Soft blue and green washes at under 10% opacity. |

Phase-1 sidecar keys, which video must keep and must not replace:

`id`, `output`, `timestamp`, `created_at`, `params`, `label`, `consent_attested`, `consent_agreed`, `ai_generated`, `preset`, `session_id`, `client_ip`, `user_id`, `user_label`, `responsibility`.

`client_ip` is the connection address only. The paid edge ignores `X-Forwarded-For`, `X-Real-IP`, and similar headers unless Galion’s own proxy writes the peer once. Nobody looks that address up. It is not copied into the vector index. `user_id` on the local studio stays `anonymous`. No legal name is invented.

Responsibility flags already recorded after an active agreement stay on video jobs:

- `user_agreed_not_to_create_harmful_content`
- `user_is_legally_responsible_for_what_they_create`
- `program_takes_no_responsibility`
- `public_mit_oss_for_research_and_phds`

## Video mode

### Control

V2 leaves `#mode-switch` empty on purpose. V3 fills that node and removes `hidden` / `aria-hidden` only when a video job can actually be submitted to the paid API (gate V3-6). Until then the node stays empty, including through the policy and billing work.

The control is a `radiogroup` labelled Mode:

- **Images** — today’s studio. The button reads **Generate**. No price.
- **Video** — the first SKU. The button reads **Generate · €2**.

Phone and desktop share this one control, in the header, under or beside the Galion wordmark. Minimum target 44px. Arrow keys move the selection. The V2 comment allows a side switcher from 801px up. D1 rejects that. Two navigations would split a shell that is already a single column of cards. Maciej reopens D1 only after a pass on a wide screen shows the header cannot hold two segments.

Selecting Video on a MIT build that has no paid endpoint configured shows the price and one control, **Open API**, linking to the hosted price screen. It does not `POST /api/generate`. The CPU route continues to accept images only.

### Job the caller sees

Video is a short clip made from media the caller supplies. The pane has a drop zone, the consent gate, the price on the button, and a result player. It has no timeline, no keyframes, no face box, no “reference person” slot, and no preset named after a human being.

Drop zone accepts the studio’s stills (JPEG, PNG, WebP, 12 MB, up to 16) and one source clip (MP4 or WebM) inside D3 and the byte cap in section 6. Audio in a source clip is stripped. Galion Voice is not called. This product does not speak in someone’s voice.

### Pipeline on the island

Each stage has a failure that does not fall through:

1. **Sniff.** Container, duration, resolution, fps, byte length. Over cap → `over_cap`, no queue, no charge.
2. **Consent.** `consent_agreed` and `consent_attested` both true. Paid video requires the rights flag. Local images keep today’s default of false. Missing agreement → `consent_required`.
3. **Policy.** Forbidden fields and forbidden intents → `policy_refused`, no GPU, void. See below.
4. **Authorize.** Processor hold for €2. No hold → `payment_required`.
5. **Queue.** Admit or `queue_full` / `rate_limited` / `spend_cap`. A reject here voids the hold.
6. **Decode.** Island CPU writes frames to a scratch directory. Scratch is deleted at the end of the job whether it succeeds or fails.
7. **Generate.** Exactly one B200 runs the accepted model (D4). One slot (D10).
8. **Label.** Visible “AI-generated”, then remux.
9. **Remux.** H.264 in MP4, `faststart`, no audio track, pixel size and duration inside the SKU.
10. **Sidecar, then URL.** The sidecar is on disk before the download URL exists. State `ready`. Capture €2.

A GPU error retries once on a different GPU. A second failure is `failed` and voids. An out-of-memory failure does not retry at a larger size. Policy refusals and payment failures do not retry.

Download URLs are signed, single-purpose, and expire in one hour. The object and its sidecar are deleted **7 days** after `ready` whether or not anyone downloaded them. Local MIT files are untouched by that clock. They stay on the machine that ran the studio until that person deletes them.

### Consent copy when V3-1 lands

`/consent` gains one short block, after the existing image risks, in the same voice as the current notice:

- The video job is a synthetic clip.
- It carries a visible AI-generated mark and a sidecar.
- The paid API charges €2 for each ready clip of this SKU.
- The MIT studio on the caller’s machine is still the CPU image tool and is not billed.
- Face-swap, a non-consensual sexual image, and cloning a real person the caller has no rights to are refused.

The studio Accept line, when Video is selected, reads:

> Accept to run a paid video job. I have rights to this media, and I am responsible for what I create.

Unchecked. Never auto-approved. Accept is not sent on load. One acceptance covers the session, same as images. `consent_attested` is sent true only after that acceptance.

### Sidecar for a video job

Same Phase-1 keys, plus these job fields and no others:

| Key | Value |
|---|---|
| `label` | `AI-assisted / transformed (GPU)` |
| `media` | `video` |
| `compute` | `gpu` |
| `sku` | `video-6s-720p24` |
| `duration_s`, `fps`, `width`, `height` | Measured output |
| `container` | `mp4` |
| `codec` | `h264` |
| `price_eur` | `2` |
| `job_id` | Island job id |
| `key_id` | Public key id, never the secret |

`user_id` on a paid job is the account id the customer created. `user_label` is `account:<id>`. Neither is a name. Local jobs stay `anonymous` and `session:<id>`.

Do not add fingerprint, cookie, geolocation, ISP, timezone, user agent, EXIF, or a face embedding. Requests that include those names, or the names in the next section, are refused in full. They are not stripped and stored.

The gallery badge on a video card reads **AI-generated**. The player does not autoplay with sound, because the file has no sound.

## Out of scope: marketplace, swap, clone

Deep Mr Fake does not become a non-consensual face-swap marketplace. V3 does not add accounts that follow each other, a discovery page, comments, or a catalogue of identities.

The API has no field for a target person. These names are refused wherever they appear, including nested JSON, the same way the MCP server refuses telemetry names:

`face_embedding`, `identity`, `target_person`, `celebrity`, `swap`, `reference_face`, `lora_person`, `voice_id`, `speaker`, plus the MCP refuse list in [`MCP_AND_VECTOR_STORE.md`](MCP_AND_VECTOR_STORE.md) (fingerprint, cookie, geo, latitude, longitude, ISP, timezone, user agent, telemetry, EXIF, and the rest of that list).

Stable refusal reasons inside `policy_refused`:

| Reason | When |
|---|---|
| `face_swap` | Any swap-shaped parameter or instruction |
| `identity_clone` | A request to generate a real person the caller did not supply as their own consented source |
| `nonconsensual_intimate` | Sexual content of a person who has not consented |
| `minor` | Sexual or romantic content involving a minor. No ID upload is collected. Ambiguous jobs are refused. |
| `voice_clone` | A request to synthesize a person’s voice. That work is outside this product. |
| `marketplace` | A request to publish into a shared gallery |

HTTP 403, body `{ "error": "policy_refused", "reason": "<reason>" }`. The GPU does not start. The hold is voided. The response does not echo the offending payload.

The Code of Conduct already rejects this class of contribution. A V3 pull request that adds a swap endpoint, a celebrity preset, or a public gallery is closed.

## External Galion API

Pay-as-you-go, per generation job, for every caller. Researchers, PhDs, lawyers, and internal Galion users pay the same €2 when they use this API. There is no free tier, no “first N free”, no academic unlimited key, and no invoice line of €0. A €0 capture is a defect.

The local MIT studio stays open. Running it, agreeing to `/consent`, and generating a CPU image do not create an invoice and do not require a key.

The paid API’s first billable unit is the video SKU. Hosted image jobs are a later SKU on the same meter, still at a positive price, still consent-gated. They are off at launch. CPU images stay on the local studio. Maciej adds a hosted image row only by writing a new price, a new cap, and a new label string. He does not turn it on as a silent free path.

### Surface

Planning hostname: `https://api.galion.app`. Maciej confirms he controls that name before gate V3-3. If he does not, he writes the real host into this paragraph and into the landing link. Loopback stays as it is: studio `127.0.0.1:8765`, MCP `127.0.0.1:8766`. The island has no public GPU port.

| Method | Path | Role |
|---|---|---|
| `POST` | `/v1/jobs` | Create one video job |
| `GET` | `/v1/jobs/{id}` | State, price, refusal reason |
| `GET` | `/v1/jobs/{id}/output` | Signed download after `ready` |
| `GET` | `/v1/jobs/{id}/sidecar` | Phase-1 sidecar JSON |
| `POST` | `/v1/keys` | Mint a key. Secret returned once |
| `POST` | `/v1/keys/{id}/revoke` | Revoke now |
| `GET` | `/v1/billing/usage` | That account’s jobs, prices, and cap |

Authentication is `Authorization: Bearer`. The secret never travels in a query string. TLS at the Galion edge. Create takes an `Idempotency-Key`. The same key and the same body return the same job for 24 hours. The same key and a different body return 409. That is what stops a retry from billing twice.

Create body, planning shape:

```json
{
  "media": "video",
  "sku": "video-6s-720p24",
  "consent_agreed": true,
  "consent_attested": true
}
```

Stills or the one source clip travel as multipart parts on the same call, or as `source_ids` of objects already uploaded with that key. There is no `descriptor` required. An optional note of at most 500 characters may be stored on the sidecar under `params.note`. It must not name a person. It is not written to the local vector index (D16).

States: `accepted` → `queued` → `running` → `labelling` → `ready`. Terminal: `refused`, `rejected`, `failed`, `cancelled`, `expired`.

| HTTP | Error | Money |
|---|---|---|
| 402 | `payment_required`, `spend_cap` | No capture |
| 403 | `consent_required`, `policy_refused` | Void |
| 413 | `over_cap` | No hold |
| 429 | `rate_limited`, `queue_full` | Void if a hold was taken |
| 409 | idempotency conflict | No second job |

Scopes on a key: `jobs:video`, `jobs:read`, `billing:read`. No admin scope on the public API. No scope grants a swap or a clone.

### Keys

A key is a bearer secret the server shows once. Prefix `gdmf_live_` so a leak is obvious in a log. At least 32 bytes of randomness. Store a hash. The plaintext is not recoverable.

An account may hold more than one key (a lab key and a production key). Each key has its own D11 counters and its own spend cap. Revoke is immediate: the next call is 401. Rotation is mint-new, then revoke-old. Overlap default is 24 hours, then the old secret 401s. Maciej can shorten the overlap. He cannot disable revocation.

Keys are account credentials. They are not cookies, and they are not derived from a browser. The landing and the billing screens set no tracking cookie. The studio’s `gdmf_session` cookie is unchanged and is not accepted as payment identity.

### Rate limits and the meter

Counters key off the key id and the account. They do not key off IP reputation, geo, or a fingerprint. `client_ip` on the sidecar stays the Phase-1 connection address and is not a quota dimension.

D11 is the launch table:

| Limit | Value |
|---|---|
| Creates | 30 per minute per key |
| Concurrent `running` video jobs | 2 per key |
| Island slots | 4 |
| Waiting queue | 20 per key, 40 on the island |
| Source clip | at most 10 s, at most 100 MB, at most 1920×1080 |
| Output | the SKU: ≤ 6 s, ≤ 1280×720, 24 fps |
| Spend cap | €25 per day per key, on by default |
| Platform ceiling | €500 per day per key until Maciej raises it in this table |

The customer may raise their own cap up to the platform ceiling inside the billing screen. They may lower it. They may not turn it off. A leaked key stops at the cap.

Authorize €2 at `accepted`. Capture on `ready`. Void on `refused`, `rejected`, `failed`, and on cancel-before-`running`. Cancel after `running` captures, because the GPU time was used. Expired downloads are not refunded. The receipt is one line: job id, SKU, €2, state.

After **50** jobs reach `ready` or `failed` on the real island, Maciej recomputes the price:

1. Monthly rental invoice in EUR.
2. Sellable GPU-seconds at 50% of nameplate: `4 × days_in_invoice × 86400 × 0.5`.
3. Multiply the resulting EUR-per-second by the measured p95 seconds of this SKU.
4. Round up to a whole euro. Floor €1.

He writes the new number into D7 if it differs, and he does not set a price below that result. Until those 50 jobs exist, the card shows €2 and the pilot captures €2. The pilot is a real charge for real clips, issued only to keys Maciej has created, and it is still subject to consent and to the refusal table. It is not a comp account.

Settlement currency is EUR. The Poland operating company is the seller. The card or invoice vendor is chosen by Maciej with that company before V3-6. This plan does not bind a vendor and does not add a payment SDK. If no vendor is chosen, public charges do not start.

Operator counters Maciej may keep: jobs by state, GPU busy seconds, euros captured, euros voided, queue depth. Those are counts. They are not user-agent logs, heatmaps, or session replays.

## Landing and billing UX

Experience first. The screen shows the work and the price. B200s, queues, MCP, and model names do not appear on these screens. One Galion wordmark. System font, the same stack as `web/static/app.css`. Tight tracking on the wordmark, about `-0.03em`. Motion uses the studio curve `cubic-bezier(0.32, 0.72, 0, 1)` and respects `prefers-reduced-motion`.

### Palette

Apple-minimal iOS surfaces, with a navy-rose wash. Soft cyberpunk here means two low-opacity fields of colour. It does not mean neon type, scanlines, glitch, or a monospace HUD.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#f2f2f7` | Page |
| `--card` | `#ffffff` | Sheets |
| `--text` | `#1c1c1e` | Wordmark and price |
| `--muted` | `#8e8e93` | The one footer line |
| `--accent` | `#007aff` | The single primary button |
| `--navy` | `#0d1b2a` | Wordmark colour on the landing, first wash |
| `--rose` | `#c45c6a` | Second wash |
| `--radius` | `20px` | Cards and buttons |
| `--sep` | `rgba(60, 60, 67, 0.12)` | Hairline |

Landing background, and only the landing and the price screen:

```css
background:
  radial-gradient(900px 480px at 12% -10%, rgba(13, 27, 42, 0.10), transparent 60%),
  radial-gradient(720px 420px at 100% 0%, rgba(196, 92, 106, 0.12), transparent 55%),
  #f2f2f7;
```

The studio itself keeps today’s blue and green washes so a person moving from landing to Images does not feel a second product. Navy-rose belongs to the front door and the receipt, not to a recolor of the editor. Light mode only, `color-scheme: light`, theme colour `#f2f2f7`. A dark landing waits until the studio itself ships dark, which is outside V3.

No third-party font, no analytics script, no chat widget, no cookie banner. There is no tracking cookie to ask about. The payment page may load the processor’s card field. That field stays on the pay screen and is not given a marketing pixel beside it.

### Screens

Four screens. Almost no text. The strings in the table are the copy. Anything else needs a new row here before it is designed.

| Screen | What is on it | Primary action |
|---|---|---|
| Landing | Wordmark **Galion**. One crossfading still of a consented abstract or licensed image. No face. | **Studio** and **API** |
| Price | Wordmark. **€2**. The words **per video job**. | **Continue** |
| Pay | **€2 per job**. Card or invoice. Spend cap, default €25 / day. | **Pay** |
| Key | The secret, a **Copy** control, the line **Shown once.** | **Done** |

Footer on the landing only, one line, muted: `MIT · consent · AI-labelled`, with links to `/consent` and to the price screen.

**Studio** opens the local MIT image app. **API** opens the price screen. **Continue** opens pay. **Pay** mints the key only after the processor accepts the method. **Done** returns to Video mode if the caller came from the switcher, otherwise to the price screen.

Empty billing state is the price and the button again. There is no chart. The job list, when it exists, is rows of state, price, and download. Refused and failed rows show the reason and **Voided**. Failed rows also show **Retry**. A row that hits the cap shows the cap figure and stops. It does not open a sales page.

The still on the landing is abstract or clearly licensed. It is not a portrait of a real person, and it is not a demonstration of a swap.

### What these screens refuse to contain

These screens leave out a feature grid, a blog, testimonials, university logos, a research badge, a chat, a plan comparison, and the words GPU, B200, queue, MCP, and deepfake. PhDs and lawyers see the same €2 as everyone else. Their route to a CPU edit on their own machine is the **Studio** button.

## GPU island

Heavy Deep Mr Fake jobs run on a separate machine. Galion One, Galion Voice, and Hermes stay CPU/RAM-friendly. The island does not host agent loops, the sherpa-onnx cascade, or the desktop.

### Size

Planning SKU, to be read off the quote before anyone signs:

| Item | Assumption to confirm |
|---|---|
| GPUs | 4× NVIDIA B200 |
| Memory | 192 GB HBM3e per GPU, about 768 GB on the box. The quote line wins if the SKU differs. |
| Packing | One job per GPU (D10) |
| Host | One server. On the order of 64 CPU cores, 512 GB RAM, 8 TB NVMe scratch, 100 GbE toward the Galion CPU fleet. The quote’s real figures replace these. |
| Power | On the order of 1 kW per B200 plus the host. Facilities uses the quote, not this sentence. |
| Tenancy | Single-tenant. Monthly rental, renewable in perpetuity. Not spot, not a shared serverless GPU, not a third-party inference API that receives customer frames. |
| Place | Same trust boundary as the rest of Galion infrastructure. Poland operator. GDPR. |
| Drivers | Live on this host only. Galion OS does not need them to boot. |

An 8-GPU chassis or an NVL72 rack is a different plan. Maciej accepts that in writing, in D9, before the order. Otherwise the order stays four GPUs.

Throughput, for capacity talk only, until it is measured: if one GPU finishes one SKU job in 60–120 seconds, four GPUs finish on the order of 120–240 jobs an hour. Publish nothing from that range. The first real number is the p95 from the 50-job review. Customer quotas are D11, not this paragraph.

### Queue

The paid API is the only client of the queue. The local studio does not enqueue. MCP does not enqueue.

Admission order: consent, policy, payment hold, rate limit, queue depth, then a free slot. FIFO inside a key. Across keys, round-robin so one key’s backlog cannot pin all four GPUs; the per-key concurrency cap of 2 already limits that, and the scheduler still alternates when several keys are waiting.

No research priority. A PhD key does not jump a paying key, because it is a paying key.

Scratch, decoded frames, and model activations are deleted at the end of the job. Logs for the operator are the counters in the meter section plus the job id, key id, state, and timestamps. Prompts and frames are not shipped to a log vendor.

If the island is down, new jobs fail, holds void, and Galion One’s CPU fleet keeps serving agents. V3 has one region. There is no warm standby.

### Procurement gate

Maciej sends the quote request. He does not start it from this repository, and this repository does not contain credentials, a cloud account, or a Terraform stack for the island.

The quote matches D9, or Maciej edits D9 first. Only then may a contract be signed. Rent is operational work outside this codebase.

## Ecosystem

Do not rename a product into the wrong layer.

| Name | Role |
|---|---|
| **Galion One** | Main agent product. CPU/RAM-friendly. May call this toolkit as an MCP client when an operator configures that on a machine with the checkout. |
| **Galion Voice** | Belongs under Galion One. sherpa-onnx cascade. Current focus stream. CPU-first. Image jobs only if its host attaches MCP tools. No audio, speaker data, or transcripts are sent here. Voice is not a video product and is not moved onto the GPU island. |
| **Hermes Research** (also Galion Research) and the console | Become the **Linux desktop** on **Galion OS**. The desktop runs the local CPU studio and, separately, a client of the paid API. It does not absorb Voice, and it does not become the GPU host. |
| **Galion OS** | That desktop layer. Same visual family: system font, light surfaces, Galion wordmark, the navy-rose wash on the front door. |
| **Deep Mr Fake** | A tool in that family. The V2 studio already uses the family (system fonts, calm light surfaces, responsive layout, Galion naming). V3 keeps it when the mode control appears. |

The desktop is not built in this repository. When it ships, Images and Video use the same control as D1. Boot of the desktop does not depend on the island.

## MCP clients

Wiring notes only. Nothing in this plan opens a socket to Galion One, Hermes Research, or Galion Voice, and nothing registers this repository with a hosted control plane.

The local server is specified in [`MCP_AND_VECTOR_STORE.md`](MCP_AND_VECTOR_STORE.md). Summary an operator needs:

| Process | Command | Bind |
|---|---|---|
| Studio | `make run` | `127.0.0.1:8765` |
| MCP stdio | `make mcp` | stdin/stdout |
| MCP HTTP | `make mcp-http` | `127.0.0.1:8766`, loopback only |

HTTP refuses a non-loopback host. It sets no cookie. `Origin` and `Host` must be loopback. Stdio writes `client_ip` as the literal `local`.

Client entry an operator pastes into **their** agent config, on a machine that has this checkout:

```json
{
  "mcpServers": {
    "galion-deep-mr-fake": {
      "command": "web/.venv/bin/python",
      "args": ["web/mcp_server.py"],
      "cwd": "/absolute/path/to/Galion-Deep-Mr-Fake-v2"
    }
  }
}
```

Loopback alternative: `{"url": "http://127.0.0.1:8766/mcp"}`.

| Client | What the operator does | What this repo does |
|---|---|---|
| **Galion One** | Add the stdio command or the loopback URL in that agent’s MCP settings. | Nothing. No outbound call. The hosted fleet is unchanged until the operator edits it. |
| **Hermes Research** | The same entry in the desktop agent, once that agent runs on Galion OS. | No Hermes plugin ships here. |
| **Galion Voice** | If the Voice host can attach MCP tools, point it at this server for image jobs. | Do not modify the sherpa-onnx cascade. Refuse audio payloads by leaving them off the tool list. |

A normal agent turn is `consent_agree`, then `upload`, then `generate`, then `gallery` or `vector_search`. Agreement is per process. A restart requires `consent_agree` again. Tools that touch media stay closed until then.

The paid video API is not an MCP transport. It is HTTPS with a key, and every ready job costs €2. If Galion One later submits video, it does so with a key the operator stores, through `/v1/jobs`, under D8. That client is written when V3-6 is open. It is not implied by the local MCP server. The GPU island is not exposed as a public MCP endpoint.

Video output is not inserted into `web/data/vectors/` (D16). The index remains a local hash of consented image metadata, 256 dimensions, `local-hash-v1`, capped near the 200 newest rows, session-scoped. It is not a face embedding. A future video row, if Maciej reverses D16, may hash an optional text note only. It may not hash pixels.

## Phased delivery

V2 gates are closed. V3 gates open in order. A later gate does not start because an earlier one is “mostly done”. Maciej accepts each exit test.

### V2 — done

- [x] Image studio: upload, edit, presets, batch, before/after gallery
- [x] CPU/RAM Pillow path. onnxruntime not required
- [x] pytest and GitHub Actions
- [x] CPU Docker image and Compose
- [x] Active consent, `/consent`, session sidecar, `ai_generated: true`
- [x] `#mode-switch` present, empty, hidden
- [x] Local MCP server and local vector index
- [x] Video encode, billing, GPU rental, API keys, and paid-API rate limits absent

### V3 — next

| Gate | Builds | Exit test | Stays out |
|---|---|---|---|
| **V3-0** | This document | Diff is docs. `web/` untouched. | Runtime |
| **V3-1** | Consent block for video. Fixture tests that forbidden field names return `policy_refused` and write no output. | pytest still CPU. `#mode-switch` still empty. | Encoder, price capture |
| **V3-2** | Landing, price, pay, and key screens as static IA, copy limited to the table above, palette tokens as specified. | No third-party script except a stub where the card field will be. No analytics cookie. Studio still has no price on **Generate**. | A live charge |
| **V3-3** | Key mint/revoke, idempotency, D11 counters, authorize/void against the test mode of the chosen processor. | A test job cannot reach `ready` at €0. Secrets stored as hashes. | GPU, public DNS traffic |
| **V3-4** | Quote for D9. | Quote matches D9, or D9 is edited first. Contract may then be signed outside this repo. | Drivers in the MIT image, any credential in git |
| **V3-5** | Island worker, four slots, decode, the accepted model, visible label, remux, sidecar, 7-day delete. | One consented SKU clip returns `ready` with sidecar and visible mark. A `face_swap` fixture never occupies a GPU. p95 seconds written down. | A public price change below the formula |
| **V3-6** | Public keys, live capture, mode control rendered, **Generate · €2**. | Operator confirmation on AI Act labelling is filed. Vendor is chosen. 50-job price review is scheduled. Local `make run` and pytest still have no GPU dependency. | Auto-registration of Galion One, Hermes, or Voice. Video rows in the local vector index. |

V3 is shipped when all of the following are true:

- A caller with rights submits a consented still and receives a labelled 720p clip and a sidecar.
- The receipt is €2, or the recomputed whole-euro price, and it is not zero.
- A swap-shaped request returns `policy_refused`, voids, and does not start a GPU.
- PhD, lawyer, and research keys use that same price.
- The MIT studio still generates a CPU image with no account and no invoice.
- No geo, ISP, or browser fingerprint is collected. Sidecars still match Phase-1 plus the video fields in the table above.
- Galion One, Voice, and Hermes still run CPU-first. The island is the only GPU, and it is the one Maciej rented under D9.

## Not in this pull request

No edit under `web/`. No workflow change. No cloud account. No live MCP session to Galion One, Hermes, or Voice. The mode mount stays empty. The next code change, when Maciej asks for it, is V3-1 and nothing else.

— Maciej Grajczyk, Galion Studio
