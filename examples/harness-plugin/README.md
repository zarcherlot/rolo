# Rolo harness plugin template

This minimal package shows how to add a Codex/Claude Code-compatible chat transport
without taking lifecycle or target authority.

1. Implement `ModelHarness.run(HarnessRequest, on_output=...)`.
2. Register a `settings=...` factory in the `rolo.harnesses` entry-point group.
3. Keep provider/model/API-key handling inside the harness and never persist secrets.
4. Run the fake-harness conformance test before enabling the plugin for users.

The harness may stream text, but Rolo remains responsible for confirmation, target
evidence, artifact publication, and release decisions.
