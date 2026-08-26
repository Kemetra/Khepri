"""The browser journey carries the source contract, or the operator is stranded.

`POST /api/v1/beta/profile` requires a `source_contract` under
`rra003.mapping.v3`, deliberately with no default: "a request without a
declaration is refused rather than profiled on inferred semantics". The browser
client posted `{requested_semantics: []}`, so every web upload answered 422 and
left the operator on the upload page with a message about a malformed body they
never wrote.

**Why these tests are not browser tests.** The regression is a *payload shape*
mismatch between a JavaScript object literal and a Pydantic model. A
`@pytest.mark.browser` test skips wherever the pinned Chromium is absent, which
is most machines and every environment that has not fetched it -- so
browser-only coverage of this seam would report success by not running. The
tests here read the shipped asset and the shipped template, derive the
declaration the client actually collects, and push it through the *real* request
model. They fail on the machine that has no browser, which is the point.

**What is deliberately not asserted: a destination.** `MAPPING_VERSION` is
`rra003.mapping.v2` while this lands, so the pairing is still admitted and a
normal upload profiles through. Later in this slice the pairing becomes
unlisted, `packages.py` refuses, and the journey reaches a governed refusal
instead. A test asserting "the operator reaches the review page" would pass now
and fail then, for a reason that is not a regression. So what is asserted is the
seam: the declaration reaches the server and is accepted by the model, and no
422 is returned. That is true on both sides of the version move.
"""

from __future__ import annotations

import json
import re
from importlib.resources import files

import pytest
from pydantic import ValidationError

from khepri.rra.journey.copy import JOURNEY_COPY
from khepri.rra.profile_request import ProfileRequestBody
from khepri.rra.source_contract import ContractRefused, SourceContractBody
from tests.test_rra003_api import harness as api_harness
from tests.test_rra003_api import redeem_and_consent, upload
from tests.test_rra_journey_api import client

#: The declarations `build_source_contract` refuses to infer. Each is a decision
#: `RRA-003` says the data cannot make about itself, so each has to be a control
#: the operator can see and set -- not a field left to a model default, which the
#: source-contract module names "an inference wearing a configuration's clothes".
OPERATOR_DECLARED_FIELDS = (
    "contract_id",
    "evidence",
    "sale_only",
    "posted_only",
    "currency_code",
    "unique_line_grain_attested",
    "transaction_id_column",
    "transaction_id_unique_package_wide",
    "revenue_vat_exclusive",
    "revenue_is_net_of_returns",
    "units_are_integral",
    "cost_is_extended",
    "discount_is_additive",
)


def journey_asset(name: str) -> str:
    return files("khepri.rra.journey").joinpath("assets", name).read_text(
        encoding="utf-8"
    )


def upload_template(language: str = "en") -> str:
    """The upload page as an operator receives it, rendered by the real route.

    The *rendered* page rather than the template source, because the controls are
    emitted from a Jinja loop: reading the source would see `{{ field }}` and
    measure nothing. Rendering also proves the copy keys resolve -- the
    environment uses `StrictUndefined`, so a label naming a key that does not
    exist raises here instead of shipping a blank label.
    """
    return client().get(f"/beta/{language}/upload").text


def declared_field_names() -> set[str]:
    """The contract field names the shipped upload form actually carries.

    Read off the page rather than restated, so a control renamed in the markup
    and left stale in the script is a failure here instead of a 422 in front of
    an operator.
    """
    return set(re.findall(r'data-contract-field="([a-z_]+)"', upload_template()))


def test_the_upload_form_collects_every_declaration_rra003_refuses_to_infer() -> None:
    """Each governed semantic is a control on the page, not a model default.

    A form that collected two identifiers and let `SourceContractBody` default
    the rest would post a declaration the *client* composed. It would validate,
    profile, and be indistinguishable downstream from one the operator chose --
    which is exactly the inference `RRA-003` refuses. So the test is that every
    refusable declaration is present as a field the operator can set.
    """
    declared = declared_field_names()
    for field in OPERATOR_DECLARED_FIELDS:
        assert field in declared, f"the upload form never collects {field}"


