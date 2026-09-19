#!/usr/bin/env python3
"""Static lint for Agent Skills (SKILL.md + referenced files).

Checks per skill directory:
  1. SKILL.md exists and its frontmatter parses with name + description
  2. frontmatter name matches the directory name (Anthropic convention)
  3. description length <= 1024 characters (hard limit in skill loaders)
  4. repo-internal relative paths referenced in backticks or markdown links
     exist on disk (references/, scripts/, assets/, files/ prefixes)
  5. no high-confidence secret patterns in SKILL.md and referenced files

Exit code 0 = all skills clean; 1 = at least one failure. --json emits a
machine-readable report instead of human output (used by CI).
"""

import argparse
import json
import re
import sys
from pathlib import Path

MAX_DESCRIPTION_CHARS = 1024

# Referenced-file extraction: backtick spans like `references/foo.md` and
# markdown links like [label](references/foo.md). Only check paths under
# known asset subdirectories — other backtick spans are usually generic
# filenames (config.toml, package.json) that are not repo files.
ASSET_PREFIXES = ("references/", "scripts/", "assets/", "files/")
BACKTICK_PATH = re.compile(r"`([^\s`]+)`")
MD_LINK_PATH = re.compile(r"\]\(([^)\s]+)\)")

# Secret patterns: keep to high-confidence shapes to avoid false positives
# on placeholders like <YOUR_API_KEY> or "xxx".
SECRET_PATTERNS = [
    ("openai-style-key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("assigned-secret-literal", re.compile(
        r"(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*[\"'][A-Za-z0-9+/_-]{16,}[\"']")),
]
PLACEHOLDER_HINTS = ("xxx", "your", "example", "placeholder", "<", "{{")


def parse_frontmatter(text):
    """Return (metadata_dict, error). Only YAML key: value lines are needed."""
    if not text.startswith("---"):
        return None, "missing frontmatter block"
    end = text.find("\n---", 3)
    if end == -1:
        return None, "frontmatter not closed"
    block = text[4:end] if text[3] == "\n" else text[3:end]
    meta = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            meta[m.group(1)] = m.group(2).strip().strip("\"'")
    return meta, None


def referenced_paths(text):
    seen = set()
    for pattern in (BACKTICK_PATH, MD_LINK_PATH):
        for raw in pattern.findall(text):
            if raw.startswith(("http://", "https://", "#", "mailto:")):
                continue
            if raw.startswith(ASSET_PREFIXES):
                seen.add(raw)
    return sorted(seen)


def lint_skill(skill_dir: Path):
    """Return a list of {check, severity, message} findings for one skill."""
    findings = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [{"check": "skilmd-exists", "severity": "error",
                 "message": "SKILL.md not found"}]

    text = skill_md.read_text(encoding="utf-8")
    meta, err = parse_frontmatter(text)
    if err:
        return [{"check": "frontmatter", "severity": "error", "message": err}]
    for field in ("name", "description"):
        if not meta.get(field):
            findings.append({"check": "frontmatter", "severity": "error",
                             "message": f"frontmatter field '{field}' is missing or empty"})
    if findings:
        return findings

    if meta["name"] != skill_dir.name:
        findings.append({"check": "name-matches-dir", "severity": "error",
                         "message": f"frontmatter name '{meta['name']}' != directory '{skill_dir.name}'"})

    # Frontmatter may be followed by quoted multi-line descriptions; measure
    # the raw field as written (single-line value in this repo's convention).
    desc_len = len(meta["description"])
    if desc_len > MAX_DESCRIPTION_CHARS:
        findings.append({"check": "description-length", "severity": "error",
                         "message": f"description is {desc_len} chars (limit {MAX_DESCRIPTION_CHARS})"})

    body = text[text.find("---", 3) + 3:]

    missing = [p for p in referenced_paths(body) if not (skill_dir / p).exists()]
    for p in missing:
        findings.append({"check": "referenced-file-exists", "severity": "error",
                         "message": f"referenced file not found: {p}"})

    # Secret scan covers the whole SKILL.md (frontmatter included) plus every
    # referenced text file that exists.
    scan_targets = [("<SKILL.md>", text)]
    for p in referenced_paths(body):
        target = skill_dir / p
        if target.is_file():
            try:
                scan_targets.append((p, target.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
    for where, content in scan_targets:
        for label, pattern in SECRET_PATTERNS:
            for m in pattern.finditer(content):
                snippet = m.group(0)[:40]
                if any(h in snippet.lower() for h in PLACEHOLDER_HINTS):
                    continue
                findings.append({"check": "secret-scan", "severity": "error",
                                 "message": f"{label} pattern in {where}: {snippet}..."})
    return findings


def main():
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dirs", nargs="*", help="skill directories (default: huohou-* under repo root)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    skill_dirs = [Path(d) for d in args.dirs] or sorted(
        d for d in repo_root.glob("huohou-*")
        if d.is_dir() and not d.name.endswith("-workspace"))
    skill_dirs = [d for d in skill_dirs if d.is_dir()]
    if not skill_dirs:
        print("no skill directories found", file=sys.stderr)
        return 2

    report = {}
    for d in skill_dirs:
        report[d.name] = lint_skill(d)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        failed = False
        for name, findings in report.items():
            if not findings:
                print(f"PASS {name}")
                continue
            failed = True
            for f in findings:
                print(f"FAIL {name}: [{f['check']}] {f['message']}")
        total = sum(len(v) for v in report.values())
        print(f"\n{len(report)} skills checked, {total} finding(s)")
        return 1 if failed else 0
    return 1 if any(report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
