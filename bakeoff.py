# ai-generated: 100% - Claude Code (Opus 5.5) wrote it from CI-SPEC.md section 3 on the course skeleton; tested on lab5-practice and edge cases
"""bakeoff.py - scanner SARIF + a labels file -> a per-tool confusion matrix (CI-SPEC.md P-23).

Standard library only - it runs as `python3 -S -E bakeoff.py`.

    python3 bakeoff.py --labels labels.json a.sarif b.sarif > bakeoff.json

Each rule of CI-SPEC.md section 3 is implemented by the function that names it (P-15 .. P-22).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import unquote

# P-19: the course's classes and their CWE numbers.
CLASS_CWES: dict[str, frozenset[int]] = {
    "secret": frozenset({259, 260, 321, 798}),
    "injection": frozenset({74, 77, 78, 79, 80, 88, 89, 90, 91, 94, 95, 96, 611, 776, 917, 943, 1336}),
    "deserialization": frozenset({502}),
    "weak-crypto": frozenset({261, 326, 327, 328, 330, 331, 338, 759, 760, 916}),
    "insecure-transport": frozenset({295, 297, 319, 322, 757}),
    "path-traversal": frozenset({22, 23, 35, 36, 73}),
    "ssrf": frozenset({918}),
    "vulnerable-dependency": frozenset({937, 1035, 1104, 1395}),
    "misconfiguration": frozenset({16, 215, 250, 489, 668, 732, 1188}),
    "access-control": frozenset({284, 285, 639, 862, 863}),
}
VULN_DEP = "vulnerable-dependency"

KNOWN_TOOLS = {"trivy": "trivy", "grype": "grype", "osv-scanner": "osv-scanner", "gitleaks": "gitleaks"}
SEMGREP_NAMES = {"semgrep", "semgrep oss", "semgrep ce", "semgrep community edition", "semgrep pro"}
TRIVY_TAG_CLASSES = {"vulnerability": VULN_DEP, "secret": "secret", "misconfiguration": "misconfiguration"}

CWE_RE = re.compile(r"(?<![A-Za-z0-9])[Cc][Ww][Ee]-([0-9]+)")
TOKEN_RE = re.compile(r"[A-Za-z0-9._-]+")
SEPARATORS_RE = re.compile(r"[-_.]+")
SLUG_RE = re.compile(r"[^a-z0-9]+")

NO_RULE = object()  # P-21: a result without a ruleId string, different from every string


def _obj(value) -> dict:
    """A JSON object, or an empty one for anything else (null counts as absent)."""
    return value if isinstance(value, dict) else {}


def _arr(value) -> list:
    """A JSON array, or no entries for anything else (an array member that is not an array has no entries)."""
    return value if isinstance(value, list) else []


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def tool_id(run: dict) -> str:
    """P-15: the tool id of a run."""
    tool = run.get("tool")
    driver = tool.get("driver") if isinstance(tool, dict) else None
    name = driver.get("name") if isinstance(driver, dict) else None
    if not isinstance(name, str):
        return "unknown"
    lowered = name.strip().lower()
    if lowered in KNOWN_TOOLS:
        return KNOWN_TOOLS[lowered]
    if lowered in SEMGREP_NAMES:
        return "semgrep"
    slug = SLUG_RE.sub("-", lowered).strip("-")
    return slug or "unknown"


def kept(result: dict) -> bool:
    """P-16: kind absent, null or exactly "fail", and no suppressions."""
    kind = result.get("kind")
    if kind is not None and kind != "fail":
        return False
    suppressions = result.get("suppressions")
    return suppressions is None or suppressions in ([], {}, False, 0, "")


def location(result: dict) -> dict | None:
    """P-16: the physicalLocation of the first location, when it names a non-empty uri string."""
    locations = _arr(result.get("locations"))
    if not locations:
        return None
    physical = _obj(_obj(locations[0]).get("physicalLocation"))
    uri = _obj(physical.get("artifactLocation")).get("uri")
    if not isinstance(uri, str) or uri == "":
        return None
    return physical


def set_file(uri: str, root: str) -> str | None:
    """P-17: the result's file inside the set, or None when it is outside."""
    path = unquote(uri)
    if path[:7].lower() == "file://":
        path = path[7:]
    if path.startswith("./"):
        path = path[2:]
    parts = path.split("/")
    last = None
    for index, part in enumerate(parts):
        if part == root:
            last = index
    if last is None:
        return None
    return "/".join(parts[last:])


def lines(physical: dict) -> tuple[int, int] | None:
    """P-18: (start, end) of the region, or None when the result has no lines."""
    region = _obj(physical.get("region"))
    start = region.get("startLine")
    if not _is_int(start) or start < 1:
        return None
    end = region.get("endLine")
    if not _is_int(end) or end < start:
        end = start
    return start, end


def _tags(properties) -> list[str]:
    return [tag for tag in _arr(_obj(properties).get("tags")) if isinstance(tag, str)]


