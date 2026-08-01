"""Local development wiring. Not governed, not production, not evidence.

Everything in this package exists so the RRA journey can be run end to end on a
developer's machine. None of it is authorized by `KHEPRI-DEC-005`, none of it is
deployed, and nothing it produces is approval or benchmark evidence.

**Why this is a separate package.** `AGENTS.md` restricts product code in
`khepri.rra` to specification-linked slices, and `KHEPRI-DEC-005` reserves
narrative provider selection to its own architecture decision. A local composition
root and a local deterministic narrator are neither, so they live here where what
they are is stated by the import path rather than inferred from a docstring.

**What this package must never do.** It must not fabricate a proof that a control
ran. The object store is the sharp example: `intake` requires
`encryption_algorithm == "aws:kms"` and the schema carries a CHECK constraint
enforcing it, so a local store returning that string over a plaintext file would
write a durable false claim into the database. Nothing here does that. Local
storage is a real S3-compatible endpoint performing real SSE-KMS, so the stored
row is true.
"""
