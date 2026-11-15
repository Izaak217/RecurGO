from __future__ import annotations

import json
import re
from html.parser import HTMLParser

import pytest

from recurgo.reporting.viewer import render_report_html


class ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.external_resources: list[str] = []
        self.scripts: list[dict[str, str | None]] = []
        self.identifiers: list[str] = []
        self.csp = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        properties = dict(attrs)
        identifier = properties.get("id")
        if identifier:
            self.identifiers.append(identifier)
        if tag == "script":
            self.scripts.append(properties)
        if tag in {"script", "img", "iframe", "source", "link"}:
            reference = properties.get("src") or properties.get("href")
            if reference:
                self.external_resources.append(reference)
        if properties.get("http-equiv") == "Content-Security-Policy":
            self.csp = properties.get("content") or ""


def test_report_data_cannot_close_script_or_inject_markup() -> None:
    dangerous = '</script><img src="https://invalid.example" onerror="alert(1)"> & \u2028\u2029'
    data: dict[str, object] = {
        "schemaVersion": 1, "game": {"name": dangerous},
        "nodes": {}, "language": "zh", "title": "中文棋谱",
    }
    output = render_report_html(data)
    parser = ReportParser()
    parser.feed(output)
    assert len(parser.scripts) == 2
    assert not parser.external_resources
    assert dangerous not in output
    match = re.search(
        r'<script id="report-data" type="application/json">(.*?)</script>', output,
    )
    assert match is not None
    assert json.loads(match[1]) == data
    assert "\\u003c/script\\u003e" in match[1]
    assert "\\u0026" in match[1]
    assert "\\u2028" in match[1]
    assert "\\u2029" in match[1]


def test_report_is_self_contained_and_has_interactive_sections() -> None:
    output = render_report_html({"schemaVersion": 1, "nodes": {}})
    parser = ReportParser()
    parser.feed(output)
    assert not parser.external_resources
    assert "connect-src 'none'" in parser.csp
    assert len(parser.identifiers) == len(set(parser.identifiers))
    expected = {
        "board", "candidate-body", "move-number", "move-slider", "branch-select",
        "first-move", "previous-move", "next-move", "last-move", "pv-prev", "pv-next",
        "pv-exit", "trend-chart", "quality-chart", "problem-body", "match-body",
        "overview-content", "scope-select", "language-select", "zoom-x", "zoom-y",
        "reset-zoom", "panel-trend", "panel-quality", "panel-problems", "panel-match",
        "panel-overview", "report-content", "open-help",
    }
    assert expected.issubset(parser.identifiers)
    assert 'name="viewport"' in output
    assert "innerHTML" not in output
    assert "fetch(" not in output
    assert "XMLHttpRequest" not in output


def test_browser_help_is_static_and_the_report_starts_hidden() -> None:
    output = render_report_html({"schemaVersion": 1, "nodes": {}})
    assert 'id="open-help" class="card open-help"' in output
    assert 'id="report-content" hidden' in output
    assert "使用浏览器（如 Edge、Chrome）打开" in output
    assert "如果使用浏览器打开后仍无法操作，请检查浏览器是否已开启 JavaScript" in output
    assert "please open the report in a browser, such as Edge or Chrome" in output
    assert 'type="file"' not in output
    assert "FileReader" not in output
    assert "render_report_viewer_html" not in output


@pytest.mark.parametrize("version", [None, 0, 2, "1"])
def test_report_refuses_an_unknown_schema(version: object) -> None:
    with pytest.raises(ValueError, match="schema"):
        render_report_html({"schemaVersion": version})


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_report_refuses_non_finite_json_numbers(invalid: float) -> None:
    with pytest.raises(ValueError):
        render_report_html({"schemaVersion": 1, "value": invalid})
