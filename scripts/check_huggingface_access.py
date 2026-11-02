"""Check access to every gated Hugging Face repository used by the app."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from huggingface_hub import HfApi, get_hf_file_metadata, hf_hub_url


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
TOKEN_FILE = PROJECT_DIRECTORY / "config" / "tokens.json"
CHECK_GROUPS = (
    (
        "Speaker diarization agreements",
        (
            ("pyannote/speaker-diarization-3.1", "config.yaml"),
            ("pyannote/segmentation-3.0", "config.yaml"),
            ("pyannote/speaker-diarization-community-1", "config.yaml"),
        ),
    ),
    (
        "AIST emotion analysis agreements",
        (
            (
                "imprt/kushinada-hubert-large-jtes-er",
                "s3prl/jtes/Session1/train_meta_data.json",
            ),
            (
                "imprt/kushinada-hubert-large",
                "s3prl/kushinada-hubert-large-s3prl.pt",
            ),
            (
                "imprt/izanami-wav2vec2-large-jtes-er",
                "s3prl/jtes/Session1/train_meta_data.json",
            ),
            (
                "imprt/izanami-wav2vec2-large",
                "s3prl/izanami-wav2vec2-large-s3prl.pt",
            ),
        ),
    ),
)


def load_token() -> str:
    try:
        payload = json.loads(TOKEN_FILE.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return ""
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[NG] Hugging Face token: cannot read {TOKEN_FILE.name} ({exc})")
        return ""
    return str(payload.get("huggingface_token") or "").strip()


def access_error(exc: Exception) -> str:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    if status_code == 401:
        return "token is invalid or expired"
    if status_code == 403 or exc.__class__.__name__ == "GatedRepoError":
        return "agreement has not been accepted for this account"
    if status_code == 404:
        return "required file was not found or access is denied"
    return f"{exc.__class__.__name__}: {str(exc).splitlines()[0]}"


def check_repository(token: str, repo_id: str, filename: str) -> tuple[bool, str]:
    try:
        # A metadata HEAD request validates gated-file access without downloading
        # the large model weights.
        get_hf_file_metadata(hf_hub_url(repo_id, filename), token=token)
        return True, "accessible"
    except Exception as exc:  # The hub exposes several HTTP exception subclasses.
        return False, access_error(exc)


def main() -> int:
    print()
    print("=" * 68)
    print("HUGGING FACE ACCESS CHECK")
    print("=" * 68)
    token = load_token()
    token_ok = False
    if not token:
        print("[NG] 1/3 Token authentication: huggingface_token is missing")
    else:
        try:
            HfApi(token=token).whoami()
            token_ok = True
            print("[OK] 1/3 Token authentication")
        except Exception as exc:
            print(f"[NG] 1/3 Token authentication: {access_error(exc)}")

    checks = [item for _, group in CHECK_GROUPS for item in group]
    results: dict[str, tuple[bool, str]] = {}
    if token_ok:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(check_repository, token, repo_id, filename): repo_id
                for repo_id, filename in checks
            }
            for future in as_completed(futures):
                results[futures[future]] = future.result()
    else:
        results = {repo_id: (False, "token authentication failed") for repo_id, _ in checks}

    for group_index, (group_name, group) in enumerate(CHECK_GROUPS, start=2):
        print()
        ok_count = 0
        for repo_id, _ in group:
            ok, detail = results[repo_id]
            ok_count += int(ok)
            print(f"  [{'OK' if ok else 'NG'}] {repo_id}")
            if not ok:
                print(f"       {detail}")
        group_ok = ok_count == len(group)
        print(
            f"[{'OK' if group_ok else 'NG'}] {group_index}/3 {group_name}: "
            f"{ok_count}/{len(group)} repositories accessible"
        )

    accessible = sum(int(ok) for ok, _ in results.values())
    all_ok = token_ok and accessible == len(checks)
    print()
    print("-" * 68)
    print(f"Repository total: {accessible}/{len(checks)} accessible")
    print("ALL HUGGING FACE CHECKS: " + ("OK" if all_ok else "NG"))
    print("-" * 68)
    failed_repositories = [repo_id for repo_id, _ in checks if not results[repo_id][0]]
    if failed_repositories:
        print()
        print("AGREEMENT LINKS FOR NG REPOSITORIES")
        print("Open each link with the same account used by tokens.json:")
        for repo_id in failed_repositories:
            print(f"  https://huggingface.co/{repo_id}")
        print()
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
