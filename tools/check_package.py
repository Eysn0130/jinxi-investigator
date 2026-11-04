#!/usr/bin/env python3
"""Check the public package structure, local links and obvious publication leaks."""
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/jinxi-investigator"
ALLOWED = {".md", ".py", ".csv", ".yaml", ".yml"}
IGNORED = {".git", "__pycache__"}
PATTERNS = [re.compile(r"/(?:Users|home)/"), re.compile(r"thread:/{2}"),
            re.compile(r"\b(?:sk|gh[pousr])[-_][A-Za-z0-9]{20,}\b"),
            re.compile(r"(?<![A-Za-z0-9])[0-9]{15,19}(?![A-Za-z0-9])")]


def main():
    errors = []
    count = 0
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        if any(part in IGNORED for part in rel.parts):
            continue
        if path.is_symlink():
            errors.append(str(rel) + ": symlink not allowed")
            continue
        if not path.is_file():
            continue
        count += 1
        if path.name not in ("LICENSE", ".gitignore") and path.suffix not in ALLOWED:
            errors.append(str(rel) + ": unexpected public file type")
            continue
        text = path.read_text(encoding="utf-8")
        if any(p.search(text) for p in PATTERNS):
            errors.append(str(rel) + ": possible private path, identifier or credential")
        if path.suffix == ".md":
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if target.startswith(("https://", "http://", "#")):
                    continue
                dest = (path.parent / unquote(target.split("#", 1)[0])).resolve()
                if (dest != ROOT and ROOT not in dest.parents) or not dest.exists():
                    errors.append(str(rel) + ": unresolved local link " + target)
    source = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    if not source.startswith("---\nname: jinxi-investigator\ndescription: ") or "\n---\n" not in source[4:]:
        errors.append("invalid skill frontmatter")
    for required in ["README.md", "LICENSE", "PUBLICATION.md", "skills/jinxi-investigator/agents/openai.yaml"]:
        if not (ROOT / required).is_file():
            errors.append("missing " + required)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print(f"Package structure, local links and basic publication scan passed ({count} files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
