"""Detect normative prose that disarms itself when a lifecycle state changes.

`APP-021` corrected a family charter whose `Excludes` section carried:

    - Product implementation while this family remains proposed or its
      specifications remain draft.

Both conditions became false when the family went `active` and its first
specification was approved, so the exclusion stopped excluding anything at the
exact moment it was needed. No digest check can catch this: the document bytes
never change. The defect is that the rule's normative force is conditioned on a
state that flips beneath it.

This module flags that shape in normative sections only. Prose that merely
mentions a lifecycle state is not a defect; prose whose *obligation* is
conditioned on one is.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

GOVERNED_DOCUMENT_GLOBS = (
    "governance/families/*.md",
    "governance/specifications/*.md",
)

# Sections whose bullets carry normative force. A lifecycle mention in Context
# or Consequences prose describes; a mention in Excludes governs.
NORMATIVE_HEADINGS = ("excludes", "owns", "requirements", "constraints")

LIFECYCLE_STATES = (
    "proposed",
    "draft",
    "active",
    "accepted",
    "approved",
    "implemented",
    "verified",
    "retired",
    "rejected",
    "superseded",
)

_STATES = "|".join(LIFECYCLE_STATES)

# "while ... remains|is <state>" and "until ... is|are <state>".
CONDITION_PATTERN = re.compile(
    rf"\b(?:while|until|as long as|so long as)\b[^.]{{0,80}}?"
    rf"\b(?:remains?|is|are|stays?)\b\s+`?(?:{_STATES})`?",
    re.IGNORECASE,
)

# An author who has considered the flip and accepted it writes this inline.
SUPPRESSION_PATTERN = re.compile(
    r"<!--\s*lifecycle-ok:\s*(.+?)\s*-->", re.IGNORECASE | re.DOTALL
)

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass(frozen=True)
class LifecycleFinding:
    """One self-disarming rule, or one suppressed candidate."""

    path: str
    line: int
    heading: str
    text: str
    suppressed_reason: str | None = None

    @property
    def is_suppressed(self) -> bool:
        return self.suppressed_reason is not None

    def message(self) -> str:
        if self.suppressed_reason is not None:
            return (
                f"{self.path}:{self.line}: lifecycle-conditioned rule under "
                f"'{self.heading}' suppressed: {self.suppressed_reason}"
            )
        return (
            f"{self.path}:{self.line}: rule under '{self.heading}' is conditioned "
            f"on a lifecycle state and stops applying when that state changes; "
            f"state it against a real precondition instead"
        )


def _is_normative(heading: str) -> bool:
    normalised = heading.strip().lower().strip("`")
    return any(normalised.startswith(name) for name in NORMATIVE_HEADINGS)


def _strip_quotations(text: str) -> str:
    """Blank quoted spans so prose *describing* the defect is not flagged as one.

    `RCA.md` explains its corrected exclusion by quoting the defective form it
    replaced, and that quotation runs across two lines. Newlines are preserved so
    line numbers survive the substitution.
    """

    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    without_double = re.sub(r'"[^"]*"', blank, text, flags=re.DOTALL)
    return re.sub(r"[“][^”]*[”]", blank, without_double, flags=re.DOTALL)


def _bullet_span(lines: list[str], index: int) -> int:
    """Count continuation lines belonging to the bullet starting at ``index``.

    A bullet continues while following lines are indented and non-empty; a blank
    line, a new bullet, or a heading ends it.
    """
    span = 1
    for line in lines[index:]:
        stripped = line.strip()
        if not stripped or stripped.startswith(("-", "*", "#")):
            break
        if not line.startswith((" ", "\t")):
            break
        span += 1
    return span


def scan_text(path: str, text: str) -> list[LifecycleFinding]:
    """Return every lifecycle-conditioned rule in a document's normative sections."""
    findings: list[LifecycleFinding] = []
    heading = ""
    raw_lines = text.splitlines()
    scan_lines = _strip_quotations(text).splitlines()
    for index, line in enumerate(raw_lines, start=1):
        match = HEADING_PATTERN.match(line)
        if match is not None:
            heading = match.group(2).strip()
            continue
        if not _is_normative(heading):
            continue
        if not CONDITION_PATTERN.search(scan_lines[index - 1]):
            continue
        # A suppression comment may wrap onto following lines, so search from the
        # flagged line to the end of its bullet rather than the line alone.
        suppression = SUPPRESSION_PATTERN.search(
            "\n".join(raw_lines[index - 1 : index + _bullet_span(raw_lines, index)])
        )
        findings.append(
            LifecycleFinding(
                path=path,
                line=index,
                heading=heading,
                text=line.strip(),
                suppressed_reason=suppression.group(1) if suppression else None,
            )
        )
    return findings


def scan_document(root: Path, relative: str) -> list[LifecycleFinding]:
    path = root / relative
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return []
    return scan_text(relative, text)


def governed_documents(root: Path) -> list[str]:
    paths: list[str] = []
    for pattern in GOVERNED_DOCUMENT_GLOBS:
        directory, _, glob = pattern.rpartition("/")
        for path in sorted((root / directory).glob(glob)):
            paths.append(path.relative_to(root).as_posix())
    return paths


def scan_repository(root: Path) -> list[LifecycleFinding]:
    findings: list[LifecycleFinding] = []
    for relative in governed_documents(root):
        findings.extend(scan_document(root, relative))
    return findings


def lifecycle_condition_errors(findings: Iterable[LifecycleFinding]) -> list[str]:
    """Only unsuppressed findings are errors; suppressed ones are reported, not failed."""
    return [finding.message() for finding in findings if not finding.is_suppressed]