def test_every_collected_field_is_a_field_the_wire_model_accepts() -> None:
    """No control invents a key: `extra="forbid"` turns a typo into a 422.

    `SourceContractBody` forbids extra keys deliberately -- a misspelled
    `revenue_vat_inclusive` must not silently yield the default basis. That
    makes a mislabelled control on the page a 422 rather than a wrong report,
    and this is the test that catches it before an operator does.
    """
    accepted = set(SourceContractBody.model_fields)
    for field in declared_field_names():
        assert field in accepted, f"the form collects {field}, which the model forbids"


#: Accepted by `SourceContractBody` and deliberately not on the form yet. Each is
#: the column-mapped branch of a rule whose package-level branch the form does
#: collect, so declining one of those claims currently leads to a refusal the
#: operator cannot act on. Recorded as a literal so the gap is a stated,
#: reviewable boundary of this slice rather than an accident: a later slice adding
#: a control has to shorten this list, and that failure is the reminder.
UNCOLLECTED_WIRE_FIELDS = frozenset(
    {
        "event_kind_column",
        "status_column",
        "currency_column",
        "event_key_columns",
        "transaction_key_components",
    }
)


def test_the_uncollected_declarations_are_exactly_the_known_gap() -> None:
    """The form's boundary, pinned so it cannot widen unnoticed.

    A control added to the page must shrink this set, and a field added to the
    wire model must be either collected or listed here. Without this, the next
    accepted-but-uncollectible field arrives silently and an operator meets a
    governed refusal with no control to resolve it.
    """
    accepted = set(SourceContractBody.model_fields)
    assert accepted - declared_field_names() == UNCOLLECTED_WIRE_FIELDS


@pytest.mark.parametrize(
    ("claim", "refusal_message"),
    [
        ("sale_only", "must map or declare event kind; it is never inferred"),
        ("posted_only", "must map or declare status; it is never inferred"),
        (
            "unique_line_grain_attested",
            "must supply event keys or attest unique line grain",
        ),
        (
            "transaction_id_unique_package_wide",
            "transaction identifier not proven unique needs a composite key",
        ),
    ],
)
def test_declining_a_package_level_claim_needs_a_column_the_form_lacks(
    claim: str,
    refusal_message: str,
) -> None:
    """Why the gap above matters, stated as behaviour rather than as a field list.

    Each of these four checkboxes reads as a choice, but the form offers no
    control for the column that `RRA-003` requires instead when the claim is
    declined. So unticking one is currently a governed refusal with no remedy on
    the page. The refusal is correct -- the rule is doing its job -- and it is
    the *collection surface* that is incomplete, which is what this records.

    **Each claim is pinned to the message it actually produces.** A bare
    `raises(ContractRefused)` would be satisfied by any refusal at all, so a
    fixture regression that blanked `contract_id` would make all four
    parametrisations pass on "must record its identifier" -- proving nothing
    about the checkbox each one is named for.
    """
    declared = client_profile_payload()["source_contract"]
    assert isinstance(declared, dict)

    with pytest.raises(ContractRefused, match=refusal_message):
        SourceContractBody(**{**declared, claim: False}).to_contract()


