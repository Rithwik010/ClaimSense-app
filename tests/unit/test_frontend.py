"""The Streamlit page renders without the API (Streamlit's in-process test runner)."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from frontend.app import dollars

PAGE = Path(__file__).resolve().parents[2] / "frontend" / "app.py"


def test_page_renders_and_reports_an_unreachable_api(monkeypatch) -> None:
    monkeypatch.setenv("CLAIMSENSE_API_URL", "http://127.0.0.1:9")

    page = AppTest.from_file(str(PAGE), default_timeout=30).run()

    assert not page.exception
    assert "API unreachable" in page.sidebar.error[0].value
    assert '"claim_id": "CLM-SAMPLE-0001"' in page.text_area[0].value
    assert page.button[0].label == "Submit and process"


def test_money_is_formatted_from_integer_cents() -> None:
    assert [dollars(cents) for cents in (0, 5, 123456, -2500)] == [
        "$0.00",
        "$0.05",
        "$1,234.56",
        "-$25.00",
    ]
