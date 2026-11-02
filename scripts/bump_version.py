"""Bump or check the app version (rules: docs/DEVELOPMENT.md).

Format: [β]MAJOR.MINOR.PATCH, e.g. β0.46.1. APP_VERSION in app.py is the source
of truth; the README sentence is kept in step with it.

  bump_version.py check   format, README match, and β vs. remaining "Coming Soon"
  bump_version.py info    print the current version and its tag
  bump_version.py auto  --subjects FILE   subjects of the pushed commits, one per line
  bump_version.py patch | minor | major | release | beta-on | beta-off

With --github-output the new version, tag and whether anything changed are
appended to $GITHUB_OUTPUT. Only the stdlib is used.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "src" / "gurumoji" / "app.py"
README_PATH = ROOT / "README.md"
APP_RE = re.compile(r'^(APP_VERSION\s*=\s*")([^"]+)(")', re.MULTILINE)
README_RE = re.compile(r"(バージョンは)([^。]+?)(です。)")
VERSION_RE = re.compile(r"^(β?)(\d+)\.(\d+)\.(\d+)$")
FEATURE_RE = re.compile(r"^feat(\([^)]*\))?!?:")
SKIP_RE = re.compile(r"^(docs|chore|ci|test|style)(\([^)]*\))?!?:|^chore\(release\)")


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def write(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))  # keep the repo's LF endings


def current_version() -> str:
    match = APP_RE.search(read(APP_PATH))
    if not match:
        raise SystemExit("APP_VERSION が app.py に見つかりません。")
    return match.group(2)


def parse(version: str) -> tuple[bool, int, int, int]:
    match = VERSION_RE.match(version)
    if not match:
        raise SystemExit(f"版の書式が不正です: {version}（例: β0.46.1）")
    return bool(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))


def fmt(beta: bool, major: int, minor: int, patch: int) -> str:
    return f"{'β' if beta else ''}{major}.{minor}.{patch}"


def tag_for(version: str) -> str:
    beta, major, minor, patch = parse(version)
    return f"public/v{major}.{minor}.{patch}" + ("-beta" if beta else "")


def decide_auto(subjects: list[str]) -> str:
    """feat: -> minor, docs/chore/ci/test/style only -> none, anything else -> patch."""
    subjects = [s.strip() for s in subjects if s.strip()]
    if any(FEATURE_RE.match(s) for s in subjects):
        return "minor"
    if any(not SKIP_RE.match(s) for s in subjects):
        return "patch"
    return "none"


def bump(version: str, kind: str) -> str:
    beta, major, minor, patch = parse(version)
    if kind == "patch":
        patch += 1
    elif kind == "minor":
        minor, patch = minor + 1, 0
    elif kind == "major":
        major, minor, patch = major + 1, 0, 0
    elif kind == "release":  # product release: drop β, 0 -> 1
        beta, major, minor, patch = False, max(major, 0) + 1, 0, 0
    elif kind == "beta-on":
        beta = True
    elif kind == "beta-off":
        beta = False
    else:
        raise SystemExit(f"不明な種別: {kind}")
    return fmt(beta, major, minor, patch)


def coming_soon_files() -> list[str]:
    found = []
    for folder in (ROOT / "src" / "gurumoji" / "templates", ROOT / "src" / "gurumoji" / "static"):
        for path in sorted(folder.rglob("*")):
            if path.suffix in {".html", ".js"} and "coming soon" in read(path).lower():
                found.append(path.relative_to(ROOT).as_posix())
    return found


def check() -> None:
    version = current_version()
    beta = parse(version)[0]
    readme = README_RE.search(read(README_PATH))
    if not readme or readme.group(2) != version:
        raise SystemExit(f"READMEの版表記が APP_VERSION（{version}）と一致しません。")
    soon = coming_soon_files()
    if soon and not beta:
        # Coming Soon が残る間はβを外さない（docs/DEVELOPMENT.md）
        raise SystemExit(f"Coming Soon が残っているのにβが付いていません: {', '.join(soon)}")
    if beta and not soon:
        print("::warning::Coming Soon が画面に残っていません。製品版にするなら手動実行の release / beta-off を使えます。")
    print(f"OK {version}")


def apply(new_version: str) -> None:
    write(APP_PATH, APP_RE.sub(lambda m: m.group(1) + new_version + m.group(3), read(APP_PATH), count=1))
    write(README_PATH, README_RE.sub(lambda m: m.group(1) + new_version + m.group(3), read(README_PATH), count=1))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # β must survive Windows consoles
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["check", "info", "auto", "patch", "minor", "major", "release", "beta-on", "beta-off"])
    parser.add_argument("--subjects", type=Path, help="auto: file with one commit subject per line")
    parser.add_argument("--github-output", action="store_true")
    args = parser.parse_args()

    if args.command == "check":
        check()
        return 0

    old = current_version()
    if args.command == "info":
        print(f"{old} {tag_for(old)}")
        if args.github_output and os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
                out.write(f"version={old}\ntag={tag_for(old)}\nprerelease={'true' if parse(old)[0] else 'false'}\n")
        return 0
    kind = args.command
    if kind == "auto":
        if not args.subjects:
            parser.error("auto には --subjects が必要です。")
        kind = decide_auto(args.subjects.read_text(encoding="utf-8").splitlines())
    new = old if kind == "none" else bump(old, kind)
    changed = new != old
    if changed:
        apply(new)
    print(f"{old} -> {new} ({kind})")
    if args.github_output and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            out.write(f"changed={'true' if changed else 'false'}\nversion={new}\ntag={tag_for(new)}\nkind={kind}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
