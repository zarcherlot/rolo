"""Built-in Codex implementation of the provider-neutral downstream Stage SPI."""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from rolo.core.artifacts import ArtifactStore
from rolo.core.config import Settings
from rolo.core.hashing import sha256_file
from rolo.harness import HarnessError, HarnessRequest, configured_harness
from rolo.stages.agent_runner import OutputCallback, StageAgentTask
from rolo.stages.artifact_paths import ArtifactLayout, resolve_artifact_ref
from rolo.stages.handoffs import commit_diagnosis_handoff, commit_verification_handoff

Stage = Literal["diagnose", "verify"]
MAX_STAGE_INPUT_BYTES = 16 * 1024 * 1024
MAX_STAGE_INPUT_TOTAL_BYTES = 64 * 1024 * 1024
MAX_STAGE_INPUT_ARTIFACTS = 512


class CodexStageAgentExecutor:
    """Ask Codex for a strict result object and let Rolo materialize the handoff."""

    def __init__(
        self,
        *,
        artifacts: ArtifactStore,
        settings: Settings,
        stage: Stage,
    ) -> None:
        self.artifacts = artifacts
        self.settings = settings
        self.stage = stage

    def execute_stage(
        self,
        task: StageAgentTask,
        *,
        workspace: Path,
        on_output: OutputCallback | None = None,
    ) -> Mapping[str, str]:
        if task.stage != self.stage:
            raise ValueError(f"Codex Stage executor is bound to {self.stage}, got {task.stage}")
        local_inputs = self._materialize_inputs(task, workspace)
        prompt = self._prompt(task, local_inputs=local_inputs)
        if self.settings.coding_agent_preflight_url:
            from rolo.stages.network_preflight import preflight_agent_network

            preflight_agent_network(
                self.settings.coding_agent_preflight_url,
                timeout_s=self.settings.coding_agent_connect_timeout_s,
            )
        try:
            stdout, stderr, code = configured_harness(self.settings).run(
                HarnessRequest(
                    prompt=prompt,
                    workspace=workspace,
                    timeout_s=self.settings.coding_agent_timeout_s or 1800,
                ),
                on_output=on_output,
            )
        except HarnessError as exc:
            raise ValueError(str(exc)) from exc
        if code != 0:
            detail = stderr.strip() or stdout.strip() or f"Codex exited with code {code}"
            raise ValueError(detail[-2_000:])
        required = (
            {"frozen_config", "diagnosis_report"}
            if self.stage == "diagnose"
            else {"regression_report", "evidence_package"}
        )
        result = self._parse_result(stdout, required)
        run_id = f"codex-{task.plan_sha256[:16]}"
        if self.stage == "diagnose":
            diagnosis_report = self._prepare_diagnosis_report(
                task, self._mapping(result, "diagnosis_report"), run_id
            )
            handoff = commit_diagnosis_handoff(
                self.artifacts.root,
                task.robot_id,
                frozen_config=self._mapping(result, "frozen_config"),
                diagnosis_report=diagnosis_report,
                run_id=run_id,
            )
            return {
                "handoff": ArtifactLayout(self.artifacts.root).ref(
                    ArtifactLayout(self.artifacts.root).stage_file(
                        "diagnose", task.robot_id, "handoff.json"
                    )
                ),
                "frozen_config": handoff.frozen_config_ref,
            }
        handoff = commit_verification_handoff(
            self.artifacts.root,
            task.robot_id,
            regression_report=self._mapping(result, "regression_report"),
            evidence_package=self._mapping(result, "evidence_package"),
            run_id=run_id,
        )
        return {
            "handoff": ArtifactLayout(self.artifacts.root).ref(
                ArtifactLayout(self.artifacts.root).stage_file(
                    "verify", task.robot_id, "handoff.json"
                )
            ),
            "regression_report": handoff.regression_report_ref,
            "evidence_package": handoff.evidence_package_ref,
        }

    def _prepare_diagnosis_report(
        self, task: StageAgentTask, report: dict[str, object], run_id: str
    ) -> dict[str, object]:
        """Bind a strict report to an explicit, unverified observation artifact.

        A model can reason about supplied files but cannot safely mint an
        ``artifact://`` Episode reference in the canonical store. When it emits
        an otherwise valid strict report without one, Rolo records the model's
        observations plus the digest-bound inputs as an explicitly unverified
        observation artifact. This preserves the closed-loop contract without
        pretending that a target runtime episode was executed.
        """

        if report.get("schema_version") != "rolo-diagnosis-report/v1":
            return report
        enriched = dict(report)
        limitations = enriched.get("limitations")
        if not isinstance(limitations, list):
            limitations = []
        if enriched.get("decision") == "INCONCLUSIVE" and enriched.get("changes") == []:
            enriched["changes"] = [
                {
                    "kind": "NO_CHANGE",
                    "status": "NOT_APPLIED",
                    "applied": False,
                    "reason": "No target change was proposed or executed by the Diagnose Agent.",
                }
            ]
            limitations = [
                *[str(item) for item in limitations],
                "The Diagnose Agent proposed no target change; Rolo materialized an explicit "
                "NO_CHANGE record to preserve the closed-loop contract.",
            ]
        enriched["limitations"] = limitations
        refs = enriched.get("episode_refs")
        if isinstance(refs, list) and refs:
            return enriched
        input_refs = [
            ref for ref in task.input_refs.values() if ref.startswith("artifact://")
        ]
        if not input_refs:
            raise ValueError("strict diagnosis report requires an episode reference")
        layout = ArtifactLayout(self.artifacts.root)
        observation = {
            "schema_version": "rolo-diagnosis-agent-observation/v1",
            "robot_id": task.robot_id,
            "source_task_ref": f"artifact://diagnose/{task.robot_id}/runs/{run_id}/task.json",
            "source_input_refs": input_refs,
            "observations": report.get("observations", []),
            "hypotheses": report.get("hypotheses", []),
            "changes": enriched.get("changes", []),
            "authority": "UNVERIFIED_AGENT_OBSERVATION",
        }
        path = self.artifacts.write_json(
            f"diagnose/{task.robot_id}/runs/{run_id}/episodes/agent-observation.json",
            observation,
        )
        enriched["episode_refs"] = [layout.ref(path)]
        enriched["limitations"] = [
            *[str(item) for item in enriched["limitations"]],
            "No target runtime episode was executed; the bound artifact is an "
            "unverified agent observation.",
        ]
        return enriched

    def _materialize_inputs(self, task: StageAgentTask, workspace: Path) -> dict[str, str]:
        """Copy only digest-bound task inputs into the ephemeral Agent workspace.

        ``artifact://`` references are intentionally not meaningful to an external
        coding-agent CLI.  Resolving them here gives Codex/Claude-style plugins a
        concrete, read-only local context while keeping the canonical artifact tree
        outside the plugin's workspace.  The runner still validates every output and
        handoff after the plugin returns.
        """

        input_root = workspace / "rolo-stage-inputs"
        input_root.mkdir(parents=True, exist_ok=True)
        local_inputs: dict[str, str] = {}
        destinations: set[Path] = set()
        manifest: dict[str, dict[str, object]] = {}
        total_bytes = 0

        def copy_reference(
            reference: str, *, expected: str | None, label: str, depth: int = 0
        ) -> None:
            nonlocal total_bytes
            if reference in manifest:
                if expected is not None and manifest[reference]["sha256"] != expected:
                    raise ValueError(f"nested artifact hash mismatch: {label}")
                return
            if depth > 16 or len(manifest) >= MAX_STAGE_INPUT_ARTIFACTS:
                raise ValueError("Stage input artifact graph exceeds the recursion limit")
            source = resolve_artifact_ref(self.artifacts.root, reference)
            if not source.is_file():
                raise ValueError(f"Stage input artifact is missing: {reference}")
            size = source.stat().st_size
            if size > MAX_STAGE_INPUT_BYTES:
                raise ValueError(f"Stage input artifact exceeds the size limit: {reference}")
            total_bytes += size
            if total_bytes > MAX_STAGE_INPUT_TOTAL_BYTES:
                raise ValueError("Stage input artifact graph exceeds the total size limit")
            actual = sha256_file(source)
            if expected is not None and actual != expected:
                raise ValueError(f"nested artifact hash mismatch: {label}")
            relative = source.resolve().relative_to(self.artifacts.root.resolve())
            destination = input_root / "artifacts" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            manifest[reference] = {
                "local_path": str(destination),
                "sha256": actual,
                "size_bytes": size,
            }
            try:
                payload = json.loads(source.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return
            discover(payload, label=label, depth=depth + 1)

        def discover(value: object, *, label: str, depth: int) -> None:
            if isinstance(value, Mapping):
                for key, child in value.items():
                    child_label = f"{label}.{key}"
                    if isinstance(child, str) and child.startswith("artifact://"):
                        expected_key = (
                            f"{str(key)[:-4]}_sha256" if str(key).endswith("_ref") else None
                        )
                        expected_value = value.get(expected_key) if expected_key else None
                        expected = expected_value if isinstance(expected_value, str) else None
                        copy_reference(
                            child, expected=expected, label=child_label, depth=depth
                        )
                    else:
                        discover(child, label=child_label, depth=depth)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    child_label = f"{label}[{index}]"
                    if isinstance(child, str) and child.startswith("artifact://"):
                        copy_reference(
                            child, expected=None, label=child_label, depth=depth
                        )
                    else:
                        discover(child, label=child_label, depth=depth)

        for name, reference in task.input_refs.items():
            source = resolve_artifact_ref(self.artifacts.root, reference)
            if not source.is_file():
                raise ValueError(f"Stage input artifact is missing: {reference}")
            if source.stat().st_size > MAX_STAGE_INPUT_BYTES:
                raise ValueError(f"Stage input artifact exceeds the size limit: {reference}")
            expected = task.input_sha256.get(name)
            if expected is not None and sha256_file(source) != expected:
                raise ValueError(f"Stage input artifact hash mismatch: {name}")
            safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._") or "input"
            destination = input_root / f"{safe_name}.json"
            if destination in destinations:
                raise ValueError("Stage input names collide after workspace normalization")
            destinations.add(destination)
            shutil.copyfile(source, destination)
            local_inputs[name] = str(destination)
            copy_reference(
                reference,
                expected=expected,
                label=name,
            )
        manifest_path = workspace / "rolo-stage-inputs-manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "rolo-materialized-stage-inputs/v1",
                    "task_plan_sha256": task.plan_sha256,
                    "artifacts": manifest,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        local_inputs["__manifest__"] = str(manifest_path)
        (workspace / "rolo-stage-inputs.json").write_text(
            json.dumps(local_inputs, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return local_inputs

    def _prompt(
        self,
        task: StageAgentTask,
        *,
        local_inputs: Mapping[str, str] | None = None,
    ) -> str:
        expected = (
            '{"frozen_config": {...}, "diagnosis_report": '
            '{"schema_version":"rolo-diagnosis-report/v1", '
            '"robot_id":"...", "baseline": {...}, "observations": [...], '
            '"hypotheses": [...], "changes": [...], "smoke": {...}, '
            '"decision":"COMMIT|ROLLBACK|INCONCLUSIVE", "episode_refs": [...]}}'
            if self.stage == "diagnose"
            else '{"regression_report": {...}, "evidence_package": {...}}'
        )
        return (
            "You are a Rolo downstream lifecycle Agent. Rolo owns authorization, safety, "
            "artifact paths, hashes and release decisions. Read the supplied task references "
            "only; the same inputs are materialized under the local paths listed below. Do not "
            "mutate a target and do not claim release authority. Return exactly one "
            f"JSON object with this shape: {expected}. No markdown, prose, secrets, or paths "
            "outside artifact references. For Diagnose, episode_refs may be omitted when no "
            "runtime episode exists; Rolo will bind an explicitly unverified observation "
            "artifact. Diagnose changes must contain at least one record. When no target change "
            "was proposed or executed, return one explicit NO_CHANGE record with applied=false "
            "and use decision=INCONCLUSIVE.\n\n"
            "Materialized input paths:\n"
            + json.dumps(dict(local_inputs or {}), ensure_ascii=False, indent=2)
            + "\n\n"
            + json.dumps(task.model_dump(mode="json"), ensure_ascii=False, indent=2)
        )

    @staticmethod
    def _parse_result(stdout: str, required: set[str]) -> dict[str, Any]:
        candidates: list[str] = [stdout.strip()]
        for line in reversed(stdout.splitlines()):
            value = line.strip()
            if value:
                candidates.append(value)
            try:
                event = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                for key in ("text", "output_text", "message"):
                    nested = event.get(key)
                    if isinstance(nested, str):
                        candidates.append(nested.strip())
                item = event.get("item")
                if isinstance(item, dict):
                    nested = item.get("text")
                    if isinstance(nested, str):
                        candidates.append(nested.strip())
        for candidate in candidates:
            try:
                value = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and required.issubset(value):
                return value
            if isinstance(value, dict) and isinstance(value.get("result"), dict):
                nested = value["result"]
                if required.issubset(nested):
                    return nested
        raise ValueError("Codex Stage executor did not return a JSON object")

    @staticmethod
    def _mapping(result: Mapping[str, Any], key: str) -> dict[str, object]:
        value = result.get(key)
        if not isinstance(value, dict):
            raise ValueError(f"Codex Stage result field {key!r} must be a JSON object")
        return dict(value)
