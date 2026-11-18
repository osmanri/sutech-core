# External services: guarantees and platform limits

Checked on 18 November 2026 against the live Telegram Serverless runtime, using
`@tgcloud/cli` 0.2.0 `run` with local probe code, without deploying or accessing
the database, messages or external providers.

## What the host actually supports

The probe returned `undefined` for `setTimeout`, `clearTimeout`,
`AbortController` and `AbortSignal`. No timer/cancellation globals were exposed.
The SDK exports `api`, `db`, `fetch`, `InputFile`, `FormData`, `BotApiError` and
`EndpointError`; it exposes no timer/configuration API.

The live `fetch` wrapper passes only URL, method, headers, prepared body and
redirect mode to the host. It uses the host's internal `fetchUpcallTimeout`;
this setting is not exposed to application code. Passing a Node/browser
`signal` or an invented `timeout` option would not enforce cancellation.

The [official SDK reference](https://core.telegram.org/bots/serverless#http)
documents HTTP and body readers, but no application-controlled request timeout.
The [official CLI](https://github.com/justwasm/tgcloud) documents `run` for
executing local code without deployment. Repeat capability checks after a
platform update; do not infer host behavior from Node tests.

## Application behavior

- Weather responses are accepted only within 15 seconds of starting HTTP,
  including reading the JSON body. Late responses are neither cached nor used
  to change a field. No automatic weather retry is started.
- A Gemini attempt has a 25-second response acceptance budget, including JSON.
  The whole AI operation has a 60-second budget before saving its answer,
  shorter than its 75-second lease. These are acceptance deadlines, **not
  interrupting timeouts**: a stalled SDK call still waits for the host.
- A provider request can be retried once after explicit HTTP 500/502/503/504.
  Deep mode can also fall back once to the standard model after HTTP 400/404.
  HTTP 429, 401/403, unknown network failures and elapsed responses do not
  trigger another automatic request. Retries share one application quota
  reservation; the provider may bill each HTTP attempt separately.
- Field/report writes check the current lease token in the database statement;
  nested updates also check the enclosing field-key lease.
  A delayed worker cannot commit after a retry has taken over its lease.
  AI writes additionally check the user's navigation generation and AI mode.
  Navigation suppresses late writes and display; it does not cancel HTTP.
- Changing field parameters rereads the field under its own lock after weather
  arrives. Soil checks/watering recorded during the wait remain in the log.
  A physical reset still starts a new balance at the reset time as before.
- Each calculation starts a new navigation generation; its pending-input write
  checks that generation, so old input/errors cannot replace a newer request.
  Calculation input is saved before requesting weather. A retry continues one
  field rather than adding its deficit again. Failed/cancelled AI input stays
  in the Telegram chat, including photos; it is not queued for UI cleanup.
  The farmer can resend it. Successful input is cleaned up after the answer
  has been saved. No additional photo storage was introduced.
- The optional plant classifier already refuses to start when timer functions
  are absent. Consequently it is unavailable on this checked host; Gemini's
  preliminary photo assessment is separate. This is not a classifier rollout.

## Remaining limit

Application code cannot guarantee a bounded wait or stop provider work on this
host. If an invocation is terminated by the host, the catch/finally blocks may
not run; saved calculation input and retained Telegram AI input remain, while
leases expire. An application-controlled hard timeout needs a supported SDK
feature or a separately operated HTTP gateway with a verified deadline. Neither
has been deployed or claimed here.

## Verification

`serverless/test/service-reliability.test.js` uses synthetic responses, controlled
clock advances and blocked database writes. It covers late headers/body,
preserved input/history, limited retries and quota use, duplicate submissions,
lease takeover, soil-check preservation and a new conversation during an AI
write. All 14 new scenarios, the full 1531-test JavaScript suite, 350 Python tests
and the build passed locally. Independent review findings were reproduced and
fixed. Existing integration tests cover navigation and repeated actual watering.
These are software failure scenarios, not measured provider uptime or field data.
