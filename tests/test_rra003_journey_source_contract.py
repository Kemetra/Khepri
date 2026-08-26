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


def blank_form_payload() -> dict[str, object]:
    """What `declaration()` builds from controls the operator never touched.

    Derived from the same source of truth as the filled payload, so the two
    cannot disagree about which fields exist.
    """
    contract: dict[str, object] = {}
    filled = client_profile_payload()["source_contract"]
    assert isinstance(filled, dict)
    for name, value in filled.items():
        if isinstance(value, bool):
            contract[name] = False
        else:
            contract[name] = "" if name in REQUIRED_TEXT_FIELDS else None
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
        SourceContractBody(**{**{"contract_id": None, "evidence": None}})
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


def test_the_review_surface_renders_a_governed_refusal_bilingually() -> None:
    """The reason reaches a surface, and its wording is the server's.

    The established pattern is that the page carries both languages in
    `data-*` attributes and the script reads them, so no Arabic is compiled
    into an asset. A refusal rendered from a string in JavaScript would ship
    one language and silently drop the other.
    """
    script = journey_asset("review.js")
    assert "refusal" in script.lower()
    for language in ("en", "ar"):
        wording = JOURNEY_COPY[language]["refusal_stated"]
        assert wording, f"{language} has no wording for a stated refusal"
        assert wording not in script, "refusal wording belongs on the page, not in JS"


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


def test_the_declaration_controls_carry_bilingual_labels() -> None:
    """The form's own wording is server-owned copy, like the rest of the page.

    The template renders `copy.*`, so both languages come from `copy.py` and
    neither can be hardcoded into the markup. Asserting the key exists in both
    dictionaries is what keeps the Arabic page from rendering English labels.
    """
    source = files("khepri.rra.journey").joinpath(
        "templates", "upload.html.j2"
    ).read_text(encoding="utf-8")
    keys = set(re.findall(r"copy\.(contract_[a-z_]+)", source))
    assert keys, "the collection surface renders no governed copy"
    for key in keys:
        for language in ("en", "ar"):
            assert JOURNEY_COPY[language].get(key), f"{language} is missing {key}"
    # And the wording actually reaches the page an operator is served, in the
    # language they asked for. A key present in the dictionary but never rendered
    # would leave the control unlabelled while passing the check above.
    for language in ("en", "ar"):
        page = upload_template(language)
        for key in keys:
            assert JOURNEY_COPY[language][key] in page, f"{language} page omits {key}"


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
