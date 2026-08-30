# Rolo Verify provider staging template

Use this fixture to stage a real Verify provider before connecting robot hardware.

- Declare `stage = "verify"` so Rolo rejects accidental Diagnose binding.
- Accept only the immutable `StageAgentTask` and ephemeral workspace.
- Return artifact references only; Rolo validates that the files exist and owns the
  verification handoff.
- Stream informational output through `on_output`; never print credentials or claim release.

The provider is intentionally offline and deterministic. Replace its body with the real
regression runner only after the conformance and negative tests pass.
