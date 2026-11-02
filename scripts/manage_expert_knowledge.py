#!/usr/bin/env python3
"""Expert knowledge inventory, local-paper handling, and model operations."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gurumoji import method_experts  # noqa: E402
from gurumoji.obsidian_layout import unpack  # noqa: E402

EXIT_OK = 0
EXIT_NOT_CONFIGURED = 2
EXIT_UNREACHABLE = 3
EXIT_REJECTED_URL = 4
DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
PILOT_EXPERT_IDS = (
    "exp-thematic-analysis",
    "exp-framework-method",
    "exp-descriptive-statistics",
)


def _frontmatter(path: Path) -> dict[str, Any]:
    """Read only a note's YAML frontmatter, never its body."""
    return _frontmatter_result(path)[0]


def _frontmatter_result(path: Path) -> tuple[dict[str, Any], bool]:
    """Return properties and whether a terminated, parseable mapping exists."""
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            if handle.readline().strip() != "---":
                return {}, False
            lines = []
            terminated = False
            for line in handle:
                if line.rstrip("\r\n") == "---":
                    terminated = True
                    break
                lines.append(line)
        if not terminated:
            return {}, False
        props, _ = unpack("---\n" + "".join(lines) + "---\n")
        return (props, True) if isinstance(props, dict) else ({}, False)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError):
        return {}, False


def _visible_markdown(directory: Path) -> dict[str, Path]:
    if not directory.is_dir():
        return {}
    return {
        path.name: path for path in directory.glob("*.md")
        if path.name != "00-Index.md" and path.is_file()
    }


def inventory(catalog: method_experts.ExpertCatalog | None = None) -> dict[str, Any]:
    """Return aggregate counts only; do not serialize paths, note bodies, or claims."""
    catalog = catalog or method_experts.default_catalog()
    experts = catalog.index()
    local_literature = _visible_markdown(catalog.local_root / method_experts.LITERATURE_DIR)
    base_literature = _visible_markdown(catalog.root / method_experts.LITERATURE_DIR)
    literature = {**base_literature, **local_literature}
    note_states: Counter[str] = Counter()
    correction_states: Counter[str] = Counter()
    access_scopes: Counter[str] = Counter()
    malformed_frontmatter = 0
    for path in literature.values():
        props = _frontmatter(path)
        if not props:
            malformed_frontmatter += 1
        note_states[str(props.get("status") or "unspecified")] += 1
        correction_states[str(props.get("correction_status") or "unspecified")] += 1
        access_scopes[str(props.get("access_scope") or "unspecified")] += 1

    unresolved = 0
    definition_errors = 0
    references_total = 0
    for expert_id in experts:
        try:
            definition = catalog.definition(expert_id)
        except (method_experts.ExpertDefinitionError, OSError):
            definition_errors += 1
            continue
        for reference in definition.get("literature", []):
            references_total += 1
            relative = method_experts.LITERATURE_DIR / f"{reference}.md"
            if not (catalog.local_root / relative).is_file() and not (catalog.root / relative).is_file():
                unresolved += 1

    return {
        "schema_version": 1,
        "status": "ok",
        "experts": {"definitions": len(experts), "definition_errors": definition_errors},
        "literature": {
            "notes": len(literature),
            "local_overrides": len(set(local_literature) & set(base_literature)),
            "local_only": len(set(local_literature) - set(base_literature)),
            "status_counts": dict(sorted(note_states.items())),
            "correction_status_counts": dict(sorted(correction_states.items())),
            "access_scope_counts": dict(sorted(access_scopes.items())),
            "frontmatter_missing_or_invalid": malformed_frontmatter,
        },
        "references": {"declared": references_total, "unresolved": unresolved},
    }


def _note_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_https_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urllib.parse.urlsplit(value.strip())
        return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password
    except ValueError:
        return False


def _doi_or_https_url(props: dict[str, Any]) -> str | None:
    doi = props.get("doi")
    if isinstance(doi, (str, int)):
        value = str(doi).strip()
        if value.startswith("https://doi.org/"):
            parsed_doi_url = urllib.parse.urlsplit(value)
            if parsed_doi_url.netloc.lower() == "doi.org" and not parsed_doi_url.query and not parsed_doi_url.fragment:
                value = parsed_doi_url.path.lstrip("/")
            else:
                value = ""
        if _DOI_PATTERN.fullmatch(value):
            return value
    url = props.get("url")
    if not _valid_https_url(url):
        return None
    parsed_url = urllib.parse.urlsplit(url.strip())
    if parsed_url.query or parsed_url.fragment:
        return None
    return url.strip()


