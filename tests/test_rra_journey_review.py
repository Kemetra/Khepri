from __future__ import annotations

from importlib.resources import files

from tests.test_rra_journey_api import client


def test_review_page_uses_a_captioned_scoped_table_and_no_editable_mapping() -> None:
    body = client().get("/beta/en/review").text
    assert "<caption" in body
    assert body.count('scope="col"') == 4
    assert '<select' not in body
    assert 'id="confirm-mapping"' in body and " disabled" in body


def test_review_renders_server_values_as_text_and_requires_mapped_fields() -> None:
    script = files("khepri.rra.journey").joinpath("assets", "review.js").read_text(
        encoding="utf-8"
    )
    assert "textContent = value" in script
    assert "innerHTML" not in script
    assert 'item.state === "mapped"' in script
    assert script.index("/api/v1/beta/facts") < script.index("/api/v1/beta/reports")
