# Meta Graph API Integration — رقيب (Raqib)

This document covers how Raqib connects to Facebook Pages, what it reads and writes,
and the platform limitations that shape the integration.

## 1. Permissions (OAuth scopes)

Raqib requests these scopes during the Meta OAuth2 consent flow
(`api/app/services/meta_oauth.py`):

| Scope | Needed for |
|---|---|
| `pages_show_list` | Discover the Pages the user manages |
| `pages_read_engagement` | Read conversations, messages, metadata |
| `pages_manage_metadata` | Page settings/verification fields |
| `pages_messaging` | Read inbox threads **and** send replies |
| `email` / `public_profile` | Identify the connecting user |

After the callback, Raqib **validates the granted scopes** and reports any missing
permission instead of silently degrading (`validate_scopes`). If Meta has not approved
`pages_messaging` for your app, connect succeeds but send operations are blocked —
the UI surfaces this clearly.

## 2. Token lifecycle

1. **Exchange** — authorization code → long-lived user token (server-side only,
   never exposed to the frontend, never logged).
2. **Encryption at rest** — tokens are encrypted with the app `SECRET_KEY` before
   storage in `page_connections.access_token_enc` (AES-GCM via `cryptography`).
3. **Refresh** — long-lived user tokens refresh via the Graph API
   (`/oauth/access_token?grant_type=fb_exchange_token`) before expiry; failures mark
   the connection inactive and surface in the Pages UI.
4. **Revoke/disconnect** — `DELETE` on the connection calls Meta's
   `/{user-id}/permissions?permission=pages_messaging` revoke path and rotates the
   stored token to garbage server-side.

## 3. Read path (ingestion)

- `GET /{page-id}/conversations?platform=messenger&limit=50` — paginated with
  `paging.cursors.after` + `paging.next`.
- Each conversation: `GET /{page-id}/conversations/{id}?fields=participants,messages…`
  (message pagination included).
- Raw payloads are stored via `StorageProvider` before any transformation, so
  reprocessing never needs a re-fetch.
- The import job rate-limits against the Graph API (Redis sliding window) and
  checkpoint-crawls the cursor so a crash resumes at the exact page it stopped at.

## 4. Write path (respond)

- Human-approved replies are sent with `POST /{page-id}/messages?recipient={psid}`
  (or the conversation-scoped send endpoint) from `api/app/services/meta_client.py`.
- Sending is idempotent per `AiResponse` row — retries never double-send.
- Response drafts are gated behind human approval in the inbox; the API never sends
  without an explicit approved decision.

## 5. Webhooks

Implemented in `api/app/services/meta_webhooks.py`:

- **Verification handshake** — `hub.mode`/`hub.verify_token`/`hub.challenge`
  (constant-time compare against `META_WEBHOOK_VERIFY_TOKEN`).
- **Signature verification** — `X-Hub-Signature-256` HMAC check against
  `META_APP_SECRET`; payloads are rejected on mismatch.
- **Event normalization** — `messages`/`message_deliveries`/`messaging_postbacks`
  normalized into internal events that mark conversations for re-import.

### Known limitation (documented honestly)

Webhook delivery requires:

1. A **public HTTPS endpoint** reachable from Meta's servers
   (`META_WEBHOOK_VERIFY_TOKEN` set, route exposed at `/api/webhooks/meta`).
2. A Meta app configured to subscribe to the page's `messages` webhook field.

Raqib implements the server side completely, but activation is operator-dependent:
you must configure the webhook URL in the Meta developer portal and complete the
verification handshake. Until then, the platform is **fully functional via polling
imports** (manual sync + scheduled re-import jobs) — webhooks are an optimization,
not a dependency.

## 6. Platform limitations we respect

- **Inbox access** — `pages_messaging` requires app review for production; during
  development it works in test mode with approved testers/roles.
- **Message history depth** — the Graph API returns inbox messages for the retention
  window Meta permits; older history may require business-messaging API access.
- **No fake fallback** — if Meta does not grant a capability, Raqib does not simulate
  it. The UI shows the missing permission and the exact scope to request.
- **Rate ceilings** — per-app/per-page call limits vary; Raqib's rate limiter is
  tunable (`META_RATE_LIMIT_*` settings) and retries with exponential backoff + jitter.

## 7. Testing without a Meta app

`api/sample_data/*.json` contains realistic Arabic conversations (Egyptian shop, Gulf
restaurant, Levantine support) with correct page-participant linkage. The **dev-only**
router (`/api/dev/...`, disabled when `APP_ENV=prod`) seeds these through the *same*
pipeline code path used for real imports — validation, dedupe, dialect, moderation,
quality, and dataset stages all execute for real. Only the fetch stage is substituted
with the sample files, exactly as it would be in an integration test.
