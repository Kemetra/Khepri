"""The four `RRA-008` analysis families, each deriving facts from one package.

Four modules rather than one, because they share no code beyond the `RRA-004`
types they read and a single `analysis.py` would fail *Number of Functions in a
Single Module* and the mean-complexity threshold at once. Each exposes one
`derive(package)` returning facts or a refusal, so the pipeline treats them
uniformly, and each reconciles what it derives to the aggregate it read.

None of them computes an aggregate. `RRA-004` owns the fact package and
`RRA-008` excludes changing it, so a family that needs an aggregate the package
does not carry refuses rather than reconstructing one -- which is why
concentration and attach rate are gated on an `RRA-004` amendment.
"""
