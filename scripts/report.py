#!/usr/bin/env python3
"""Score Arabic readiness and render the pull request comment.

Reads the JSON output of rtl-lint and xcstrings-audit, combines three dimensions
into one number, and writes a markdown report. Exit code is 1 when the score is
below --min-score.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

MARKER = "<!-- arabic-readiness -->"
WEIGHTS = {"rtl": 0.5, "coverage": 0.4, "consistency": 0.1}
CONSISTENCY_KINDS = {"specifier", "plural"}
RULE_LABELS = {
    "RTL001": "physical alignment",
    "RTL002": "explicit alignment enums",
    "RTL003": "left/right anchors",
    "RTL004": "physical edge insets",
    "RTL005": "forced direction",
    "RTL006": "manual direction branches",
    "RTL007": "manual mirroring",
    "RTL008": "storyboard alignment",
    "RTL009": "storyboard forced direction",
}


def load(path: Optional[str]) -> Optional[dict]:
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _rtl_dimension(rtl: Optional[dict]) -> dict:
    if rtl is None:
        return {"key": "rtl", "available": False, "score": 0.0, "detail": "rtl-lint did not run"}

    files = int(rtl.get("files") or 0)
    issues = rtl.get("issues") or []
    affected = len({issue.get("path") for issue in issues})
    score = 100.0 if files == 0 else 100.0 * (files - affected) / files
    return {
        "key": "rtl",
        "available": True,
        "score": score,
        "detail": "%d of %d files have physical layout code" % (affected, files),
        "affected": affected,
        "files": files,
        "issues": issues,
    }


def _coverage_dimension(catalog: Optional[dict], language: str) -> dict:
    if catalog is None:
        return {
            "key": "coverage",
            "available": False,
            "score": 0.0,
            "detail": "no String Catalog found",
        }

    for entry in catalog.get("languages") or []:
        if entry.get("language") == language and entry.get("total"):
            return {
                "key": "coverage",
                "available": True,
                "score": float(entry.get("coverage", 0.0)),
                "detail": "%d of %d keys translated"
                % (entry.get("filled", 0), entry.get("total", 0)),
                "entry": entry,
            }

    return {
        "key": "coverage",
        "available": False,
        "score": 0.0,
        "detail": "no %r strings in the catalog yet" % language,
    }


def _consistency_dimension(catalog: Optional[dict]) -> dict:
    if catalog is None:
        return {
            "key": "consistency",
            "available": False,
            "score": 0.0,
            "detail": "no String Catalog found",
        }

    problems = [p for p in (catalog.get("problems") or []) if p.get("kind") in CONSISTENCY_KINDS]
    score = max(0.0, 100.0 - 10.0 * len(problems))
    return {
        "key": "consistency",
        "available": True,
        "score": score,
        "detail": "%d placeholder or plural %s"
        % (len(problems), "issue" if len(problems) == 1 else "issues"),
        "problems": problems,
    }


def compute(rtl: Optional[dict], catalog: Optional[dict], language: str = "ar") -> dict:
    dimensions = [
        _rtl_dimension(rtl),
        _coverage_dimension(catalog, language),
        _consistency_dimension(catalog),
    ]
    available = [item for item in dimensions if item["available"]]
    total_weight = sum(WEIGHTS[item["key"]] for item in available)
    if total_weight == 0:
        score = 0.0
    else:
        score = sum(WEIGHTS[item["key"]] * item["score"] for item in available) / total_weight

    rounded = int(round(score))
    if rounded >= 90:
        status = "ready"
    elif rounded >= 70:
        status = "almost there"
    else:
        status = "not ready"

    return {
        "score": rounded,
        "status": status,
        "dimensions": dimensions,
        "weights": {item["key"]: WEIGHTS[item["key"]] for item in available},
        "language": language,
    }


def _top_rules(issues: List[dict], limit: int = 4) -> List[tuple]:
    counts: Dict[str, int] = {}
    for issue in issues:
        code = issue.get("code") or "?"
        counts[code] = counts.get(code, 0) + 1
    return sorted(counts.items(), key=lambda item: -item[1])[:limit]


def render(result: dict, details: Optional[dict] = None) -> str:
    details = details or {}
    lines: List[str] = [MARKER, ""]
    lines.append("## Arabic readiness: %d%%" % result["score"])
    lines.append("")
    lines.append("**%s** · %s" % (result["status"], details.get("subtitle", "").strip() or "—"))
    lines.append("")
    lines.append("| Check | Score | Detail |")
    lines.append("| --- | --- | --- |")
    for item in result["dimensions"]:
        label = {
            "rtl": "RTL layout",
            "coverage": "Arabic coverage",
            "consistency": "Placeholders & plurals",
        }[item["key"]]
        if item["available"]:
            value = "%d%%" % round(item["score"])
        else:
            value = "n/a"
        lines.append("| %s | %s | %s |" % (label, value, item["detail"]))

    rtl = next(item for item in result["dimensions"] if item["key"] == "rtl")
    if rtl.get("issues"):
        rules = _top_rules(rtl["issues"])
        if rules:
            lines.append("")
            lines.append("<details><summary>Top layout findings</summary>")
            lines.append("")
            lines.append("| Rule | What | Count |")
            lines.append("| --- | --- | --- |")
            for code, count in rules:
                lines.append("| `%s` | %s | %d |" % (code, RULE_LABELS.get(code, code), count))
            lines.append("")
            lines.append("Run `rtl-lint migrate` for a branch with the safe fixes.")
            lines.append("")
            lines.append("</details>")

    problems = [
        item
        for item in result["dimensions"]
        if item["key"] == "consistency" and item.get("problems")
    ]
    if problems:
        lines.append("")
        lines.append("<details><summary>Placeholder and plural issues</summary>")
        lines.append("")
        for problem in problems[0]["problems"][:10]:
            lines.append(
                "- `%s` (%s): %s" % (problem.get("key"), problem.get("language"), problem.get("detail"))
            )
        lines.append("")
        lines.append("</details>")

    lines.append("")
    lines.append("<details><summary>Not checked by this action</summary>")
    lines.append("")
    lines.append("- Images that should mirror (arrows, timelines, media controls).")
    lines.append("- Number, date and currency formatting.")
    lines.append("- Truncation and line breaking in Arabic.")
    lines.append("- Whether the translation itself reads well.")
    lines.append("")
    lines.append("</details>")

    formula = " + ".join(
        "%.1f × %d" % (result["weights"][item["key"]], round(item["score"]))
        for item in result["dimensions"]
        if item["available"]
    )
    lines.append("")
    lines.append(
        "<sub>Score: %s = %d. Weights are fixed: layout 0.5, coverage 0.4, placeholders 0.1. "
        "Unavailable checks are dropped and the rest renormalised.</sub>"
        % (formula, result["score"])
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Score Arabic readiness")
    parser.add_argument("--rtl", help="rtl-lint --format json output")
    parser.add_argument("--catalog", help="xcstrings-audit --json output")
    parser.add_argument("--lang", default="ar")
    parser.add_argument("--min-score", type=int, default=0)
    parser.add_argument("--output", help="write the markdown comment here")
    parser.add_argument("--summary", help="append to GITHUB_STEP_SUMMARY")
    args = parser.parse_args(argv)

    rtl = load(args.rtl)
    catalog = load(args.catalog)
    result = compute(rtl, catalog, args.lang)

    subtitle_parts = []
    rtl_dim = result["dimensions"][0]
    if rtl_dim["available"]:
        subtitle_parts.append(rtl_dim["detail"])
    coverage = next(item for item in result["dimensions"] if item["key"] == "coverage")
    if coverage["available"]:
        subtitle_parts.append(coverage["detail"])
    markdown = render(result, {"subtitle": " · ".join(subtitle_parts)})

    if args.output:
        Path(args.output).write_text(markdown + "\n", encoding="utf-8")
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as handle:
            handle.write(markdown + "\n")
    print("arabic-readiness: %d%% (%s)" % (result["score"], result["status"]))

    if args.min_score and result["score"] < args.min_score:
        print("below minimum score %d" % args.min_score, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
