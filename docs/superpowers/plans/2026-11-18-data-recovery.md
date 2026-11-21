# Readiness Task 4: data recovery and deletion

Goal: preserve a private, verifiable recovery path and prevent in-flight work from restoring deleted user data.

Spec: Task 4 in `docs/READINESS_PLAN.md`. Execute inline using Executing Plans.
Quality and regression evidence take priority over speed.

Decisions:

- Use the existing private records table for a minimal owner lifecycle marker; no production schema migration is required. Retain only owner id, random epoch, deletion state and generation seed. Explain this retention explicitly.
- Capture the epoch before asynchronous business work and check it atomically when writing. Deletion changes the epoch, blocks writes, removes user records and resumes safely if interrupted. An old invocation must never borrow the new epoch.
- Expire operational records on activity, with a lease to limit cleanup frequency. Do not silently delete field history or saved AI answers.
- Implement management-only encrypted snapshots. No backup endpoint or public artifact. Validate authenticated encryption, format, schema and engine versions before restoring to a new local SQLite database. Never overwrite an existing destination.
- Production export, online restore, scheduled encrypted backup and storage retention are not considered operational without separate real checks. This block uses synthetic data only; no user database is downloaded or restored.

Implementation and tests:

- [x] Reproduce late field/AI/feedback writes and interrupted deletion. Implement lifecycle fencing in store, business writers and rendering.
- [x] Test cleanup cutoffs, recent receipts and quotas, active leases and durable deletion markers. Attempt cleanup on activity.
- [x] Test encrypted export and restore with synthetic SQLite, tampering, wrong keys, unknown versions, duplicate rows, bad types and an existing destination. Add private export and staging restore tools.
- [x] Document private operation and platform limits. Independently review the changes and rerun regression tests after correcting the findings. Track deployment and CI in the release PR.
