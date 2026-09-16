# zuper-wop-notify

Thin **unidirectional** Flask service: Zuper webhook in → filter for module *Waiting on Parts* jobs → **GET-only** job detail from Zuper → JSON notify out to Shop Manager Bot + Parts Bot.

It never writes to Zuper (no PATCH/PUT/POST). It never talks to Google Calendar. It never invents stock or SKUs — only prefixes that actually appear on the live job are forwarded.

## Flow

1. Verify webhook secret (`x-webhook-secret` or `secret-key` / `Secret-Key`). All whitespace is stripped; `ZUPER_WEBHOOK_SECRET` may be comma-separated. Bad/missing secret → **401**.
2. Event allowlist via `ZUPER_EVENT_ALLOWLIST` (default: `job.status_changed`, `job.updated`, `job.update`, `job.update_status`, `job.status_update`, `job.update_schedule`, `job.created`, `job.create`). Present events that are not listed → **200** `skipped: event_not_allowed`. **Missing/null `event` is not skipped on the allowlist** — the receiver still GETs the job and applies WOP/module filters. Zuper’s webhook UI uses human labels (Module = Jobs, Event like “Update Job Status” / “Job Status Changed”); `payload.event` may be the code form above. Keep the allowlist aligned with whatever string actually arrives — this receiver does not map UI labels. WOP filtering remains on **current job status after GET**, not on the event name.
3. Require `job_uid` (payload often nests under `data`). Missing → **400**.
4. `GET {ZUPER_BASE_URL}/api/jobs/{job_uid}` with `x-api-key`. Unwrap `data`.
5. Skip **200** `not_wop` unless **current** status is *Waiting on Parts* (case-insensitive). Live Get Job Details puts that on `current_job_status.status_name` (and similar nested fields). `job_status` is a **history array** and is not treated as current status.
6. Skip **200** `not_module` unless a line-item identifier matches `MODULE_SKU_PREFIXES` (default `0000675`). Carbon modules often use `product_id` / `product.product_id` rather than `sku` — both are accepted.
7. On match: build the notify payload and POST it to `SHOP_MANAGER_WEBHOOK_URL` and, if set, `PARTS_BOT_WEBHOOK_URL`. Fan-out failures are logged and returned in the JSON body but the HTTP status back to Zuper is still **200** (avoids retry storms).

`POST /dry-run` runs the same pipeline and returns the payload **without** fan-out.

## Notify payload

```json
{
  "source": "zuper-wop-notify",
  "zuper_event": "job.update_status",
  "received_at": "2026-09-14T20:00:00Z",
  "job_uid": "...",
  "job_number": "...",
  "title": "...",
  "status": "Waiting on Parts",
  "job_priority": "...",
  "parent_job_number": null,
  "is_frp_child": false,
  "latitude": null,
  "longitude": null,
  "gps_missing": true,
  "module_skus_found": [{"sku": "0000675", "qty": 1}],
  "freshness_note": "live Zuper API pull at notify time; NS→Zuper lag unknown"
}
```

`job_number` prefers Zuper `job_number` and falls back to `work_order_number`. GPS is taken from the job when present (`customer_address.geo_cordinates` and similar). `qty` is copied from the line item; if Zuper omitted quantity it is `null` rather than guessed.

## Local run

```bash
cd zuper-wop-notify
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill secrets — never commit .env
python webhook_receiver.py
```

Health check: `GET http://localhost:8080/health`

Tests:

```bash
cd zuper-wop-notify
pytest
```

## Deploy (gunicorn)

From this directory, with env vars injected by the host (do not bake secrets into the image):

```bash
gunicorn --bind 0.0.0.0:${PORT:-8080} webhook_receiver:app
```

Example systemd unit `ExecStart`:

```
/opt/zuper-wop-notify/.venv/bin/gunicorn --workers 2 --bind 0.0.0.0:8080 webhook_receiver:app
```

Working directory must be `zuper-wop-notify/` so `webhook_receiver:app` imports `filters`, `fanout`, and `zuper_api`.

## Zuper webhook setup (Sam / Carbon admin — exact clicks)

Create a **new** webhook. Do **not** edit or reuse existing webhooks (calendar-sync, KPI, or any other integration) — they stay untouched.

