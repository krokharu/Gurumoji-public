"""Verify the published Qwen3 GGUF and retain the old file before replacement.

The model must be unloaded from LM Studio before using --repair.
"""
import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

REPOSITORY = 'lmstudio-community/Qwen3-8B-GGUF'
FILENAME = 'Qwen3-8B-Q4_K_M.gguf'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('model_path', type=Path)
    parser.add_argument('--repair', action='store_true')
    args = parser.parse_args()
    path = args.model_path.resolve(strict=True)
    with urllib.request.urlopen(f'https://huggingface.co/api/models/{REPOSITORY}/revision/main', timeout=30) as response:
        revision = json.load(response)['sha']
    with urllib.request.urlopen(f'https://huggingface.co/api/models/{REPOSITORY}/tree/{revision}', timeout=30) as response:
        entry = next(row for row in json.load(response) if row.get('path') == FILENAME)
    expected = entry['lfs']['oid']
    original = digest(path)
    print(json.dumps({'revision': revision, 'expected_sha256': expected, 'local_sha256': original}), flush=True)
    if original == expected:
        print('Verified: already matches the published file.', flush=True)
        return
    if not args.repair:
        raise SystemExit('Mismatch. Use --repair with the model unloaded to download a verified replacement.')
    candidate = path.with_suffix('.verified-download.part')
    url = f'https://huggingface.co/{REPOSITORY}/resolve/{revision}/{FILENAME}?download=true'
    downloaded = 0
    last = time.monotonic()
    sha = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=60) as response, candidate.open('wb') as stream:
        while chunk := response.read(8 * 1024 * 1024):
            stream.write(chunk)
            sha.update(chunk)
            downloaded += len(chunk)
            if time.monotonic() - last > 10:
                print(f'Downloaded {downloaded / entry["size"]:.0%}', flush=True)
                last = time.monotonic()
    if downloaded != entry['size'] or sha.hexdigest() != expected:
        raise SystemExit('Downloaded file failed verification. Original file is untouched.')
    backup = path.with_suffix(f'.gguf.backup-{original[:12]}')
    if backup.exists():
        raise SystemExit(f'Backup already exists: {backup}. Original file is untouched.')
    path.rename(backup)
    try:
        candidate.rename(path)
    except OSError:
        backup.rename(path)
        raise
    print(json.dumps({'verified_sha256': expected, 'backup': str(backup), 'model_path': str(path)}), flush=True)


if __name__ == '__main__':
    main()
