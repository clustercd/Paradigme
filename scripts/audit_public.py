"""Audit the current publishable working tree without printing sensitive values.

This is a deterministic release gate, not proof that arbitrary text is anonymous.
It includes tracked and non-ignored new files, and skips tracked deletions.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PREFIXES = (
    "paradigme_venv/", "dist/", "env/", ".venv/", "venv/", ".local/", "data/", "data_external/", "kb/", "logs/", "reports/",
    "agents/projects/", "backend/projects/", "backend/users/", "backend/uploads/",
    "demo/", "sounds/", "frontend/public/encyclopedia_data/",
    "frontend/public/larousse_data/", "frontend/public/assets/car-mode/",
    "frontend/public/plugins/gps/",
)
PRIVATE_SUFFIXES = (".bak", ".db", ".sqlite", ".sqlite3", ".zip", ".7z", ".pdf", ".docx", ".mp4", ".avi", ".wmv", ".mkv", ".mov", ".webm", ".ogv", ".mp3", ".wav", ".m4a", ".flac", ".ogg")
PRIVATE_NAMES = {
    "config.json", ".ctpm.json", "desktop.ini", "private_settings.json", "cookies.txt", "secrets.env", "personal_identity.json", "network_config.json", "paths_config.json",
    "complete_storage_report.json", "search_results.json", "dico.txt",
    "dictionnaire_progress.json",
}
TEXT_SUFFIXES = {
    "", ".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".json", ".md",
    ".txt", ".bat", ".sh", ".ps1", ".yaml", ".yml", ".toml", ".svg", ".example",
    ".ai", ".per", ".dart", ".test", ".0",
}
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
KEY = re.compile(
    r"(?:gsk_|sk-proj-|ghp_|github_pat_|hf_)[A-Za-z0-9_-]{20,}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
MACHINE_PATH = re.compile(r"[A-Z]:[\\/]+(?:Users[\\/]+(?!user\b|Public\b)[^\\/\s\"']+|Venvglobal[\\/])", re.I)


def folded(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def identity_pattern(terms):
    # Also recognize names embedded in regexes, such as a vowel character class.
    words = []
    for term in terms:
        letters = []
        for char in folded(term):
            escaped = re.escape(char)
            letters.append(r"(?:" + escaped + r"|\[[^\]\r\n]{0,8}" + escaped + r"[^\]\r\n]{0,8}\])")
        words.append("".join(letters))
    return re.compile(r"(?:(?<!\w)|(?<=\\b))(?:" + "|".join(words) + r")(?!\w)", re.I) if words else None


def candidates(root=ROOT):
    output = subprocess.check_output(
        ["git", "-c", f"safe.directory={root.as_posix()}", "ls-files",
         "--cached", "--others", "--exclude-standard", "-z"], cwd=root
    )
    return sorted({p for p in output.decode("utf-8").split("\0") if p})


def load_identity(root=ROOT, denylist_path=None):
    # A private reference list can live outside the checkout.
    explicit = denylist_path or os.environ.get("PUBLIC_PRIVACY_DENYLIST")
    denylist_path = Path(explicit) if explicit else root / ".local" / "privacy-denylist.json"
    if explicit and not denylist_path.is_file():
        raise ValueError("The explicitly configured private denylist does not exist.")
    terms = json.loads(denylist_path.read_text(encoding="utf-8-sig")) if denylist_path.exists() else []
    if not isinstance(terms, list) or any(not isinstance(term, str) or len(term) < 3 for term in terms):
        raise ValueError("The private denylist must be a JSON array of strings (minimum length 3).")
    return identity_pattern(terms)


def private_path(relative):
    path = Path(relative)
    return (
        relative.startswith(PRIVATE_PREFIXES)
        or path.suffix.lower() in PRIVATE_SUFFIXES
        or path.name in PRIVATE_NAMES
        or (path.name.startswith(".env") and not path.name.endswith(".example"))
        or (relative.startswith("backend/data/") and path.name != ".gitkeep")
    )


def text_findings(text, identity=None):
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        line = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), line)
        for category, pattern in (("known-identity", identity), ("machine-path", MACHINE_PATH), ("credential", KEY)):
            if pattern is not None and pattern.search(folded(line) if category == "known-identity" else line):
                findings.append({"line": number, "category": category})
        for match in EMAIL.finditer(line):
            domain = match[1].lower()
            if domain not in ("example.com", "example.org", "example.net") and not domain.endswith((".invalid", ".example", ".local")):
                findings.append({"line": number, "category": "non-example-email"})
    return findings


def audit(root=ROOT, denylist_path=None):
    findings = []
    checked = 0
    identity = load_identity(root, denylist_path)
    for relative in candidates(root):
        path = root / relative
        if not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            findings.append({"file": relative, "line": 0, "category": "external-link"})
            continue
        checked += 1
        if private_path(relative):
            findings.append({"file": relative, "line": 0, "category": "private-artifact"})
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in (".gitignore", ".gitattributes"):
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError:
            findings.append({"file": relative, "line": 0, "category": "unexpected-binary"})
            continue
        findings.extend({"file": relative, **item} for item in text_findings(text, identity))
    return {"scope": "current working tree; Git history and ignored local data excluded",
            "private_denylist_loaded": identity is not None,
            "files_checked": checked, "finding_count": len(findings),
            "categories": dict(Counter(f["category"] for f in findings)),
            "findings": findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Write a redacted audit report.")
    parser.add_argument("--private-denylist", type=Path, help="Private JSON reference list, preferably outside the checkout.")
    args = parser.parse_args()
    report = audit(denylist_path=args.private_denylist)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f'Checked {report["files_checked"]} files; {report["finding_count"]} findings.')
    for item in report["findings"]:
        print(f'{item["file"]}:{item["line"]}: {item["category"]}')
    return int(bool(report["findings"]))


if __name__ == "__main__":
    sys.exit(main())
