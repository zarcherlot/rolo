# Episode cohort read-model contract

Status: E8 implementation review candidate

Feature: `workbench.episode-cohort-read-model/v1`

Base: `workbench.episode-read-model/v1`

## Decision

E8 adds a bounded read model for reviewing a selected Episode revision against a clearly
defined population of other published Episodes. It answers which comparable records are
in scope and what descriptive values they contain. It does not decide whether a run
improved, regressed, passed, failed, became safer, or has a particular cause.

Media delivery, replay, recollection, export, external handoff, and robot action remain
outside this contract.

## Endpoint

```text
GET /v1/robots/{robot_id}/episode-cohorts
  ?reference_episode_id={episode_id}
  &reference_revision={revision}
  &window_days={7|30|90}
  &limit={1..100}
```

The server derives a mandatory closed-open window ending at the reference `started_at`:
`started_at - window_days <= member.started_at < reference.started_at`. The reference
revision may be current or historical but must pass the existing Episode detail
validation. The server derives both window and cohort identity from the reference; clients
cannot submit free-form timestamps, operation, test-case, or expected-behavior selectors.

## Cohort identity

V1 includes only records that match the reference exactly on all three fields:

- canonical `operation`;
- non-null `test_case_id`;
- non-null normalized `expected_behavior` text.

If the reference lacks any field, the request returns `409` instead of weakening the
identity. Matching is exact and deterministic; Agent inference, text similarity, task
labels, confidence, outcome, or verification cannot establish membership.

Each distinct `episode_id` contributes at most one member: its current published revision.
The reference Episode identity is outside the population even when the reference is
historical, so a single task cannot be counted twice through revision churn. Members must
be terminal and immutable. Running or mutable semantically matched publications inside
the window are counted in exclusions, not silently mixed into the cohort.

## Response

`rolo-episode-cohort/v1` contains:

- robot and reference Episode/revision identity;
- exact operation and test-case identity plus a SHA-256 expected-behavior digest;
- requested time window and server `as_of` timestamp;
- newest-first `rolo-episode-cohort-member/v1` items;
- `population_count`, `included_count`, `excluded_count`, and `truncated_count`;
- bounded exclusion counts for `RUNNING` and `MUTABLE`;
- `coverage` as `COMPLETE` or `BOUNDED_PARTIAL`;
- source kind and safe limitations.

Each member exposes only existing safe Episode summary facts plus `duration_ms` and
`evidence_count`. Outcome, verification, coverage, counts, and immutability remain
separate. No aggregate score, ranking, percentile, significance claim, release verdict,
or causal field is published in V1.

`included_count` equals the number of returned items. `excluded_count` equals the sum of
the exclusion categories. `population_count` equals included, excluded, and truncated
records. Any contradiction is an integrity failure.

## Bounds and ordering

- no pagination in V1; one request produces one review population;
- maximum 100 returned members and 1,000 scanned current Episode projections; exceeding
  the scan bound fails closed instead of publishing an unknowable population;
- newest `started_at` first, with `(episode_id, revision)` as deterministic tie-breakers;
- `BOUNDED_PARTIAL` whenever `truncated_count > 0`;
- duplicate identity, mixed robot, missing current publication, malformed timestamps,
  unsafe content, or count disagreement fails closed.
- raw artifact paths, signed URLs, credentials, prompts, and provider payloads remain
  forbidden public content.

The absence of pagination prevents clients from stitching different `as_of` populations
and presenting the result as one complete cohort.

## Authority boundary

- Outcome is the producer's execution outcome, not independent verification.
- Verification remains its existing separate field.
- Candidate causes and Agent events are not cohort membership or regression evidence.
- Numeric distributions computed by a consumer describe only returned members.
- A bounded or complete cohort cannot authorize release, remediation, or robot action.

## Acceptance gate

Implementation starts only after review confirms the exact cohort identity, current-only
member rule, 90-day/100-member bounds, no-pagination decision, and absence of verdict or
write authority.