def find_rule(run: dict, rule_id) -> dict | None:
    """P-19: the first entry of tool.driver.rules[] whose id equals the result's ruleId."""
    if not isinstance(rule_id, str):
        return None
    rules = _arr(_obj(_obj(run.get("tool")).get("driver")).get("rules"))
    for rule in rules:
        if isinstance(rule, dict) and rule.get("id") == rule_id:
            return rule
    return None


def classes(tool: str, result: dict, rule: dict | None) -> set[str]:
    """P-19: the classes of a result, from the first source that gives any; {"other"} otherwise."""
    own = _obj(result.get("properties")).get("class")
    if isinstance(own, str) and own in CLASS_CWES:
        return {own}
    rule_tags = _tags(rule.get("properties")) if rule is not None else []
    if tool == "gitleaks":
        return {"secret"}
    if tool in ("grype", "osv-scanner"):
        return {VULN_DEP}
    if tool == "trivy":
        found = {TRIVY_TAG_CLASSES[tag.lower()] for tag in rule_tags if tag.lower() in TRIVY_TAG_CLASSES}
        if found:
            return found
    numbers = set()
    for tag in _tags(result.get("properties")) + rule_tags:
        numbers.update(int(match) for match in CWE_RE.findall(tag))
    found = {name for name, cwes in CLASS_CWES.items() if numbers & cwes}
    return found or {"other"}


def _normalise(name: str) -> str:
    """PEP 503: lower case, every run of -, _ and . as a single -."""
    return SEPARATORS_RE.sub("-", name.lower())


def package_tokens(result: dict) -> set[str]:
    """P-20: the normalised tokens of message.text (none when there is no text string)."""
    text = _obj(result.get("message")).get("text")
    if not isinstance(text, str):
        return set()
    tokens = set()
    for raw in TOKEN_RE.findall(text):
        token = raw.strip("._-")
        if token:
            tokens.add(_normalise(token))
    return tokens


def matches(finding: dict, defect: dict) -> bool:
    """P-20: does one in-set result match one defect."""
    if finding["file"] != defect.get("file") or defect.get("class") not in finding["classes"]:
        return False
    if defect["class"] == VULN_DEP:
        package = defect.get("package")
        return isinstance(package, str) and _normalise(package) in finding["tokens"]
    span = finding["lines"]
    if span is None:
        return False
    return span[0] <= defect["end_line"] and defect["start_line"] <= span[1]


def _ratio(numerator: int, denominator: int):
    return None if denominator == 0 else round(numerator / denominator, 4)


def confusion_matrix(labels: dict, sarif_documents: list) -> dict:
    """The matrix of P-21 and P-22 for the labels (P-14) and the parsed SARIF documents."""
    root = labels["set"]
    defects = labels["defects"]
    findings: dict[str, list[dict]] = {}
    for document in sarif_documents:
        for run in _arr(_obj(document).get("runs")):
            if not isinstance(run, dict):
                continue
            tool = tool_id(run)
            bucket = findings.setdefault(tool, [])
            for result in _arr(run.get("results")):
                if not isinstance(result, dict) or not kept(result):
                    continue
                physical = location(result)
                if physical is None:
                    continue
                file = set_file(physical["artifactLocation"]["uri"], root)
                if file is None:
                    continue
                rule_id = result.get("ruleId")
                bucket.append({
                    "rule": rule_id if isinstance(rule_id, str) else NO_RULE,
                    "file": file,
                    "lines": lines(physical),
                    "classes": classes(tool, result, find_rule(run, rule_id)),
                    "tokens": package_tokens(result),
                })

    tools = {}
    for tool in sorted(findings):
        found: set[int] = set()
        false_positives = set()
        for finding in findings[tool]:
            hit = [index for index, defect in enumerate(defects) if matches(finding, defect)]
            if hit:
                found.update(hit)
                continue
            start, end = finding["lines"] if finding["lines"] is not None else (None, None)
            rule = finding["rule"] if finding["rule"] is not NO_RULE else ("\0no-rule",)  # a tuple is never a str
            false_positives.add((rule, finding["file"], start, end))
        tp, fp = len(found), len(false_positives)
        fn = len(defects) - tp
        tools[tool] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": _ratio(tp, tp + fp),
            "recall": _ratio(tp, tp + fn),
            "f1": _ratio(2 * tp, 2 * tp + fp + fn),
        }
    return {"set": root, "defects": len(defects), "tools": tools}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="per-tool confusion matrix of SARIF against labels (CI-SPEC.md P-23)")
    parser.add_argument("--labels", required=True, help="the labels file (P-14)")
    parser.add_argument("sarif", nargs="+", help="SARIF 2.1.0 files")
    args = parser.parse_args(argv)
    with open(args.labels, encoding="utf-8-sig") as fh:
        labels = json.load(fh)
    documents = []
    for path in args.sarif:
        with open(path, encoding="utf-8-sig") as fh:
            documents.append(json.load(fh))
    json.dump(confusion_matrix(labels, documents), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
