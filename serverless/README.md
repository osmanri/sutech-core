# Su-Tech — Telegram Serverless

Production bot: https://t.me/Su_Tech_bot

Mini App: https://app8796056339.tgcloud.ai/

The JavaScript bot, calculation engine, Mini App endpoints and persistent SQLite
database run on Telegram Serverless. Gemini and Open-Meteo remain external APIs.
The old Render service is suspended; do not resume it or run the Python bot with
production credentials, because its startup can overwrite Telegram's webhook.
The retired Python entry point now refuses startup before database or webhook
operations. An operator must explicitly set `SU_TECH_ENABLE_LEGACY_BOT=1` for a
controlled rollback; never do so while Serverless is active.

## Local operations

Run commands from `serverless/` with Node 18+ (tests use Node 24's SQLite):

```powershell
npm ci --ignore-scripts
npm test
npm run build
node cli.mjs fetch
node cli.mjs status
node cli.mjs push
node cli.mjs migrate --safe
node admin.mjs verify
```

The CLI wrapper loads `TGCLOUD_TOKEN` from ignored `../bot/.env`, passes it only
through the child environment, and redacts credential values in output. Never
enable CLI body debugging while provisioning or importing private data.

`admin.mjs` invokes temporary maintenance code with the authenticated management
API. It does **not** publish a maintenance endpoint. Gemini credentials are stored
in private database configuration, never in JS sources, static assets or model
prompts. Public endpoints accept the platform-verified Telegram user and scope all
queries to that user. A payload's `user_id` never determines the owner.

## Migration and recovery

- Private export: `.tgcloud/legacy-backup.json`, ignored by Git and protected by
  Windows ACLs. Its SHA-256 is
  `4445c4f1dc51a33ab05351d67cc8c2c2ecd62687e09fcc1ac06024ebc4bd8c22`.
- Imported 1,341 records including six language settings, one field, five
  calculation history entries, six AI answers and the original source records.
- `backup-legacy.py` refuses to overwrite its backup. The import uses
  `INSERT OR IGNORE`; rerunning it does not overwrite new user activity.
- The old PostgreSQL database is retained for recovery. Runtime code no longer
  connects to it.
- Older Vercel Mini App links redirect to the Telegram-hosted app, preserving the
  selected language and Telegram's signed fragment. The ordinary public landing
  page remains usable outside Telegram.

## Verification and boundaries

- 675 scenarios are compared with the original Python FAO-56.5 implementation.
- Additional tests cover cross-user access, concurrent quota reservations,
  duplicate updates, duplicate watering, language menus, stale AI replies,
  navigation generations, expired sessions and browser transport.
- Menus use one editable message per chat. A durable per-chat render lease and
  latest-view mailbox serialize fast taps; unrelated user saves preserve the
  message pointer. Expired callback acknowledgements do not stop navigation.
  Known old menus are removed after rendering; clicking an orphan menu registers
  it for cleanup. Telegram messages older than 48 hours have their buttons
  disabled when deletion is unavailable. Field and AI history stay in storage.
- `node admin.mjs ui-smoke` checks rendering against the real Telegram SQLite
  runtime with a temporary fake Bot API and an isolated, cleaned-up fixture owner.
  It sends no chat messages and makes no Gemini requests.
- AI: 20 attempted questions per user in a rolling 24-hour window. Chat reset
  does not reset this counter. Unrelated text is rejected before an API call.
- At most one extra provider attempt is made for HTTP 500/502/503/504. API keys,
  raw provider errors and photos are not written to chat history or logs.
- Photos provide preliminary symptom assessment. No field trial or hardware
  connection is fabricated.
- Field recommendations refresh when opened. Background scheduled notifications
  from the Python monitor have not been ported: the documented platform API has
  no scheduler. A gap between observations is shown, not filled with invented
  daily weather.
- Opt-in offer participation and report feedback remain available under More
  and on field cards. Deleting participation preserves fields and calculations.
- Deep analysis is selected for the next question/photo. If the stronger model
  is unavailable, one standard-model fallback is labelled in the answer.

Revoke the CLI key that was pasted into the conversation using BotFather's CLI
Access controls. Put the replacement directly in local `bot/.env`, never in chat.
Revoking a CLI deployment key does not replace the bot's Bot API token.