1. Log in to Zuper as an admin → gear icon → **Settings** → **Webhooks** (in some tenants this lives under Settings → Developer Hub / API & Webhooks → Webhooks).
2. Click **New Webhook** / **Add Webhook** (do not open an existing row).
3. **Name:** `wop-module-notify`.
4. **URL:** `https://<your-https-host>/zuper-webhook` (must be HTTPS).
5. **Events:** under **Module = Jobs**, subscribe at minimum to the status-change event (UI label like “Job Status Changed” / “Update Job Status” → payload code usually `job.status_changed` / `job.update_status`). Optionally also subscribe “Job Updated” and “Job Created” if status-change alone misses WOP transitions in this tenant.
6. **Write down the exact event string the Zuper UI shows** for each subscription. After the first real delivery, also check the service logs for the `payload.event` value that actually arrived. If either differs from the defaults, add the payload string to `ZUPER_EVENT_ALLOWLIST` — do not rely on a guessed name. (Missing/null events are never skipped on the allowlist; WOP matching always uses current job status after the GET.)
7. **Secret:** set the webhook secret/header to the same value as `ZUPER_WEBHOOK_SECRET`. This service reads the secret from the `x-webhook-secret` or `secret-key` / `Secret-Key` header (see `filters.webhook_secret_is_valid`). It does **not** use `X-Zuper-Signature` — that header belongs to other Carbon integrations; if the Zuper UI only offers a custom-header field, name the header `x-webhook-secret`.
8. Save. Zuper delivery to this service is one-way: the service only ever GETs job details back (API key with **read** access to Jobs in `ZUPER_API_KEY`; default base URL `https://us-east-1.zuperpro.com`).

## Deploy checklist

1. **HTTPS host up.** Vercel (below), or any host running `gunicorn --bind 0.0.0.0:8080 webhook_receiver:app` behind HTTPS. Inject env vars from `.env.example` via the host — never bake secrets into images.
2. **Health green:** `curl https://<host>/health` → `{"status": "ok", "service": "zuper-wop-notify"}`.
3. **Dry-run passes** (same pipeline, no fan-out):

```bash
curl -sS -X POST https://<host>/dry-run \
  -H "Content-Type: application/json" \
  -H "x-webhook-secret: $ZUPER_WEBHOOK_SECRET" \
  -d '{"event": "job.status_changed", "job_uid": "<real-module-WOP-job-uid>"}'
```

4. **Register the real webhook** in Zuper (section above) pointing at `https://<host>/zuper-webhook`.
5. **Paste back to CoS:** the HTTPS URL + the exact event name(s) from the Zuper UI, so the Grok Shop Manager / Parts Bot routines can be wired. Then fill `SHOP_MANAGER_WEBHOOK_URL` / `PARTS_BOT_WEBHOOK_URL`.

### Deploy on Vercel

`vercel.json` routes all paths to the Flask app as one Python serverless function. From `zuper-wop-notify/`: `vercel deploy --prod` (or the Vercel MCP/dashboard). Set the env vars from `.env.example` in Project → Settings → Environment Variables and redeploy. Production `*.vercel.app` URLs are public by default; preview URLs are usually behind Vercel Authentication, so point Zuper at the **production** URL.

## Verifying with one real module WOP job

1. Pick (or move) a real job with a `0000675*` module line item into **Waiting on Parts** in Zuper.
2. Watch the service logs. Expected outcomes per delivery:
   - Module WOP job → `Notified job_uid=... fanout=...` and the notify JSON above POSTed to the configured Grok URLs (HTTP 200 back to Zuper either way).
   - Job not currently WOP (noise) → 200 with `skipped: true, reason: "not_wop"`.
   - WOP job with no `0000675*` line item → 200 with `skipped: true, reason: "not_module"`.
   - Event not on the allowlist → 200 with `skipped: true, reason: "event_not_allowed"` (add the logged event string to `ZUPER_EVENT_ALLOWLIST` if it should notify).
3. No downstream URL wired yet? Use `POST /dry-run` with the job's `job_uid` (checklist step 3) — it returns the exact fan-out body without POSTing anywhere.

## Grok Bot webhook routine URLs

Fan-out is a JSON `POST` of the notify payload:

| Env var | Destination | Required |
| --- | --- | --- |
| `SHOP_MANAGER_WEBHOOK_URL` | Shop Manager Bot Grok **routine webhook URL** | Yes (for a successful notify) |
| `PARTS_BOT_WEBHOOK_URL` | Parts Bot Grok **routine webhook URL** | No — skipped if empty |
| `NOTIFY_TOKEN` | Sent as `X-Notify-Token` on those POSTs | No |

Paste the routine URLs from each Grok bot’s webhook/routine settings into those env vars. Optional `NOTIFY_TOKEN` is for bots that require a shared header token.

## Constraints

- **Read-only Zuper:** `zuper_api.py` exposes `get_job_detail` (HTTP GET) only.
- **No Google Calendar.**
- **Secrets via env only.** See `.env.example`. Never commit `.env` or API keys.
- **Fail loud:** missing `job_uid` or Zuper GET failure is an error; SKUs/qty that are not on the job are not fabricated.

## Meeting context

Waiting-on-Parts jobs were discussed as a gap for shop/parts automation (in-shop WOP not triggering the team board; Zuper-triggered replenishment when a module is on the job). This service is the unidirectional notify hop only — it does not order parts or mutate Zuper.
