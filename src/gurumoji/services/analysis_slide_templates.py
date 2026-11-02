"""Load reviewed templates only when their Software Vault design is present.

The fixed repository paths are application-owned configuration. They are never
accepted from an HTTP request, and no prompt is executed by this loader.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..analysis_core import AnalysisContractError

DESIGN_PATH = "docs/program-vault/40-Design/60-Output/slide-generation-design-and-prompts/00-Index.md"
CATALOG_PATH = "config/analysis_slide_templates.json"


def load_slide_templates(project_root: Path) -> dict:
    catalog_path = Path(project_root) / CATALOG_PATH
    if not catalog_path.is_file():
        return {}
    raw = catalog_path.read_bytes()
    if len(raw) > 256 * 1024:
        raise AnalysisContractError("スライド設計カタログが上限を超えています。", code="slide_design_unverified")
    try:
        catalog = json.loads(raw)
        document = catalog["design_document"]
        if catalog["schema_version"] != 1 or document["path"] != DESIGN_PATH:
            raise ValueError
        digest = hashlib.sha256((Path(project_root) / DESIGN_PATH).read_bytes()).hexdigest()
        if document["sha256"] != digest or not isinstance(catalog["templates"], dict):
            raise ValueError
        parts=document.get('parts',{})
        if not isinstance(parts,dict) or set(parts)!={f'{index:02d}-section.md' for index in range(1,6)}: raise ValueError
        for name,expected_hash in parts.items():
            if name not in {f'{index:02d}-section.md' for index in range(1,6)}: raise ValueError
            if hashlib.sha256((Path(project_root)/DESIGN_PATH).with_name(name).read_bytes()).hexdigest()!=expected_hash:
                raise ValueError
        return catalog["templates"]
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise AnalysisContractError(
            "Software Vaultの採用設計とテンプレートが一致しません。設計記録を確認してください。",
            code="slide_design_unverified",
        ) from exc
