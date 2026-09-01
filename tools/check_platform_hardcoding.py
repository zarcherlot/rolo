"""Guard the core runtime against accidental platform-specific hardcoding.

Integration tests and target profiles may mention external platforms, but the
``src/rolo`` runtime must remain provider-neutral.  A small, explicit
allowlist keeps the few compatibility/documentation references reviewable.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "src" / "rolo"
FORBIDDEN = (
    re.compile(r"\blerobot\b", re.IGNORECASE),
    re.compile(r"\blander\s*pi\b", re.IGNORECASE),
    re.compile(r"\blanderpi\b", re.IGNORECASE),
    re.compile(r"\bnav2_msgs\b", re.IGNORECASE),
    re.compile(r"\bnav2_bringup\b", re.IGNORECASE),
    re.compile(r"\b(?:controller|planner)_server\b", re.IGNORECASE),
    re.compile(r"\bbt_navigator\b", re.IGNORECASE),
)

# These are intentionally narrow: each exception has a compatibility or
# regression-prevention reason and must be reviewed when the file changes.
ALLOWLIST: dict[str, tuple[str, ...]] = {
    "stages/adapt/application_cli_mapping.py": ("lerobot-info",),
    "operation_contracts/app.yaml": ("nav2",),
}


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    text: str
    token: str


def _allowed(relative: str, line: str) -> bool:
    return any(
        relative == path and token.casefold() in line.casefold()
        for path, tokens in ALLOWLIST.items()
        for token in tokens
    )


def scan(root: Path = DEFAULT_ROOT) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(root.rglob("*.py")) + sorted(root.rglob("*.yaml")):
        relative = path.relative_to(root).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _allowed(relative, line):
                continue
            for pattern in FORBIDDEN:
                match = pattern.search(line)
                if match:
                    findings.append(Finding(path, number, line.strip(), match.group(0)))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    findings = scan(args.root.resolve())
    if not findings:
        print(f"platform hardcoding check passed: {args.root}")
        return 0
    for finding in findings:
        print(f"{finding.path}:{finding.line}: {finding.token}: {finding.text}")
    print(f"platform hardcoding check failed: {len(findings)} finding(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
