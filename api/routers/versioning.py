"""Strict Semantic Versioning helpers used by release publishing and clients."""

from __future__ import annotations

import re
from typing import Optional


SEMVER_PATTERN = re.compile(
    r"^[vV]?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def parse_semver(value: str) -> Optional[tuple[tuple[int, int, int], tuple[str, ...]]]:
    match = SEMVER_PATTERN.fullmatch(str(value or "").strip())
    if not match:
        return None
    prerelease = tuple((match.group(4) or "").split(".")) if match.group(4) else ()
    if any(part.isdigit() and len(part) > 1 and part.startswith("0") for part in prerelease):
        return None
    return (
        (int(match.group(1)), int(match.group(2)), int(match.group(3))),
        prerelease,
    )


def compare_versions(left: str, right: str) -> Optional[int]:
    left_version = parse_semver(left)
    right_version = parse_semver(right)
    if left_version is None or right_version is None:
        return None
    if left_version[0] != right_version[0]:
        return 1 if left_version[0] > right_version[0] else -1
    return _compare_prerelease(left_version[1], right_version[1])


def _compare_prerelease(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    for left_part, right_part in zip(left, right):
        if left_part == right_part:
            continue
        left_numeric = left_part.isdigit()
        right_numeric = right_part.isdigit()
        if left_numeric and right_numeric:
            return 1 if int(left_part) > int(right_part) else -1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return 1 if left_part > right_part else -1
    if len(left) == len(right):
        return 0
    return 1 if len(left) > len(right) else -1
