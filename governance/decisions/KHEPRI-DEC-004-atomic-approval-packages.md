# KHEPRI-DEC-004: Atomic approval packages and bounded implementation authority

> Retired by KHEPRI-DEC-017. This document records the former approval model and is historical.

## Context

Khepri requires explicit named-human approval, but repeating one coherent approval decision
across related decisions, a family, and dependent specifications creates delay without adding
review quality.

## Proposed decision

Adopt digest-locked approval packages as structured evidence. One active human authority may
approve an exact, dependency-closed manifest once. Automation may then materialize only the
listed lifecycle transitions when the approved manifest digest and governed document digests are
unchanged.

Artifact registries remain authoritative for lifecycle state. A package never grants authority
by itself, and implementation within approved specifications needs no repeated product approval
unless a governed artifact changes.

## Consequences

- Packages fail closed on partial application, stale documents, missing dependencies, ambiguous
  renewal chains, or inconsistent evidence.
- Full governed documents are immutable under one approval; changes require explicit renewal.
- Automation calculates, validates, and materializes but never approves.
- Architecture/provider selection and beta launch authorization remain separately governed.

This decision remains proposed until exact traceable human approval is supplied.
