# zuper-wop-notify

Thin **unidirectional** Flask service: Zuper webhook in → filter for module *Waiting on Parts* jobs → **GET-only** job detail from Zuper → JSON notify out to Shop Manager Bot + Parts Bot.

It never writes to Zuper (no PATCH/PUT/POST). It never talks to Google Calendar. It never invents stock or SKUs — only prefixes that actually appear on the live job are forwarded.

## Flow

1. Verify webhook secret (`x-webhook-secret` or `secret-key` / `Secret-Key`). All whitespace is stripped; `ZUPER_WEBHOOK_SECRET` may be comma-separated. Bad/missing secret → **401**.
2. Event allowlist via `ZUPER_EVENT_ALLOWLIST` (default: `job.status_changed`). Present events that are not listed → **200** `skipped: event_not_allowed`. **Missing/null `event` is not skipped on the allowlist** — the receiver still GETs the job and applies WOP/module filters. Zuper’s webhook UI uses human labels (Module = Jobs, Event like “Job Status Changed”); `payload.event` may be a code form. Keep the allowlist aligned with the exact payload string confirmed in the tenant — this receiver does not map UI labels. WOP filtering remains on **current job status after GET**, not on the event name.
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
  "zuper_event": "job.status_changed",
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

## Deploy (Vercel HTTPS preview/production)

This folder also includes a Vercel Python entrypoint at `api/index.py` and `vercel.json` so the same Flask app can run behind a Vercel HTTPS URL. Configure the Vercel project root directory as `zuper-wop-notify/`, then set the env vars from `.env.example`.

`GET /health`, `POST /dry-run`, and `POST /zuper-webhook` are the same routes as the gunicorn deployment.

## Deploy checklist

1. Deploy this folder behind an HTTPS host.
2. Set all env vars from `.env.example` on the host. `SHOP_MANAGER_WEBHOOK_URL` and `PARTS_BOT_WEBHOOK_URL` may be placeholders until CoS wires the Grok routines, but both should be populated for production fan-out.
3. Verify liveness: `GET https://<your-https-host>/health` returns `{"status":"ok","service":"zuper-wop-notify"}`.
4. Verify body shape without downstream fan-out: `POST https://<your-https-host>/dry-run` with the same shared-secret header and a Zuper-style payload containing `event` + `job_uid`.
5. Register the new Zuper webhook below.
6. Trigger or stage one real module job whose live status is **Waiting on Parts** and whose line items include a `0000675*` identifier. Expect `notified: true` and the JSON payload shown above; unrelated jobs should return `skipped: true` with `reason: not_wop` or `reason: not_module`.

## Zuper webhook setup

Create a **new** webhook for this bridge. Do not edit, reuse, or retarget existing calendar-sync, KPI, or other tenant webhooks.

1. In Zuper as a Carbon admin, go to **Settings → Webhooks**.
2. Click **Create Webhook** / **Add Webhook**.
3. Name it `wop-module-notify` (or another name that clearly identifies this Waiting-on-Parts module notify bridge).
4. Set the URL to `https://<your-https-host>/zuper-webhook`.
5. Set the shared secret to the same value as `ZUPER_WEBHOOK_SECRET`.
   - This service currently validates a literal shared-secret header named `x-webhook-secret`, `secret-key`, or `Secret-Key`.
   - If the Zuper UI shows a different header mechanism such as `X-Zuper-Signature`, confirm how that value is sent before enabling production traffic; the service should validate the same header name Zuper sends.
6. Subscribe under **Module = Jobs**.
   - Minimum event: **Job Status Changed** / `job.status_changed` (primary WOP transition path).
   - Optional, only if `job.status_changed` misses WOP transitions in this tenant: **Job Updated** / `job.updated` and/or **Job Created** / `job.created`.
7. Confirm the exact event string Zuper emits for the selected event(s). If the UI displays a machine event code, copy that value. Otherwise, capture the first dry-run/staged payload and copy `payload.event`.
8. Set `ZUPER_EVENT_ALLOWLIST` to those confirmed string(s), comma-separated. Do not leave guessed event names in production config.
9. Use an API key with **read** access to jobs. Put it in `ZUPER_API_KEY`. Default base URL is `https://us-east-1.zuperpro.com`.

## Grok Bot webhook routine URLs

Fan-out is a JSON `POST` of the notify payload:

| Env var | Destination | Required |
| --- | --- | --- |
| `SHOP_MANAGER_WEBHOOK_URL` | Shop Manager Bot Grok **routine webhook URL** | Yes (for a successful notify) |
| `PARTS_BOT_WEBHOOK_URL` | Parts Bot Grok **routine webhook URL** | Yes for production; skipped if empty before CoS wires it |
| `NOTIFY_TOKEN` | Sent as `X-Notify-Token` on those POSTs | No |

Paste the routine URLs from each Grok bot’s webhook/routine settings into those env vars. Optional `NOTIFY_TOKEN` is for bots that require a shared header token.
This service does not create or manage the Grok routines.

## Constraints

- **Read-only Zuper:** `zuper_api.py` exposes `get_job_detail` (HTTP GET) only.
- **No Google Calendar.**
- **Secrets via env only.** See `.env.example`. Never commit `.env` or API keys.
- **Fail loud:** missing `job_uid` or Zuper GET failure is an error; SKUs/qty that are not on the job are not fabricated.

## Meeting context

Waiting-on-Parts jobs were discussed as a gap for shop/parts automation (in-shop WOP not triggering the team board; Zuper-triggered replenishment when a module is on the job). This service is the unidirectional notify hop only — it does not order parts or mutate Zuper.
