# zuper-wop-notify

Thin **unidirectional** Flask service: Zuper webhook in → filter for module *Waiting on Parts* jobs → **GET-only** job detail from Zuper → JSON notify out to Shop Manager Bot + Parts Bot.

It never writes to Zuper (no PATCH/PUT/POST). It never talks to Google Calendar. It never invents stock or SKUs — only prefixes that actually appear on the live job are forwarded.

## Flow

1. Verify webhook secret (`x-webhook-secret` or `secret-key` / `Secret-Key`). All whitespace is stripped; `ZUPER_WEBHOOK_SECRET` may be comma-separated. Bad/missing secret → **401**.
2. Event allowlist via `ZUPER_EVENT_ALLOWLIST` (default: `job.status_changed`, `job.updated`, `job.update`, `job.update_status`, `job.status_update`, `job.update_schedule`). Present events that are not listed → **200** `skipped: event_not_allowed`. **Missing/null `event` is not skipped on the allowlist** — the receiver still GETs the job and applies WOP/module filters. Zuper’s webhook UI uses human labels (Module = Jobs, Event like “Update Job Status” / “Job Status Changed”); `payload.event` may be the code form above. Keep the allowlist aligned with whatever string actually arrives — this receiver does not map UI labels. WOP filtering remains on **current job status after GET**, not on the event name.
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

## Zuper webhook setup

1. In the Zuper UI (Settings → Developer Hub / Webhooks), subscribe under **Module = Jobs** to events such as “Update Job Status” / “Job Status Changed” (human labels). `payload.event` may use the code form (`job.status_changed`, `job.updated`, `job.update`, `job.update_status`, `job.status_update`, `job.update_schedule`). Put the **payload string** in `ZUPER_EVENT_ALLOWLIST` if it differs — the receiver does not map UI labels. WOP matching still uses current job status after GET.
2. Create a webhook pointing at `https://<your-host>/zuper-webhook` (HTTPS).
3. Set the webhook secret to the same value as `ZUPER_WEBHOOK_SECRET`. This app accepts `x-webhook-secret` or `secret-key` / `Secret-Key`.
4. Use an API key with **read** access to jobs. Put it in `ZUPER_API_KEY`. Default base URL is `https://us-east-1.zuperpro.com`.
5. Subscribe to job update / status events only. This service ignores writes and will not change Zuper records.

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
