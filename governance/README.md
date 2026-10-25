# Governance

Khepri uses a minimal governance model for a repository with one owner.

## Authority

Ahmed Shaaban is the sole repository owner and decision authority. Work on branches and pull
requests is proposed. A repository change becomes approved when the owner merges it to `main`;
the Git record is the evidence. Product decisions and specifications created after Constitution
3.0.0 are approved when the owner records them **Approved** on a canonical Confluence page in space
KHEPRI. [`ATLASSIAN-TRANSITION.md`](ATLASSIAN-TRANSITION.md) states the record conventions and maps
every legacy identifier to the home of its authority.

## Source of truth

[`registry.yaml`](registry.yaml) is the authoritative index of the artifacts it lists. It lists no
Confluence record. Each entry contains:

- `type`: `decision`, `family`, or `specification`;
- `id`: unique stable identifier;
- `state`: `active` or `retired`;
- `document`: one repository-relative Markdown document;
- `depends_on`: known artifact identifiers;
- `superseded_by`: optional active successor for a retired artifact.

A specification depends on exactly one family. An active artifact cannot depend on a retired one.
Markdown explains intent but cannot override registry state.

## Workflow

1. Create a branch.
2. Edit the governed document and registry entry together.
3. Run `uv run khepri-gov validate`, `uv run ruff check .`, and `uv run pytest`.
4. Review the pull request as a complete, independently verifiable slice.
5. The owner merges it to `main`, approving that repository change.

This workflow covers repository changes and the artifacts the registry lists. A new product
decision or specification is not added to the registry; it is approved on its Confluence record
and cited by page and version from the pull request that implements it (Constitution II, IV).
A decision or specification first listed after Constitution 3.0.0 admits no product code unless it
only retires or amends a listed artifact.

Drafts do not live in the registry on `main`. Retired artifacts remain as context and may name an
active successor. Removed approval and delegation records remain available in Git history rather
than an archive directory.

## Validator

`uv run khepri-gov validate` reports all safely discoverable errors and exits non-zero for unknown
schemas or fields, invalid values, missing documents, duplicate identities, dependency defects,
family-link defects, or invalid supersession. It never grants approval.

## Templates

Use the decision, family, and specification templates only as concise writing aids. Adding a
document without its registry entry does not make it governed.
