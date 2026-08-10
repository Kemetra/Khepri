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
# Any conditional introducer disarms the same way. Restricting this to "while"
# would let a one-word rephrasing ("if this family is proposed") bypass the gate.
INTRODUCERS = (
    "while",
    "until",
    "unless",
    "if",
    "when",
    "whenever",
    "as long as",
    "so long as",
    "for as long as",
    "before",
    "after",
    "once",
)

_INTRODUCERS = "|".join(sorted(INTRODUCERS, key=len, reverse=True))

# Bullets wrap, so this must tolerate newlines between the introducer and the
# state. It stops at a sentence boundary to avoid spanning unrelated clauses.
CONDITION_PATTERN = re.compile(
    rf"\b(?:{_INTRODUCERS})\b[^.]{{0,120}}?"
    rf"\b(?:remains?|is|are|stays?|becomes?|were|was)\b\s+`?(?:{_STATES})`?",
    re.IGNORECASE | re.DOTALL,
)

# An author who has considered the flip and accepted it writes this inline. The
# reason is mandatory: a bare marker would disable a fail-closed rule silently.
SUPPRESSION_PATTERN = re.compile(
    r"<!--\s*lifecycle-ok:\s*(\S.*?)\s*-->", re.IGNORECASE | re.DOTALL
)

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")

# Sentinel heading for a document that could not be read at all.
UNREADABLE_HEADING = "<unreadable>"


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
        if self.heading == UNREADABLE_HEADING:
            return (
                f"{self.path}: governed document could not be read as UTF-8 text "
                f"and cannot be checked for lifecycle-conditioned rules"
            )
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


BULLET_PATTERN = re.compile(r"^\s*[-*+]\s+")


def _bullet_end(lines: list[str], start: int) -> int:
    """Return the exclusive end index of the bullet beginning at ``start``.

    A bullet continues while following lines are indented and non-empty. A blank
    line, a new bullet, or a heading ends it — and the terminator is excluded, so
    a neighbouring bullet's suppression comment cannot disarm this one.
    """
    end = start + 1
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if not stripped or BULLET_PATTERN.match(line) or stripped.startswith("#"):
            break
        if not line.startswith((" ", "\t")):
            break
        end += 1
    return end


def scan_text(path: str, text: str) -> list[LifecycleFinding]:
    """Return every lifecycle-conditioned rule in a document's normative sections.

    Bullets are scanned whole rather than line by line: a Markdown wrap between
    an introducer and its state would otherwise bypass the gate on formatting
    alone.
    """
    findings: list[LifecycleFinding] = []
    heading = ""
    raw_lines = text.splitlines()
    document = _Document(path, raw_lines, _strip_quotations(text).splitlines())
    index = 0
    while index < len(raw_lines):
        line = raw_lines[index]
        match = HEADING_PATTERN.match(line)
        if match is not None:
            heading = match.group(2).strip()
            index += 1
            continue
        if not _is_normative(heading) or not BULLET_PATTERN.match(line):
            index += 1
            continue
        end = _bullet_end(raw_lines, index)
        finding = document.bullet_finding(heading, index, end)
        if finding is not None:
            findings.append(finding)
        index = end
    return findings


@dataclass(frozen=True)
class _Document:
    """One document's raw and quotation-stripped views, indexed identically."""

    path: str
    raw_lines: list[str]
    scan_lines: list[str]

    def bullet_finding(
        self,
        heading: str,
        start: int,
        end: int,
    ) -> LifecycleFinding | None:
        if not CONDITION_PATTERN.search("\n".join(self.scan_lines[start:end])):
            return None
        suppression = SUPPRESSION_PATTERN.search("\n".join(self.raw_lines[start:end]))
        return LifecycleFinding(
            path=self.path,
            line=start + 1,
            heading=heading,
            text=self.raw_lines[start].strip(),
            suppressed_reason=suppression.group(1) if suppression else None,
        )


def scan_document(root: Path, relative: str) -> list[LifecycleFinding]:
    """Scan one document, failing closed when it cannot be read.

    Constitution V: malformed data blocks progress. Treating an unreadable
    governed document as an empty clean one would let it pass unexamined.
    """
    path = root / relative
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return [
            LifecycleFinding(
                path=relative,
                line=1,
                heading=UNREADABLE_HEADING,
                text="",
            )
        ]
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
