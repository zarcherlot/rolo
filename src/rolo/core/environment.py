from __future__ import annotations

from collections.abc import Collection, Mapping


def canonical_environment(
    source: Mapping[str, str], allowed: Collection[str]
) -> dict[str, str]:
    """Return a bounded, case-normalized environment with stable precedence.

    POSIX permits both ``HTTP_PROXY`` and ``http_proxy`` to coexist.  Callers
    pass environment variables to cross-platform tools using canonical upper
    case names, so an explicitly canonical variable must win regardless of the
    insertion order of ``os.environ``.
    """

    allowed_names = {name.upper() for name in allowed}
    environment: dict[str, str] = {}
    for key, value in source.items():
        canonical = key.upper()
        if canonical not in allowed_names:
            continue
        if canonical not in environment or key == canonical:
            environment[canonical] = value
    return environment