_LLM_ROUTES = {"local", "colab", "remote_llm", "export"}
_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[^\s\\\x00-\x1f\x7f?#]+$")


def _ai_llm_processing(props: dict[str, Any]) -> dict[str, Any]:
    """Return reviewed route permissions without conflating denial and missing evidence."""
    license_id = props.get("license_id")
    license_url = props.get("license_url")
    permission = props.get("llm_processing_permission")
    routes = props.get("llm_allowed_routes")
    affirmative = permission == "explicitly_permitted"
    reviewed_without_permission = permission == "not_explicitly_permitted"
    review_status = props.get("rights_review_status")
    reviewer = props.get("rights_reviewed_by")
    reviewed_at = props.get("rights_reviewed_at")
    basis = props.get("rights_review_basis")
    try:
        timestamp = datetime.fromisoformat(str(reviewed_at).replace("Z", "+00:00"))
        timestamp_valid = timestamp.tzinfo is not None and timestamp.utcoffset() is not None
    except (TypeError, ValueError):
        timestamp_valid = False
    license_valid = (isinstance(license_id, str) and bool(license_id.strip()) and
                     _valid_https_url(license_url))
    routes_valid = (isinstance(routes, list) and
                    all(isinstance(route, str) and route in _LLM_ROUTES for route in routes) and
                    len(routes) == len(set(routes)))
    review_complete = (license_valid and routes_valid and review_status == "approved" and
                       isinstance(reviewer, str) and bool(reviewer.strip()) and timestamp_valid and
                       isinstance(basis, str) and bool(basis.strip()))
    if review_complete and affirmative:
        route_status = {
            route: {"status": "permitted" if route in routes else "not_allowlisted",
                    "reason": "route_explicitly_reviewed" if route in routes else "route_not_in_reviewed_allowlist"}
            for route in sorted(_LLM_ROUTES)
        }
        return {"status": "reviewed", "reason": "reviewed_explicit_route_allowlist",
                "permission_decision": "explicitly_permitted", "routes": route_status}
    if review_complete and reviewed_without_permission and not routes:
        route_status = {
            route: {"status": "not_allowlisted", "reason": "reviewed_no_explicit_permission"}
            for route in sorted(_LLM_ROUTES)
        }
        return {"status": "reviewed", "reason": "reviewed_no_explicit_permission",
                "permission_decision": "not_explicitly_permitted", "routes": route_status}
    status = "review_pending" if affirmative else "unverified_no_llm_route"
    reason = "explicit_permission_lacks_validated_review" if affirmative else "no_explicit_affirmative_llm_permission"
    route_status = {route: {"status": "review_pending", "reason": reason} for route in sorted(_LLM_ROUTES)}
    return {"status": status, "reason": reason, "routes": route_status}


def source_audit(catalog: Any | None = None, *, expert_ids: list[str] | tuple[str, ...] | None = None,
                 all_experts: bool = False) -> dict[str, Any]:
    """Audit selected experts' literature metadata without parsing note bodies.

    The default remains the original three-expert pilot. Production callers build
    a Base-only catalog; tests may inject a fixture catalog.
    """
    if catalog is None:
        # ExpertCatalog normally overlays a personal runtime Vault. This audit is base-only.
        with tempfile.TemporaryDirectory(prefix="gurumoji-source-audit-") as empty_local:
            base_catalog = method_experts.ExpertCatalog(
                root=ROOT / "docs" / "program-vault", local_root=Path(empty_local))
            return source_audit(base_catalog, expert_ids=expert_ids, all_experts=all_experts)

    available = catalog.index()
    if all_experts and expert_ids is not None:
        raise ValueError("--all-experts cannot be combined with --expert-id")
    selected_ids = sorted(available) if all_experts else list(
        PILOT_EXPERT_IDS if expert_ids is None else expert_ids)
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("expert IDs must not be repeated")
    if any(not isinstance(expert_id, str) or not method_experts.EXPERT_ID.fullmatch(expert_id)
           for expert_id in selected_ids):
        raise ValueError("invalid expert ID")
    if any(expert_id not in available for expert_id in selected_ids):
        raise ValueError("unknown expert ID")
    for expert_id in selected_ids:
        entry = available[expert_id]
        source = entry.get("source") if isinstance(entry, dict) else None
        if source is not None and source != "base":
            raise ValueError("source-audit accepts Base-only expert definitions")

    records: list[dict[str, Any]] = []
    definition_errors = 0
    expert_summaries: list[dict[str, Any]] = []
    for expert_id in selected_ids:
        expert_records: list[dict[str, Any]] = []
        try:
            definition = catalog.definition(expert_id)
        except (method_experts.ExpertDefinitionError, OSError):
            definition_errors += 1
            expert_summaries.append({"expert_id": expert_id, "definition_error": True,
                                     "references": 0, "unresolved_refs": 0, "missing_status": 0,
                                     "missing_correction_status": 0, "missing_rights": 0})
            continue
        for note_id in definition.get("literature", []):
            relative = method_experts.LITERATURE_DIR / f"{note_id}.md"
            note_path = catalog.root / relative
            exists = note_path.is_file()
            props, frontmatter_valid = _frontmatter_result(note_path) if exists else ({}, False)
            resolution_status = "missing" if not exists else "invalid_frontmatter"
            if exists and frontmatter_valid:
                if props.get("note_type") != "literature":
                    resolution_status = "note_type_mismatch"
                elif props.get("literature_id") != note_id:
                    resolution_status = "literature_id_mismatch"
                else:
                    resolution_status = "resolved"
            ai_permission = _ai_llm_processing(props if resolution_status == "resolved" else {})
            year = props.get("year")
            if not isinstance(year, (str, int, float)) or isinstance(year, bool):
                year = None
            record = {
                "expert_id": expert_id,
                "note_id": note_id,
                "title": props.get("title") if isinstance(props.get("title"), str) else None,
                "year": year,
                "doi_or_url": _doi_or_https_url(props) if resolution_status == "resolved" else None,
                "note_sha256": _note_sha256(note_path) if exists else None,
                "status": props.get("status"),
                "correction_status": props.get("correction_status"),
                "access_scope": props.get("access_scope"),
                "rights_status": ai_permission["status"],
                "ai_llm_processing": ai_permission,
                "resolution_status": resolution_status,
                "resolved": resolution_status == "resolved",
            }
            records.append(record)
            expert_records.append(record)
        expert_summaries.append({
            "expert_id": expert_id,
            "definition_error": False,
            "references": len(expert_records),
            "unresolved_refs": sum(not record["resolved"] for record in expert_records),
            "missing_status": sum(not record["status"] for record in expert_records),
            "missing_correction_status": sum(not record["correction_status"] for record in expert_records),
            "missing_rights": sum(record["rights_status"] != "reviewed" for record in expert_records),
        })
    return {
        "schema_version": 1,
        "status": "ok",
        "scope": {"catalog": "base_only", "expert_ids": selected_ids},
        "experts": expert_summaries,
        "counts": {
            "experts": len(selected_ids),
            "definition_errors": definition_errors,
            "references": len(records),
            "unresolved_refs": sum(not record["resolved"] for record in records),
            "missing_status": sum(not record["status"] for record in records),
            "missing_correction_status": sum(not record["correction_status"] for record in records),
            "missing_rights": sum(record["rights_status"] != "reviewed" for record in records),
            "resolution_status_counts": dict(sorted(Counter(
                record["resolution_status"] for record in records).items())),
        },
        "records": records,
    }


def _is_loopback_url(base_url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            return False
        if parsed.path not in {"", "/", "/v1", "/v1/"}:
            return False
        host = parsed.hostname.rstrip(".").lower()
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False
    except ValueError:
        return False


def _gpu_memory() -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        if result.returncode != 0:
            return {"status": "unavailable"}
        devices = []
        for line in result.stdout.splitlines():
            fields = [part.strip() for part in line.split(",")]
            if len(fields) != 3:
                continue
            try:
                devices.append({"name": fields[0], "total_mib": int(fields[1]), "free_mib": int(fields[2])})
            except ValueError:
                continue
        return {"status": "available" if devices else "unavailable", "devices": devices}
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "unavailable"}


def preflight_local_llm(base_url: str | None, *, timeout: float = 3.0) -> tuple[dict[str, Any], int]:
    """GET /models only. Never loads a model or sends an inference request."""
    result: dict[str, Any] = {
        "schema_version": 1,
        "gpu": _gpu_memory(),
        "models": [],
        "api": {"status": "not_configured", "endpoint": None},
        "inference_performed": False,
        "model_load_requested": False,
    }
    if not base_url:
        result["exit_code"] = EXIT_NOT_CONFIGURED
        return result, EXIT_NOT_CONFIGURED
    base_url = base_url.rstrip("/")
    if not _is_loopback_url(base_url):
        result["api"] = {"status": "rejected_url", "endpoint": None}
        result["exit_code"] = EXIT_REJECTED_URL
        return result, EXIT_REJECTED_URL
    parsed = urllib.parse.urlsplit(base_url)
    endpoint = base_url if parsed.path.endswith("/v1") else base_url + "/v1"
    result["api"]["endpoint"] = endpoint + "/models"
    request = urllib.request.Request(endpoint + "/models", headers={"Accept": "application/json"}, method="GET")
    try:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        with opener.open(request, timeout=timeout) as response:
            payload = json.loads(response.read(1_000_001))
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("Invalid OpenAI-compatible models response")
        result["models"] = [str(row["id"]) for row in payload["data"]
                            if isinstance(row, dict) and isinstance(row.get("id"), (str, int))]
        result["api"]["status"] = "reachable"
        result["exit_code"] = EXIT_OK
        return result, EXIT_OK
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        result["api"]["status"] = "unreachable"
        result["exit_code"] = EXIT_UNREACHABLE
        return result, EXIT_UNREACHABLE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inventory", help="専門家・文献を本文なしで集計")
    source_parser = commands.add_parser("source-audit", help="文献メタデータとLLM処理権利を監査（本文は出力しません）")
    source_selection = source_parser.add_mutually_exclusive_group()
    source_selection.add_argument("--all-experts", action="store_true", help="Base-onlyの全専門家を監査")
    source_selection.add_argument("--expert-id", action="append", help="監査するexpert ID（繰り返し可）")
    preflight = commands.add_parser("preflight-local-llm", help="LM Studio /modelsとGPU空き容量を確認")
    preflight.add_argument("--base-url", default=os.environ.get("MOJIOKOSI_LMSTUDIO_BASE_URL", DEFAULT_BASE_URL),
                           help=f"loopback OpenAI互換base URL (default: {DEFAULT_BASE_URL}; env: MOJIOKOSI_LMSTUDIO_BASE_URL)")
    generate_candidate = commands.add_parser(
        "generate-gale-candidate",
        help="Generate one unapproved Gale candidate with local LM Studio",
    )
    generate_candidate.add_argument("--source-extraction-dir", required=True)
    generate_candidate.add_argument("--output-batch", required=True)
    generate_candidate.add_argument("--base-url", default=os.environ.get("MOJIOKOSI_LMSTUDIO_BASE_URL", DEFAULT_BASE_URL))
    generate_candidate.add_argument("--timeout", type=float, default=180.0)
    compile_bundle = commands.add_parser(
        "compile-gale-review-bundle",
        help="Compile a pending Gale candidate into a non-release review bundle",
    )
    compile_bundle.add_argument("--candidate-batch", required=True)
    compile_bundle.add_argument("--source-extraction-dir", required=True)
    compile_bundle.add_argument("--output", required=True)
    import_local = commands.add_parser(
        "import-local-paper",
        help="Import one user-selected PDF/TXT into a private local-only paper store",
    )
    import_local.add_argument("--source-root", required=True)
    import_local.add_argument("--relative-path", required=True)
    import_local.add_argument("--data-dir", required=True)
    import_local.add_argument("--installation-id", required=True)
    import_local.add_argument("--expert-id", required=True)
    import_local.add_argument("--title", required=True)
    import_local.add_argument("--author", action="append", default=[])
    import_local.add_argument("--publication-year", type=int)
    import_local.add_argument("--confirm-local-processing", action="store_true",
                              help="Attest that you selected this file and want local-only processing")
    search_local = commands.add_parser(
        "search-local-papers",
        help="Search explicitly imported private papers for one expert",
    )
    search_local.add_argument("--data-dir", required=True)
    search_local.add_argument("--installation-id", required=True)
    search_local.add_argument("--expert-id", required=True)
    search_local.add_argument("--query", required=True)
    search_local.add_argument("--limit", type=int, default=10)
    read_local = commands.add_parser(
        "read-local-evidence",
        help="Read one exact page/paragraph from an explicitly imported paper",
    )
    read_local.add_argument("--data-dir", required=True)
    read_local.add_argument("--installation-id", required=True)
    read_local.add_argument("--expert-id", required=True)
    read_local.add_argument("--source-id", required=True)
    read_local.add_argument("--anchor-id", required=True)
    args = parser.parse_args(argv)
    if args.command == "inventory":
        output, code = inventory(), EXIT_OK
    elif args.command == "source-audit":
        try:
            output = source_audit(expert_ids=args.expert_id, all_experts=args.all_experts)
        except ValueError as exc:
            parser.error(str(exc))
        code = EXIT_OK
    elif args.command == "generate-gale-candidate":
        from gurumoji.knowledge_builder import candidate_pipeline
        if not 0 < args.timeout <= 600:
            parser.error("--timeout must be greater than 0 and at most 600 seconds")
        try:
            output = candidate_pipeline.generate_gale_candidates_local(
                args.source_extraction_dir, args.output_batch,
                base_url=args.base_url, timeout=args.timeout,
            )
        except candidate_pipeline.CandidatePipelineError as exc:
            parser.error(str(exc))
        code = EXIT_OK
    elif args.command == "compile-gale-review-bundle":
        from gurumoji.knowledge_builder import candidate_pipeline
        try:
            output = candidate_pipeline.compile_candidate_review_bundle(
                args.candidate_batch, args.source_extraction_dir, args.output,
            )
        except candidate_pipeline.CandidatePipelineError as exc:
            parser.error(str(exc))
        code = EXIT_OK
    elif args.command in {"import-local-paper", "search-local-papers", "read-local-evidence"}:
        from gurumoji.knowledge_builder import source_ingestion
        catalog = method_experts.ExpertCatalog(
            root=ROOT / "docs" / "program-vault",
            local_root=ROOT / ".no-local-expert-overrides-for-builder",
        )
        expert_index = catalog.index()
        if (args.expert_id not in expert_index or
                expert_index[args.expert_id].get("source") != "base"):
            parser.error("--expert-id must name one of the 17 Software Vault experts")
        try:
            if args.command == "import-local-paper":
                result = source_ingestion.ingest_user_selected_local_paper(
                    args.source_root, args.relative_path, data_dir=args.data_dir,
                    installation_id=args.installation_id, expert_id=args.expert_id,
                    title=args.title, authors=args.author,
                    publication_year=args.publication_year,
                    confirm_local_processing=args.confirm_local_processing,
                )
                manifest = result["manifest"]
                output = {
                    "status": result["status"], "storage_class": result["storage_class"],
                    "storage_id": result["storage_id"], "expert_id": args.expert_id,
                    "source_id": manifest["source"]["source_id"],
                    "source_sha256": manifest["source"]["sha256"],
                    "excerpt_count": manifest["excerpt_count"],
                    "anchor_count": manifest["anchor_count"],
                    "completeness": manifest["completeness"],
                    "review_reasons": manifest["extractor"]["review_reasons"],
                    "route": "local_only",
                }
            elif args.command == "search-local-papers":
                results = source_ingestion.search_local_papers(
                    args.query, data_dir=args.data_dir, installation_id=args.installation_id,
                    expert_id=args.expert_id, limit=args.limit,
                )
                output = {"expert_id": args.expert_id, "result_count": len(results),
                          "results": results, "route": "local_only"}
            else:
                output = source_ingestion.read_local_evidence(
                    args.source_id, args.anchor_id, data_dir=args.data_dir,
                    installation_id=args.installation_id, expert_id=args.expert_id,
                )
                output["route"] = "local_only"
        except source_ingestion.SourceIngestionError as exc:
            parser.error(str(exc))
        except OSError:
            parser.error("local paper storage is inaccessible; filesystem paths were omitted")
        code = EXIT_OK
    else:
        output, code = preflight_local_llm(args.base_url)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
