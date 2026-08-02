# KHEPRI-AGENT: Khepri governance delegate

## What this authority is

`KHEPRI-AGENT` is software, not a person. It is the identifier under which an AI coding agent
working in this repository records approvals it performs under a delegation granted by the named
human authority, as Article VIII permits. A reader who encounters `approved_by: KHEPRI-AGENT` in a
registry entry or an approval package should understand that no human read and approved that
specific artifact; a human granted a delegation whose recorded scope covered it.

## Role

The delegate holds the `delegate` role and no other. It is `active`, and `human` is `false`.

Registration grants nothing. The delegate may approve only inside a delegation record that a human
instruction created, only within that record's recorded scope, and never inside the reserved set
defined in Article VIII: this constitution, the authorities registry including this document's own
registry entry, every delegation record, and the acceptance of any decision that alters that set.

## Credential and its limits

The delegate acts through the `Kemetra` GitHub credential, user id 206601658. That credential also
belongs to the human authority, Ahmed Shaaban, and is the account under which every approval comment
on this repository has been posted. GitHub authorship therefore cannot distinguish the delegate from
the authority.

This document exists because of that. The registry entry and the mandatory `approved_by` attribution
required by Article VIII are what the credential cannot supply: a record, inside the repository, of
which acts were performed by software. Recorded attribution is a declaration, not a proof. The
repository cannot detect a delegate that misattributes an approval to a human, nor one that
fabricates a delegation record, and Article VIII concedes both.

Restoring the human authority's commit signing key would make the distinction cryptographic rather
than declared. It is outstanding, and it matters most for the reserved set, where a delegate has no
authority at all and impersonation is the only route in.

## Revocation

The human authority revokes by saying so, by expiring or deleting the delegation record, or by
setting `active: false` on this authority's registry entry. Any of these takes effect immediately.
The delegate may not resist, defer, or condition a revocation, and may not modify this document, its
registry entry, or any delegation record.
