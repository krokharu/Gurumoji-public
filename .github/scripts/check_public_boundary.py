"""公開ブランチの履歴に個人データ・認証情報・内部資産が入っていないか検査する。"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import PurePosixPath

FORBIDDEN_PARTS = {
    ".codex", ".agents", ".claude", ".obsidian", "ObusSQL", "runtime",
    "output", "scratch", "devtools", "tests", "fixtures", "reports",
    "experiments", "backups", "uploads", "models",
}
FORBIDDEN_SUFFIXES = {
    ".recovered", ".bak", ".orig", ".rej", ".db", ".sqlite", ".sqlite3",
    ".pem", ".key", ".p12", ".pfx", ".wav", ".mp3", ".mp4", ".safetensors",
    ".pt", ".pth", ".gguf",
}
SECRET_PATTERNS = {
    "秘密鍵": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
    "プロバイダーキー": re.compile(r"\b(?:hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-(?:proj-|svcacct-|ant-)?[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,}|(?:AKIA|ASIA)[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{20,})"),
    "認証URL": re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s/\x22\x27:]+:[^\s/@\x22\x27]+@"),
    "認証値の直書き": re.compile(r"(?i)[\x22\x27]?(?:api[_-]?key|access[_-]?token|hf[_-]?token|secret[_-]?key|client[_-]?secret|password|passwd|auth[_-]?token)[\x22\x27]?\s*[:=]\s*[\x22\x27][^\x22\x27\r\n]{6,}[\x22\x27]"),
    "個人の絶対パス": re.compile(r"(?:[A-Za-z]:[\\/]+Users[\\/]+[^\s\x22\x27<>]+|/[h]ome/[^/\s\x22\x27]+/[^\s\x22\x27]*)"),
}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-c", "core.quotePath=false", *args])


def main() -> int:
    records = git("rev-list", "--objects", "HEAD").decode("utf-8").splitlines()
    errors: set[str] = set()
    blob_count = 0
    process = subprocess.Popen(["git", "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    assert process.stdin is not None and process.stdout is not None
    try:
        for record in records:
            oid, _, name = record.partition(" ")
            if not name:
                continue
            path = PurePosixPath(name)
            if (set(path.parts) & FORBIDDEN_PARTS or path.suffix.lower() in FORBIDDEN_SUFFIXES
                    or path.name == "tokens.json" or path.name == ".env"
                    or path.name.startswith(".env.") and path.name != ".env.example"
                    or any(part.startswith(".venv") for part in path.parts)):
                errors.add(f"公開対象外のパス: {name}")
            process.stdin.write((oid + "\n").encode())
            process.stdin.flush()
            header = process.stdout.readline().split()
            data = process.stdout.read(int(header[2]))
            process.stdout.read(1)
            if header[1] != b"blob":
                continue
            blob_count += 1
            if b"\0" in data:
                continue
            text = data.decode("utf-8", errors="replace")
            for number, line in enumerate(text.splitlines(), 1):
                for label, pattern in SECRET_PATTERNS.items():
                    if pattern.search(line):
                        # 秘密値をログへ出さず、位置と分類だけを報告する。
                        errors.add(f"{label}: {name}:{number}")
            if path.suffix == ".ipynb":
                notebook = json.loads(text)
                if any(cell.get("outputs") or cell.get("execution_count") is not None for cell in notebook.get("cells", []) if cell.get("cell_type") == "code"):
                    errors.add(f"ノートブックの実行結果: {name}")
    finally:
        process.stdin.close()
        process.wait()
    if errors:
        print("\n".join(sorted(errors)), file=sys.stderr)
        return 1
    print(f"公開範囲の検査成功: 履歴内の{blob_count} blob")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
