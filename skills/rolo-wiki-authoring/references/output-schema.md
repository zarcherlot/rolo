# Output contract

New writers use `rolo.stages.adapt.wiki_insights.RoloWikiInsightBundle`, whose schema version is fixed
to `rolo-wiki-insights/v1`. The wider `WikiInsightBundle` is the read boundary and accepts legacy
`robot-wiki-insights/v1` for one migration cycle. New output must never select the legacy version.

The contract bounds findings and unknown assessments, forbids extra fields, limits confidence to
`LOW`/`MEDIUM`, and can bind target, conformance, release and previous-Wiki identities. Optional v1
fields distinguish discovery paths, failure modes, mapping rationale, Adapter constraints,
limitations, reverification conditions and version differences. `AgentArtifactProvenance` records the
authoring skill, version, model and input hashes.

Schema validation is not evidence validation. The caller must resolve `basis` and counter-evidence
references against its allowlist, apply redaction independently, keep deterministic tables separate,
and ensure Wiki content does not enter eligibility, Catalog or release digests.
