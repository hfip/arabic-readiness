import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "report.py"
spec = importlib.util.spec_from_file_location("readiness_report", SCRIPT)
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def rtl(files=10, issues=None):
    issues = issues or []
    return {"files": files, "issues": issues}


def issue(code="RTL001", path="Sources/A.swift"):
    return {"code": code, "path": path, "line": 1, "fixable": True}


def catalog(coverage=50.0, filled=1, total=2, problems=None):
    return {
        "languages": [
            {"language": "en", "total": total, "filled": total, "coverage": 100.0},
            {"language": "ar", "total": total, "filled": filled, "coverage": coverage},
        ],
        "problems": problems or [],
    }


def test_perfect_score():
    result = report.compute(rtl(files=10, issues=[]), catalog(coverage=100, filled=2, total=2))
    assert result["score"] == 100
    assert result["status"] == "ready"


def test_mixed_score():
    result = report.compute(
        rtl(files=10, issues=[issue(path="A.swift"), issue(path="B.swift"), issue(path="C.swift")]),
        catalog(coverage=50, filled=1, total=2),
    )
    # 0.5*70 + 0.4*50 + 0.1*100 = 65
    assert result["score"] == 65
    assert result["status"] == "not ready"


def test_counts_affected_files_not_issues():
    issues = [issue(path="A.swift"), issue(path="A.swift"), issue(path="B.swift")]
    result = report.compute(rtl(files=10, issues=issues), None)
    rtl_dim = result["dimensions"][0]
    assert rtl_dim["affected"] == 2
    assert round(rtl_dim["score"]) == 80


def test_missing_catalog_drops_those_dimensions():
    result = report.compute(rtl(files=4, issues=[issue()]), None)
    keys = [item["key"] for item in result["dimensions"] if item["available"]]
    assert keys == ["rtl"]
    assert result["score"] == 75


def test_placeholder_problems_lower_consistency():
    problems = [{"kind": "specifier", "key": "A", "language": "ar", "detail": "x"}] * 3
    result = report.compute(rtl(files=1, issues=[]), catalog(problems=problems))
    consistency = next(item for item in result["dimensions"] if item["key"] == "consistency")
    assert round(consistency["score"]) == 70


def test_consistency_never_negative():
    problems = [{"kind": "plural", "key": "A", "language": "ar", "detail": "x"}] * 20
    result = report.compute(rtl(files=1, issues=[]), catalog(problems=problems))
    consistency = next(item for item in result["dimensions"] if item["key"] == "consistency")
    assert consistency["score"] == 0


def test_language_without_strings_is_unavailable():
    payload = {
        "languages": [{"language": "en", "total": 2, "filled": 2, "coverage": 100.0}],
        "problems": [],
    }
    result = report.compute(rtl(), payload)
    coverage = next(item for item in result["dimensions"] if item["key"] == "coverage")
    assert coverage["available"] is False
    assert "ar" in coverage["detail"]


def test_unknown_language_reported():
    result = report.compute(rtl(), catalog(), language="fr")
    coverage = next(item for item in result["dimensions"] if item["key"] == "coverage")
    assert coverage["available"] is False
    assert "fr" in coverage["detail"]


def test_render_contains_marker_and_formula():
    result = report.compute(
        rtl(files=2, issues=[issue(code="RTL003", path="A.swift")]),
        catalog(coverage=50),
    )
    markdown = report.render(result, {"subtitle": "2 files"})
    assert markdown.startswith(report.MARKER)
    assert "Arabic readiness:" in markdown
    assert "RTL003" in markdown
    assert "0.5 ×" in markdown
    assert "Not checked" in markdown


def test_status_thresholds():
    assert report.compute(rtl(1, []), catalog(100, 2, 2))["status"] == "ready"
    almost = report.compute(rtl(10, [issue(path="A.swift"), issue(path="B.swift"), issue(path="C.swift")]),
                            catalog(coverage=90, filled=9, total=10))
    assert almost["status"] in ("almost there", "ready")


def test_main_writes_files_and_respects_min_score(tmp_path):
    rtl_path = tmp_path / "rtl.json"
    catalog_path = tmp_path / "catalog.json"
    output = tmp_path / "comment.md"
    summary = tmp_path / "summary.md"
    rtl_path.write_text(json.dumps(rtl(files=2, issues=[issue()])), encoding="utf-8")
    catalog_path.write_text(json.dumps(catalog(coverage=50)), encoding="utf-8")

    argv = [
        "--rtl", str(rtl_path),
        "--catalog", str(catalog_path),
        "--output", str(output),
        "--summary", str(summary),
    ]
    assert report.main(argv) == 0
    assert output.read_text(encoding="utf-8").startswith(report.MARKER)
    assert "Arabic readiness" in summary.read_text(encoding="utf-8")

    assert report.main(argv + ["--min-score", "99"]) == 1


def test_main_without_inputs_still_writes_a_comment(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert report.main([]) == 0


def test_load_ignores_broken_json(tmp_path):
    broken = tmp_path / "bad.json"
    broken.write_text("{nope", encoding="utf-8")
    assert report.load(str(broken)) is None
    assert report.load(str(tmp_path / "missing.json")) is None