def test_the_currency_control_makes_a_lowercase_code_hard_to_send() -> None:
    """A correctable typo must not cost a session.

    `_assert_iso_currency` refuses anything but three uppercase letters, and on
    the resume path that refusal costs the whole session rather than the field
    (a resubmit re-runs `upload()`, which answers 409 for a session that already
    has an upload). So the mistake is prevented at the control instead of
    reported after it: the browser blocks a non-three-letter value, the field
    displays what it will send, and the client uppercases the value on its way
    into the payload.

    The CSS transform alone would be cosmetic -- it changes the rendering, not
    the submitted string -- so the normalisation in `declaration()` is the part
    that actually prevents the refusal, and it is asserted here.
    """
    page = upload_template()
    assert 'pattern="[A-Za-z]{3}"' in page
    # The rule is legible before the mistake, not only in a validation bubble.
    assert 'aria-describedby="contract-currency-hint"' in page
    assert 'id="contract-currency-hint"' in page
    css = files("khepri.rra.journey").joinpath("assets", "journey.css").read_text(
        encoding="utf-8"
    )
    assert "#contract-currency-code { text-transform: uppercase; }" in css
    # The invalid state is a token, never a literal: `R8-01` censused every hex
    # below `:root` and `R8-02` only removes from that census. A new literal here
    # failed `test_the_orphan_value_count_does_not_grow` in fix round 1.
    invalid_rule = next(
        line
        for line in css.splitlines()
        if line.startswith("#contract-currency-code:invalid")
    )
    assert "var(--danger)" in invalid_rule
    assert "#" not in invalid_rule.split("{", 1)[1], (
        "the invalid state must use a token, not a hex literal"
    )
    # Colour is not the only signal: the border also thickens, so the state
    # survives a monochrome display and colour blindness.
    assert "border-width" in invalid_rule
    # And the value actually sent is normalised, which the CSS cannot do.
    script = journey_asset("upload.js")
    assert "toUpperCase()" in script


def test_a_lowercase_currency_would_be_refused_if_it_reached_the_server() -> None:
    """Why the control is hardened: the server has no tolerance to fall back on.

    This pins the server's rule so the prevention above cannot be quietly
    dropped as unnecessary. `SourceContractBody` accepts the string as a string;
    it is `to_contract()` that refuses it, which is exactly the 400 an operator
    would otherwise meet after submitting.
    """
    declared = client_profile_payload()["source_contract"]
    assert isinstance(declared, dict)

    with pytest.raises(ContractRefused, match="uppercase ISO 4217 code"):
        SourceContractBody(**{**declared, "currency_code": "egp"}).to_contract()


def test_the_payload_the_client_posts_satisfies_the_real_request_model() -> None:
    """The regression, asserted against the model rather than against a string.

    This is the failure that stranded every web upload: the client posted
    `{requested_semantics: []}` and `ProfileRequestBody` answered
    `source_contract  Field required`. Building the client's own payload shape
    and validating it here fails the moment the client stops sending a
    contract, on a machine with no browser.
    """
    payload = client_profile_payload()

    body = ProfileRequestBody(**payload)

    assert body.source_contract.contract_id
    # The declaration is complete enough to build a governed contract, so the
    # route answers 201 rather than the 400 an unproven semantic earns.
    contract = body.source_contract.to_contract()
    assert contract.digest


def client_profile_payload() -> dict[str, object]:
    """The body the shipped `upload.js` composes, with the form filled in.

    The keys come from the template's controls; the values are stand-ins for
    what an operator types. This is a shape test, so the values only have to be
    the right *type* and a complete declaration -- what matters is that every
    key the model requires is present and no key it forbids is.
    """
    return {
        "requested_semantics": [],
        "source_contract": {
            "contract_id": "src_operator_1",
            "evidence": "Declared by the operator on the upload page.",
            "sale_only": True,
            "posted_only": True,
            "currency_code": "EGP",
            "unique_line_grain_attested": True,
            "transaction_id_column": "invoice_no",
            "transaction_id_unique_package_wide": True,
            "revenue_vat_exclusive": True,
            "revenue_is_net_of_returns": False,
            "units_are_integral": True,
            "cost_is_extended": True,
            "discount_is_additive": True,
        },
    }


def test_the_clients_own_payload_is_accepted_by_the_running_route() -> None:
    """The regression, closed at the seam it actually broke at: the HTTP route.

    The model test above proves the shape validates; this proves the *route*
    accepts it, through session, consent, and upload, exactly as the browser
    reaches it. The assertion is deliberately "not a 422" rather than a status
    code or a destination: `MAPPING_VERSION` moves later in this slice, and when
    the pairing becomes unlisted this request earns a stated governed refusal
    instead of a profile. That is a different outcome, not a regression -- but a
    422 from a missing declaration is the defect either way, so that is what is
    pinned.
    """
    test = api_harness()
    redeem_and_consent(test)
    upload(test)

    response = test.client.post(
        "/api/v1/beta/profile",
        json=client_profile_payload(),
    )

    assert response.status_code != 422, response.text
    # The declaration was read, not merely tolerated: a well-formed body whose
    # declaration is incomplete earns 400, and this one is complete.
    assert response.status_code == 201, response.text


