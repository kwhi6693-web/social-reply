"""Offline, fail-closed publication checks. Findings never contain matched values."""
import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import unquote

ALLOWED = {
    "SKILL.md", "README.md", "README.zh-CN.md", "README.zh-TW.md", "LICENSE", ".gitignore", ".gitattributes",
    ".github/workflows/validate.yml", "agents/openai.yaml",
    "references/methods.md", "references/video-foundations.md",
    "CHANGELOG.md", "references/profile-memory.md", "references/theory-core.md",
    "references/extensions.md", "references/architecture.md", "scripts/validate_skill.py",
    "assets/icon.svg", "assets/config.example.json", "assets/profile.example.md", "assets/theory-core.json",
    "scripts/social_reply.py", "scripts/benchmark.py", "scripts/sr/__init__.py",
    "scripts/sr/integrity.py", "scripts/sr/memory.py", "scripts/sr/knowledge.py", "scripts/sr/runtime.py",
    "tests/test_release.py", "tests/test_v2.py", "tests/test_experience.py", "tests/scenarios.json",
}
PATTERNS = {
    "private-locator": r"(?:libfile_[A-Za-z0-9]{12,}|file_[0-9a-f]{16,}|(?:oai-library|sediment)://[A-Za-z0-9_%+.-]{8,})",
    "absolute-path": r"(?:\b[A-Za-z]:[\\/][\w. -][^\s\"']*|(?<![\w:/\\+])/(?:[\w.-]+/)+[\w. -]+|(?<!\\)\\\\[\w.-]+\\[\w.$ -]+(?:\\[^\s\"']*)?)",
    "access-token": r"\b(?:(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})\b",
    "bearer-secret": r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{16,}",
    "secret-assignment": r"""(?i)\b(?:api[_-]?key|access[_-]?token|secret|password)\b["']?\s*[:=]\s*["']?[A-Za-z0-9+/_=.-]{12,}""",
    "private-key": r"-{5}BEGIN (?:[A-Z]+ )?PRIVATE KEY-{5}",
    "email-address": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "phone-number": r"(?<![A-Za-z0-9_])(?:(?:\+?86[ -]?)?1[3-9]\d(?:[ -]?\d){8}|\+[1-9]\d{0,2}(?:[ -]?\d){7,12})(?![A-Za-z0-9_])",
    "signed-url": r"(?i)https?://[^\s\"']+[?&](?:sig|token|access_token|x-amz-signature|x-goog-signature)=[^&\s\"']{8,}",
    "jwt": r"\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\b",
}


def finding(path, rule, line=1):
    label = str(path)
    if label not in ALLOWED and label != ".":
        label = "unlisted-entry"
    return {"path": label, "line": line, "rule": rule}


def scan_text(text, path):
    output = []
    for rule, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text):
            output.append(finding(path, rule, text.count("\n", 0, match.start()) + 1))
    return output


def validate_package(root):
    root = Path(root).resolve()
    errors = []
    texts = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in list(dirs):
            child = base / name
            if name == ".git":
                dirs.remove(name)
                continue
            if child.is_symlink():
                errors.append(finding(child.relative_to(root).as_posix(), "symlink"))
                dirs.remove(name)
        for name in files:
            path = base / name
            relative = path.relative_to(root).as_posix()
            errors.extend(scan_text(relative, relative))
            if path.is_symlink():
                errors.append(finding(relative, "symlink"))
                continue
            if relative not in ALLOWED:
                errors.append(finding(relative, "unexpected-file"))
            try:
                data = path.read_bytes()
            except OSError:
                errors.append(finding(relative, "unreadable-file"))
                continue
            if len(data) > 1_000_000:
                errors.append(finding(relative, "oversized-file"))
                continue
            try:
                if b"\x00" in data:
                    raise UnicodeError()
                text = data.decode("utf-8-sig")
            except UnicodeError:
                errors.append(finding(relative, "binary-content"))
                continue
            texts[relative] = text
            errors.extend(scan_text(text, relative))

    for relative in sorted(ALLOWED):
        if relative not in texts:
            errors.append(finding(relative, "missing-resource"))

    entry = texts.get("SKILL.md", "")
    parts = entry.split("---", 2)
    fields = {}
    if len(parts) == 3 and not parts[0].strip():
        for line in parts[1].splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip()] = value.strip()
    if set(fields) != {"name", "description"} or fields.get("name") != "social-reply" or not fields.get("description", "").startswith("Use when"):
        errors.append(finding("SKILL.md", "invalid-frontmatter"))
    if "TODO" in entry or len(entry.splitlines()) > 500:
        errors.append(finding("SKILL.md", "unfinished-entry"))
    if "$social-reply" not in texts.get("agents/openai.yaml", ""):
        errors.append(finding("agents/openai.yaml", "invocation-mismatch"))

    for relative, text in texts.items():
        if not relative.endswith(".md"):
            continue
        links = [(m.group(1), m.start()) for m in re.finditer(r"!?\[[^\]]*\]\(([^)]+)\)", text)]
        definitions = {}
        for match in re.finditer(r"(?m)^\s*\[([^\]]+)\]:\s*(<[^>]+>|\S+)", text):
            definitions[match.group(1).strip().lower()] = match.group(2).strip("<>")
            links.append((match.group(2).strip("<>"), match.start()))
        for match in re.finditer(r"\[([^\]]+)\]\[([^\]]*)\]", text):
            label = (match.group(2) or match.group(1)).strip().lower()
            if label not in definitions:
                errors.append(finding(relative, "missing-resource", text.count("\n", 0, match.start()) + 1))
        for raw_target, position in links:
            target = unquote(raw_target).split("#", 1)[0]
            if not target or target.startswith(("https://", "http://")):
                continue
            candidate = Path(relative).parent / target
            if ":" in target or "\\" in target or target.startswith("/") or ".." in candidate.parts:
                errors.append(finding(relative, "unsafe-link", text.count("\n", 0, position) + 1))
            elif candidate.as_posix() not in texts:
                errors.append(finding(relative, "missing-resource", text.count("\n", 0, position) + 1))
    try:
        scenarios = json.loads(texts.get("tests/scenarios.json", "null"))
        valid = isinstance(scenarios, list) and len(scenarios) >= 10
        valid = valid and all(isinstance(x, dict) and set(x) == {"id", "mode", "input", "checks"} and isinstance(x["input"], str) and isinstance(x["checks"], list) and bool(x["checks"]) for x in scenarios)
        valid = valid and len({x["id"] for x in scenarios}) == len(scenarios)
        if not valid:
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        errors.append(finding("tests/scenarios.json", "invalid-scenarios"))
    return sorted(errors, key=lambda x: (x["path"], x["line"], x["rule"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        if not args.root.is_dir():
            raise OSError()
        errors = validate_package(args.root)
    except OSError:
        print(json.dumps({"status": "failed", "findings": [{"path": ".", "line": 1, "rule": "unavailable-root"}]}))
        return 1
    print(json.dumps({"status": "failed" if errors else "passed", "findings": errors}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

