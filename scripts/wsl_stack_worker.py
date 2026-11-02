"""専用プロセスグループでモデルを実行し、Windowsからの中止に対応する。"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def main():
    worker, request, pid_file, stopped_file = map(Path, sys.argv[1:])
    if os.getpgrp() != os.getpid():
        os.setsid()
    pid_file.write_text(str(os.getpid()), encoding="ascii")
    try:
        if stopped_file.exists():
            return
        sys.argv = [str(worker), str(request)]
        runpy.run_path(str(worker), run_name="__main__")
    finally:
        pid_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
