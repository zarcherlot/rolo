"""Read values from the LeRobot integration manifest for CI and tests."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


MANIFEST = Path(__file__).resolve().parents[1] / ".ci" / "integrations" / "lerobot.yaml"


def load() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("get", "torch", "runtime"))
    parser.add_argument("key", nargs="?")
    args = parser.parse_args()
    data = load()
    if args.command == "get":
        if not args.key:
            parser.error("get requires a dotted key")
        value: object = data
        for part in args.key.split("."):
            if not isinstance(value, dict) or part not in value:
                raise SystemExit(f"manifest key not found: {args.key}")
            value = value[part]
        print(value)
    elif args.command == "torch":
        print(data["dependencies"]["torch"]["package"])
        print(data["dependencies"]["torch"]["index_url"])
    else:
        print("\n".join(data["dependencies"]["runtime"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
