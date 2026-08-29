<!-- status: active; authority: normative; owner: docs maintainers; last_reviewed: 2026-08-29 -->

# Episode revision history contract

Status: E7 server implementation available; contract remains candidate pending consumer acceptance

Capability: `workbench.episode-revision-history/v1`

Base: `workbench.episode-read-model/v1`

Implementation status: the control plane exposes the revision collection, revision-pinned detail
and revision-pinned timeline endpoints, and advertises `workbench.episode-revision-history/v1`.
The feature remains read-only and does not authorize replay, remediation or robot action.

## Purpose

E7 makes committed Episode revisions independently readable without weakening the
immutability or trust rules of the published Episode read model. It enables a consumer to
discover a bounded revision chain, pin detail to one revision, and page the matching
timeline. It does not compare revisions or assign a verdict.

## Public surface

### Revision collection

`GET /v1/robots/{robot_id}/episodes/{episode_id}/revisions`

The response uses `rolo-episode-revision-collection/v1` and contains bounded
`rolo-episode-revision-summary/v1` items ordered newest first. Each item exposes only:

- robot, Episode, revision, and immediate parent identity;
- committed time and current-revision marker;
- state, outcome, verification, coverage, and immutable status;
- event, asset, and finding counts;
- safe limitations and whether the source is a committed record or a legacy published
  projection.

The endpoint accepts `limit` from 1 through 100 and non-negative `offset`. The server
rejects symbolic links, unexpected filenames, more than 1,000 records, gaps, duplicate
revisions, records beyond the current publication, identity drift, digest drift, and
non-contiguous parent links.

An independently published E1 projection without committed records returns only its
current revision and an explicit limitation. It never invents missing history.

### Revision-addressed detail

`GET /v1/robots/{robot_id}/episodes/{episode_id}?revision={revision}`

Omitting `revision` preserves the existing current-detail behavior. A historical request
is reconstructed from the immutable committed record and returned through the unchanged
`rolo-episode-detail/v1` projection. A missing or future revision returns `409`; an unknown
Episode returns `404`.

### Revision-addressed timeline

`GET /v1/robots/{robot_id}/episodes/{episode_id}/timeline?revision={revision}`

The existing mandatory revision pin now resolves any available committed revision. Cursor
identity remains bound to robot, Episode, revision, and offset. Cross-revision cursors,
missing revisions, and malformed lineage fail closed.

## Producer semantics

- Immutability applies to each committed revision, not to the Episode identity forever.
- A producer may publish only the immediate successor of the current revision.
- The current published revision must have a committed parent record before it can be
  superseded; legacy projection-only Episodes therefore remain single-revision.
- Existing revision content remains immutable and digest-bound.
- The publication file remains the current-revision pointer; committed records are the
  historical source of truth.

## Trust boundary

Historical projection reuses all existing Episode sanitization and semantic validation:

- candidate causes remain `INFERRED / UNVERIFIED`;
- confidence, revision order, or repetition cannot promote authority;
- raw paths, URLs, prompts, payloads, credentials, secret content, and media bytes remain
  forbidden;
- stale or incomplete history is an integrity failure, not partial success;
- the API remains read-only and adds no replay, recollection, export, remediation, media,
  external handoff, or robot action.

## Consumer rule

rolo-vis must negotiate `workbench.episode-revision-history/v1` before showing a revision
selector or requesting historical detail. Same-Episode comparison may use two validated
revisions only after each side independently passes the existing detail and bounded
timeline checks. Deltas remain neutral `right - left` facts.
