<!-- status: active; authority: normative; owner: rolo maintainers; last_reviewed: 2026-08-31 -->

# Device Hardening Evidence Producer Contract

Rolo exports the sanitized `rolo-vis-device-hardening-evidence/v1` bundle with
`rolo target export-device-hardening`. The command is read-only and writes only
bounded JSON plus an optional release ledger. Without an audited external input,
all ten device scenarios remain `PENDING_EXTERNAL`.

## Contract and identity

The bundle contains `release_line`, the pinned `rolo_revision`, a deterministic
`producer_revision`, an opaque `target_id`, `target_kind` (`local` or `ssh`), and
one item per external scenario. A `VERIFIED` item must include OS, architecture,
a redacted package digest, opaque Job ID, gate result, timestamp, and summary.
`BLOCKED` and `PENDING_EXTERNAL` items carry no implied readiness.

The producer rejects duplicate or unknown scenarios, malformed revisions, unsafe
references (URLs, credentials, SSH/known-host data, paths, commands, or bytes),
and verified items without an audited input file. The generated
`rolo-release-ledger/v1` records the same identity tuple and preserves review
status, limitations, and failure state for each scenario.

## Reproducible export

```powershell
rolo target export-device-hardening `
  --target-id staging-target `
  --release-line 0.1.x `
  --output handoff/device-hardening.json `
  --ledger-output handoff/release-ledger.json
```

This command does not connect to a target, execute a Job, or promote external
evidence. The output is suitable for the rolo-vis validator only after the
controlled staging run supplies audited evidence.