def test_an_empty_form_earns_a_stated_refusal_rather_than_a_422() -> None:
    """What the resume path posts on a fresh load, and why it is safe.

    `bootstrap()` posts the declaration as it stands, which on a fresh load is
    blank. That must not be a 422 about malformed JSON, and it must not be
    profiled on defaults: it is a 400 whose body states what is missing, which
    is what the client now shows the operator. This is the test that keeps that
    branch a governed refusal instead of either failure mode.
    """
    test = api_harness()
    redeem_and_consent(test)
    upload(test)
    response = test.client.post("/api/v1/beta/profile", json=blank_form_payload())

    assert response.status_code == 400, response.text
    # A reason the client can show, not an empty refusal.
    assert response.json()["detail"]


#: The two declarations `SourceContractBody` types as a bare `str`. A blank one
#: has to travel as "" rather than null: null is a schema violation and answers
#: 422, which is the failure this whole task exists to remove.
REQUIRED_TEXT_FIELDS = ("contract_id", "evidence")


def untouched_value(name: str, filled: object) -> object:
    """What one control contributes when the operator never touches it.

    An unticked checkbox is `False`; a blank required identifier is `""`, which
    reaches the governed refusal; a blank optional column is null, which the
    server reads as "not declared by column".
    """
    if isinstance(filled, bool):
        return False
    return "" if name in REQUIRED_TEXT_FIELDS else None


def blank_form_payload() -> dict[str, object]:
    """What `declaration()` builds from controls the operator never touched.

    Derived from the same source of truth as the filled payload, so the two
    cannot disagree about which fields exist.
    """
    filled = client_profile_payload()["source_contract"]
    assert isinstance(filled, dict)
    contract = {name: untouched_value(name, value) for name, value in filled.items()}
    return {"requested_semantics": [], "source_contract": contract}


def test_a_blank_required_field_travels_as_empty_text_not_as_null() -> None:
    """The trap this fix has to avoid on its way past the original 422.

    `contract_id` and `evidence` are typed `str`, so a client sending null for
    an untouched box reproduces the exact 422 it was meant to eliminate -- just
    with a different message. The client marks those controls and sends "" for
    them, which reaches the governed refusal instead. This pins the distinction
    at both ends: the client's rule, and the model's answer to each form.
    """
    script = journey_asset("upload.js")
    assert "contractRequired" in script
    for field in REQUIRED_TEXT_FIELDS:
        assert f'data-contract-field="{field}" data-contract-required' in (
            upload_template()
        ), f"{field} is not marked as required text"
    # Null is a schema violation; the empty string is a declaration that is
    # incomplete, which is a different and reportable thing.
    with pytest.raises(ValidationError):
        SourceContractBody(contract_id=None, evidence=None)
    with pytest.raises(ContractRefused):
        SourceContractBody(contract_id="", evidence="").to_contract()


def test_a_request_without_a_declaration_is_still_refused() -> None:
    """The fix must not have added a default on the way past the regression.

    The whole slice rests on the contract being required. A client fixed by
    giving the model a default would make these tests pass and defeat
    `RRA-003`, so the refusal is asserted here beside the fix.
    """
    with pytest.raises(ValidationError, match="source_contract"):
        ProfileRequestBody(requested_semantics=[])


def test_both_profile_call_sites_send_the_collected_contract() -> None:
    """The submit path and the resume path, because one fix leaves half broken.

    `upload.js` posts a profile from two places: the form's submit handler and
    `bootstrap()`'s resume branch, which fires when an upload landed but its
    profile response was lost. A contract added only to the submit handler
    leaves every interrupted upload answering 422.
    """
    script = journey_asset("upload.js")
    posts = re.findall(r'api\("/api/v1/beta/profile"[^\n]*', script)
    assert len(posts) == 2, "upload.js should post a profile from exactly two places"
    # Both bodies come from the one builder, so neither can drift from the other
    # and a contract cannot be added to one path and forgotten on the other.
    for post in posts:
        assert "profileRequest()" in post, f"a profile POST carries no contract: {post}"
    # And that builder is what actually names the field the route requires.
    builder = re.search(r"const profileRequest = [^\n]*", script)
    assert builder is not None, "upload.js has no single profile-body builder"
    assert "source_contract" in builder.group()
    assert "declaration()" in builder.group()


