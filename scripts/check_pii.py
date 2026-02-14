#!/usr/bin/env python3
"""Pre-commit PII scanner — blocks commits containing likely sensitive data.

Uses generic heuristic patterns to catch common PII categories,
not specific personal data. Designed as a safety net alongside
the agent rules in AGENTS.md.

Usage:
    python scripts/check_pii.py          # scan staged files (pre-commit)
    python scripts/check_pii.py --all    # scan all tracked files (CI / audit)
"""

import re
import subprocess
import sys
from pathlib import Path

# ── Generic PII patterns (not specific to any person) ──────────────────

PATTERNS: list[tuple[re.Pattern, str]] = [
    # Indian Aadhaar number: 4+4+4 digits with spaces or dashes
    (re.compile(r"\b\d{4}[\s-]\d{4}[\s-]\d{4}\b"), "Aadhaar number (NNNN NNNN NNNN)"),

    # Indian PAN card: ABCDE1234F
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "PAN card number"),

    # Indian phone numbers: +91 or standalone 0 prefix followed by 10 digits
    (re.compile(r"(?:\+91[\s-]?|\b0)[6-9]\d{9}\b"), "Indian phone number"),

    # Hardcoded password assignments in Python (not test/example placeholders)
    # Catches: password="real_secret" but allows password="test", "TEST1234", "YOUR_PASSWORD", etc.
    (
        re.compile(
            r"""(?:password|passwd|pwd|secret|api_key)\s*=\s*['"]"""
            r"""(?!test|TEST|changeme|YOUR_|your_|example|dummy|fake|placeholder|secret['"])"""
            r"""[a-zA-Z0-9@#$%^&*!]{4,}['"]""",
            re.IGNORECASE,
        ),
        "Possible hardcoded password (use env vars instead)",
    ),

    # os.environ assignment with inline secret (os.environ['X'] = 'real_value')
    (
        re.compile(
            r"""os\.environ\[['"][^'"]+['"]\]\s*=\s*['"]"""
            r"""(?!test|TEST|changeme|YOUR_|your_|example|dummy|fake|placeholder)"""
            r"""[^'"]{4,}['"]"""
        ),
        "Hardcoded secret in os.environ assignment",
    ),

    # Email addresses (except safe domains used in examples/automation)
    (
        re.compile(
            r"\b[a-zA-Z0-9._%+-]+@(?!example\.com\b|example\.org\b|anthropic\.com\b|users\.noreply\.github\.com\b)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
        ),
        "Email address (use @example.com for tests)",
    ),
]

# ── File filtering ──────────────────────────────────────────────────────

SKIP_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".pyc", ".pyo", ".db", ".sqlite", ".sqlite3",
    ".lock", ".egg-info", ".css",
}

# Files that legitimately discuss passwords/PII patterns
SKIP_PATHS = {
    "scripts/check_pii.py",
    ".pii-patterns",
    ".env.example",
    "AGENTS.md",
    "DATA_PRIVACY.md",
    "CONTRIBUTING.md",
    "docs/TESTING.md",
    "docs/TROUBLESHOOTING.md",
    "docs/ADDING_A_PARSER.md",
    "docs/DEVELOPMENT.md",
}


def get_staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True, check=True,
    )
    return [f for f in result.stdout.strip().splitlines() if f]


def get_all_tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True,
    )
    return [f for f in result.stdout.strip().splitlines() if f]


def should_skip(filepath: str) -> bool:
    p = Path(filepath)
    return p.suffix.lower() in SKIP_EXTENSIONS or str(p) in SKIP_PATHS


def scan_file(filepath: str) -> list[str]:
    violations = []
    try:
        content = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    for line_num, line in enumerate(content.splitlines(), 1):
        for compiled, description in PATTERNS:
            if compiled.search(line):
                display = line.strip()[:120]
                violations.append(
                    f"  {filepath}:{line_num}  [{description}]\n"
                    f"    | {display}"
                )
    return violations


def main() -> int:
    scan_all = "--all" in sys.argv
    files = get_all_tracked_files() if scan_all else get_staged_files()

    if not files:
        return 0

    all_violations = []
    for filepath in files:
        if should_skip(filepath):
            continue
        all_violations.extend(scan_file(filepath))

    if all_violations:
        print("\n" + "=" * 60)
        print("  PII DETECTED — commit blocked")
        print("=" * 60)
        print(f"\nFound {len(all_violations)} violation(s):\n")
        for v in all_violations:
            print(v)
        print("\n" + "-" * 60)
        print("Fix: Remove the sensitive data.")
        print("  - Passwords: use env vars (os.environ.get(...))")
        print("  - Test data: use synthetic values (see AGENTS.md)")
        print("  - False positive? Add file to SKIP_PATHS in this script.")
        print("-" * 60 + "\n")
        return 1

    if scan_all:
        print(f"PII scan: {len(files)} files checked, all clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
