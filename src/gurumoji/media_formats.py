"""Accepted media container extensions.

Both the upload edge and the analysis evidence inventory need to agree on what
counts as a video rather than audio-only source, so the sets live here instead
of in either caller.
"""

from __future__ import annotations

ALLOWED_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv", ".wav", ".mp3", ".m4a", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv"}
