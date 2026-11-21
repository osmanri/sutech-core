# Private recovery and deletion

Readiness Task 4. Quality rule: reproduce failures before fixing them, use a
synthetic recovery drill, verify the complete relevant suite and review the diff.

## What has been verified

The recovery tools were tested locally with artificial records, including a
field, deletion marker and quota timestamp. Encrypted export was decrypted and
restored into a **new local SQLite database**, with every durable row compared
and `PRAGMA integrity_check` passing. Wrong keys, modified/truncated ciphertext,
unknown versions/schema/engine, invalid rows/counts and duplicate ids are rejected.
An existing destination is never overwritten.

**Production database export and online restore have not been run.** There is no
configured scheduled encrypted backup or off-site retention job. The existing
`backup-live-bot.yml` saves code, not the database. The historical PostgreSQL
migration backup is a separate old copy, not proof of current database recovery.

## Format and protection

- Format `sutech-private-db`, version 1, schema 1, exact current engine version.
- Records and AI quota timestamps are captured by one SQLite statement, including
  column names. Unknown columns fail validation rather than being silently lost.
  Navigation/rendering leases and update receipts are omitted and restored empty.
- AES-256-GCM, a 32-byte random key, a fresh 12-byte nonce per export and a
  16-byte authentication tag. The header is authenticated too. Authentication
  must succeed before any plaintext is accepted or a recovery file is created.
  See [Node crypto](https://nodejs.org/docs/latest-v22.x/api/crypto.html).
- Limits: 16 MiB decoded JSON, 100,000 durable rows, 1 MiB per record body.
  This bounded tool refuses larger snapshots; it does not truncate them.
- The snapshot includes private configuration and may contain provider keys.
  Only encrypted backup bytes are written by export. Never log/decode them in CI,
  upload to a public artifact, commit a key or place recovery files in the site.
- Key/backup creation is exclusive, with mode 0600 and private directories on
  POSIX. Windows ACLs are inherited: verify that the chosen folder is accessible
  only to the operator before a real export. This has not been verified here.
  Keep an independently protected copy of the key; a lost key means no recovery.

## Operator commands

Use Node 22.13+ or Node 24, from `serverless/`:

```powershell
node backup.mjs keygen --key-file .tgcloud/keys/recovery.sutech-key
node backup.mjs export --key-file .tgcloud/keys/recovery.sutech-key --output .tgcloud/backups/current.sutech-backup
node backup.mjs restore-staging --key-file .tgcloud/keys/recovery.sutech-key --input .tgcloud/backups/current.sutech-backup --output .tgcloud/recovery/drill.recovery.sqlite
```

Export requires `TGCLOUD_TOKEN` already in the operator's environment. It uses
the authenticated management API with temporary local code; **no export endpoint
is deployed**. It does not read another checkout's credentials. API debug output
is disabled; only counts/version are printed. Keygen and staging restore are
offline and do not require credentials. None of these commands have been run
against real user data during this block.

The CLI rejects paths in publishable repository directories. `.tgcloud/`, key,
encrypted backup and recovery-file patterns are ignored by Git. Keep the key
separate from copies sent to private off-site storage. Staging databases contain
plaintext private records and require the same access protection as the source.

## Before any actual online recovery

Staging recovery is an inspection/drill result, not a deployment input. Do not
activate its restored UI/profile state, replay the old PostgreSQL import, or
upload raw rows to production. The one-time legacy importer now refuses to run
after lifecycle protection has been initialized.

Online recovery requires a separately reviewed cutover: stop writes, retain the
latest deletion markers and quota window, reconcile deletions after the snapshot,
clear old Telegram UI ids/drafts, verify platform import/rollback support and
compare the restored database before reopening access. An older snapshot can
contain subsequently deleted data. Do not use it to resurrect that content.
No production import/cutover capability is claimed by this tool.

## Deletion and minimal retained state

Deletion first rotates the owner's random epoch and marks deletion in progress.
Every business write captures its epoch before asynchronous work and checks it
inside its SQL statement. Old field/AI/feedback writes cannot borrow a fresh
account's epoch. Generations continue above the pre-deletion generation, so late
UI work cannot match a new session. Existing-field updates also require the row
to exist, preventing a refresh from recreating a deleted field.

User records and matching archived legacy rows are removed; this owner's active
leases are revoked. A host interruption leaves deletion blocked and the next
owner operation completes it. Completion is conditional on the same epoch, so
an older deletion attempt cannot finish a newer one incorrectly.

A minimal marker remains under owner 0: Telegram id in its key, random epoch,
deletion flag and generation seed. It contains no questions, answers, fields,
photos or coordinates. This is retained to fence stale work. The last 24 hours
of quota timestamps remain so erasure cannot bypass the daily limit. These
exceptions are described in the bot and RU/KZ/EN site privacy text.

The button acts on the current application database. Historical migration files,
the retired PostgreSQL copy, Telegram and provider copies need separate handling;
their deletion has not been verified. No old private backup was opened or removed
here. This limitation must not be presented as complete deletion of every copy.

## Operational retention

Cleanup is attempted on Telegram update activity, at most once per minute. It
is not a scheduler and failures do not discard the user's update. After inactivity,
expired records may remain until the next successful cleanup.

| Data | Cleanup cutoff |
|---|---|
| AI quota timestamps | 24 hours |
| AI conversation context | 30 minutes |
| Pending calculation input | 7 days |
| Update receipts | 7 days; older arbitrary replays are outside this deduplication window |
| Experimental classifier comparisons (no images) | 30 days |
| Shared weather cache | 24 hours |
| Expired leases | 90 seconds after expiry |
| Fields, saved reports/AI answers, lifecycle markers | Not automatically pruned |

Deletion/race tests verify other owners remain untouched, recent quota/receipt
records and active leases survive cleanup, and minimal deletion markers persist.