def test_no_contract_declaration_is_hardcoded_in_the_client() -> None:
    """A literal declaration in the asset is the inference `RRA-003` refuses.

    The values must be read out of the operator's controls at post time. A
    contract spelled out in JavaScript would be the client declaring what the
    file means, which is the defect this slice exists to remove -- and it would
    pass every other test in this module.
    """
    script = journey_asset("upload.js")
    # Asserted positively: every value is read off a control the operator sees.
    # An absent-prefix check alone would pass a script that hardcoded any other
    # identifier, so what is asserted is where the values come from.
    assert "[data-contract-field]" in script
    assert "control.dataset.contractField" in script
    assert "control.checked" in script and "control.value" in script
    # No declaration is spelled out here, in either half of the payload.
    for governed in ("sale_only", "posted_only", "revenue_vat_exclusive"):
        assert f'"{governed}"' not in script, f"{governed} is hardcoded in the client"
        assert f"{governed}:" not in script, f"{governed} is hardcoded in the client"


def test_the_error_path_keeps_the_servers_stated_reason() -> None:
    """A governed refusal states which pairing it refused; that must survive.

    `ApiError` carried only a status, so `api()` threw away the body and the
    client replaced a specific governed reason with a generic "could not be
    profiled". When the pairing becomes unlisted later in this slice, the
    reason the server states is the only thing that tells the operator what
    happened, so the client has to keep it.
    """
    common = journey_asset("common.js")
    # The error carries the reason, and the reason is read out of the body.
    assert "this.detail" in common
    assert "body?.detail" in common
    # Read on the failure path and handed to the error that is thrown there, so a
    # caller's `catch` can reach it.
    assert "statedReason(response)" in common
    # A refused response need not be JSON, so the parse cannot be unguarded: an
    # HTML error page must leave the reason absent, not replace the status with a
    # parser error the caller then reports as the refusal.
    reader = common[common.index("const statedReason") : common.index("const api")]
    assert "try {" in reader and "catch" in reader
    assert "return null" in reader


def executable_lines(script: str) -> str:
    """The script with `//` comments stripped, so prose cannot satisfy a test.

    An assertion on a bare word is met by a comment mentioning it, which is how
    a test about rendering a refusal survived the deletion of the code that
    renders one. Everything asserted about behaviour is asserted against this.
    """
    kept = []
    for line in script.splitlines():
        head = line.split("//", 1)[0]
        if head.strip():
            kept.append(head)
    return "\n".join(kept)


def test_the_review_surface_renders_a_governed_refusal_bilingually() -> None:
    """The reason reaches a surface, and its wording is the server's.

    The established pattern is that the page carries both languages in
    `data-*` attributes and the script reads them, so no Arabic is compiled
    into an asset. A refusal rendered from a string in JavaScript would ship
    one language and silently drop the other.

    **Anchored on syntax only executing code produces.** The renderer is
    asserted by its definition *and* its invocation from both catch sites, and
    by the specific `dataset` reads it makes -- so deleting the function or
    either call site fails this test. A comment mentioning a refusal cannot
    satisfy any of it, because comments are stripped first.
    """
    code = executable_lines(journey_asset("review.js"))
    # Defined, and actually called -- from both places a refusal can arrive.
    assert "const refusal = (" in code
    assert code.count("refusal(failure,") == 2, (
        "refusal() must be invoked from both the load() and confirm catch sites"
    )
    # The two paths a governed refusal reaches: the review load, and the
    # facts/reports POSTs behind the confirm button.
    assert "load().catch((failure) => refusal(failure," in code
    assert "} catch (failure) {" in code
    # The server's own stated reason is what is shown, read off the error.
    assert "failure?.detail" in code
    # Both halves of the surrounding wording come from the page, not the script.
    assert "error.dataset.refusalTitle" in code
    assert "error.dataset.refusalStated" in code
    # And the fallbacks for "no stated reason", also page-owned.
    assert "error.dataset.analysisUnavailable" in code
    assert "error.dataset.reviewUnavailable" in code
    for language in ("en", "ar"):
        wording = JOURNEY_COPY[language]["refusal_stated"]
        assert wording, f"{language} has no wording for a stated refusal"
        assert wording not in script_text(), (
            "refusal wording belongs on the page, not in JS"
        )


def script_text() -> str:
    """The whole asset, comments included: no wording may appear anywhere."""
    return journey_asset("review.js")


def test_the_refusal_wording_ships_in_both_languages() -> None:
    """Bilingual wording ships with the code that introduces it.

    `copy.py` raises at import if the two dictionaries disagree on keys, so a
    missing Arabic *key* cannot ship. What that check cannot catch is an Arabic
    value copied from the English one, which is what this asserts.
    """
    for key in ("refusal_stated", "refusal_title"):
        english = JOURNEY_COPY["en"][key]
        arabic = JOURNEY_COPY["ar"][key]
        assert english and arabic
        assert english != arabic, f"{key} was not actually translated"


def test_the_collection_surface_labels_every_control_it_adds() -> None:
    """Accessibility is a required gate: no mouse-only, no unlabelled control.

    Every control the operator has to set needs a programmatic label, and a
    native input is what makes it keyboard reachable. A `div` wired to a click
    handler satisfies neither, and PR #280 already paid for that lesson on the
    report tables.
    """
    template = upload_template()
    fields = declared_field_names()
    assert fields, "the template declares no contract fields at all"
    for field in fields:
        identifier = f'id="contract-{field.replace("_", "-")}"'
        assert identifier in template, f"{field} has no identified control"
        assert f'for="contract-{field.replace("_", "-")}"' in template, (
            f"{field}'s control carries no label"
        )
    # Native controls only: these are focusable and operable without a pointer.
    assert "<input" in template
    assert "onclick" not in template


def contract_copy_keys() -> set[str]:
    """The copy keys the collection surface renders, read from the template."""
    source = files("khepri.rra.journey").joinpath(
        "templates", "upload.html.j2"
    ).read_text(encoding="utf-8")
    return set(re.findall(r"copy\.(contract_[a-z_]+)", source))


def assert_wording_reaches_the_page(language: str, keys: set[str]) -> None:
    """Every key has wording, and that wording reaches the rendered page.

    Both halves matter: a key missing from a dictionary leaves the control
    unlabelled, and a key present but never rendered does the same while passing
    a dictionary-only check.
    """
    page = upload_template(language)
    for key in keys:
        wording = JOURNEY_COPY[language].get(key)
        assert wording, f"{language} is missing {key}"
        assert wording in page, f"{language} page omits {key}"


def test_the_declaration_controls_carry_bilingual_labels() -> None:
    """The form's own wording is server-owned copy, like the rest of the page.

    The template renders `copy.*`, so both languages come from `copy.py` and
    neither can be hardcoded into the markup. Asserting the key exists in both
    dictionaries is what keeps the Arabic page from rendering English labels.
    """
    keys = contract_copy_keys()
    assert keys, "the collection surface renders no governed copy"
    for language in ("en", "ar"):
        assert_wording_reaches_the_page(language, keys)


def test_the_client_payload_and_the_form_agree_on_every_key() -> None:
    """The two halves of the fix cannot drift apart silently.

    `client_profile_payload` above is this module's model of what the client
    sends. If it and the template's controls disagree, one of them is wrong and
    the other's tests are proving something about a payload nobody posts.
    """
    payload = client_profile_payload()
    contract = payload["source_contract"]
    assert isinstance(contract, dict)
    assert set(contract) == declared_field_names()
    # Round-trips as JSON, which is how it actually reaches the route.
    assert json.loads(json.dumps(payload)) == payload
