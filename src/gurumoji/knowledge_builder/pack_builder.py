"""Build deterministic Base Packs from accepted Commit artifacts only."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
import tempfile
from typing import Any

from . import contracts
from .job_store import KnowledgeJobStore
from gurumoji import method_experts


class PackBuildError(ValueError):
    """A candidate Base Pack violates its pinned inputs or runtime safety gates."""


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise PackBuildError(f"unsupported expert definition value type: {type(value).__name__}")


def _definition_bytes(expert_id: str, definition: Mapping[str, Any]) -> bytes:
    if definition.get("expert_id") != expert_id:
        raise PackBuildError(f"expert definition ID mismatch: {expert_id}")
    try:
        contracts._reject_answer_material(definition)
        return contracts.canonical_json(_json_safe(dict(definition)))
    except contracts.ContractError as exc:
        raise PackBuildError(f"invalid expert definition: {expert_id}") from exc


def compute_base_root_sha256(definition_hashes: Mapping[str, str],
                             source_note_hashes: Mapping[str, str]) -> str:
    """Hash validated definitions together with their exact base source-note bytes."""
    if len(definition_hashes) != 17 or set(definition_hashes) != set(source_note_hashes):
        raise PackBuildError("Base Pack pin must contain exactly 17 expert definitions")
    for expert_id, digest in definition_hashes.items():
        try:
            contracts._id(expert_id, "expert_id")
            contracts._hash(digest, "definition_sha256")
            contracts._hash(source_note_hashes[expert_id], "source_note_sha256")
        except contracts.ContractError as exc:
            raise PackBuildError("invalid expert definition hash inventory") from exc
    rows = [{"expert_id": expert_id, "source_note_sha256": source_note_hashes[expert_id],
             "definition_sha256": digest}
            for expert_id, digest in sorted(definition_hashes.items())]
    return contracts.sha256_json(rows)


def _load_base_catalog_data() -> tuple[dict[str, dict], dict[str, str], str]:
    """Read the canonical Software Vault expert definitions with local overlay disabled."""
    with tempfile.TemporaryDirectory(prefix="gurumoji-base-pack-") as empty_local:
        catalog = method_experts.ExpertCatalog(
            root=method_experts.SOFTWARE_ROOT, local_root=empty_local)
        entries = catalog.index()
        if len(entries) != 17 or any(entry.get("source") != "base" for entry in entries.values()):
            raise PackBuildError("Software Vault must provide exactly 17 base ExpertCatalog entries")
        definitions: dict[str, dict] = {}
        source_note_hashes: dict[str, str] = {}
        for expert_id in sorted(entries):
            definition = catalog.definition(expert_id)
            entry = entries[expert_id]
            note_path = catalog.root / method_experts.EXPERTS_DIR / entry["folder"] / method_experts.DEFINITION_NOTE
            try:
                note_bytes = note_path.read_bytes()
            except OSError as exc:
                raise PackBuildError(f"base expert source note is unavailable: {expert_id}") from exc
            definitions[expert_id] = definition
            source_note_hashes[expert_id] = hashlib.sha256(note_bytes).hexdigest()
        definition_hashes = {expert_id: hashlib.sha256(_definition_bytes(expert_id, definition)).hexdigest()
                             for expert_id, definition in definitions.items()}
        root_hash = compute_base_root_sha256(definition_hashes, source_note_hashes)
        return definitions, source_note_hashes, root_hash


def _is_private_or_local_source(source: dict) -> bool:
    return (source["rights"]["classification"] == "private" or
            source["access_scope"] == "local_private" or
            source["locator"]["kind"] == "local_uri" or
            set(source["rights"]["allowed_routes"]) == {"local"})


def _build_base_pack_from_inputs(
    store: KnowledgeJobStore,
    *,
    pack_id: str,
    accepted_job_ids: Sequence[str],
    expert_definitions: Mapping[str, Mapping[str, Any]],
    source_note_hashes: Mapping[str, str],
    expected_base_root_sha256: str,
    distribution_route: str,
    compiler_version: str,
) -> dict:
    """Write Base Pack files and return a manifest accepted by ``register_pack``.

    Private fixture seam. Public callers cannot inject expert definitions or their hashes.
    """
    if (not accepted_job_ids or any(not isinstance(job_id, str) for job_id in accepted_job_ids) or
            len(set(accepted_job_ids)) != len(accepted_job_ids)):
        raise PackBuildError("accepted_job_ids must be non-empty and unique")
    contracts._id(pack_id, "pack_id")
    try:
        contracts._text(compiler_version, "compiler_version", max_length=200)
    except contracts.ContractError as exc:
        raise PackBuildError("invalid compiler_version") from exc
    if len(expert_definitions) != 17 or set(expert_definitions) != set(source_note_hashes):
        raise PackBuildError("expert definitions must exactly match the 17-entry base inventory")
    if distribution_route not in contracts.ROUTES:
        raise PackBuildError("invalid distribution route")

    definition_payloads: dict[str, bytes] = {}
    actual_definition_hashes: dict[str, str] = {}
    for expert_id in sorted(expert_definitions):
        data = _definition_bytes(expert_id, expert_definitions[expert_id])
        definition_payloads[expert_id] = data
        actual_definition_hashes[expert_id] = hashlib.sha256(data).hexdigest()
    actual_base_root = compute_base_root_sha256(actual_definition_hashes, source_note_hashes)
    if actual_base_root != expected_base_root_sha256:
        raise PackBuildError("expert definition inventory does not match the pinned Base root")

    commits: list[dict] = []
    source_records: dict[str, dict] = {}
    claim_records: dict[str, dict] = {}
    for job_id in sorted(accepted_job_ids):
        commit = store.accepted_commit(job_id)
        payloads = store._read_and_validate_artifacts(job_id, commit["generation"], commit)
        commits.append({"job_id": job_id, "generation": commit["generation"],
                        "manifest_sha256": commit["manifest_sha256"]})
        for record_type, record in payloads:
            if record_type == "Source":
                source_id = record["source_id"]
                if source_id in source_records:
                    raise PackBuildError(f"duplicate Source ID across accepted Commits: {source_id}")
                source = contracts.validate_source(record)
                if _is_private_or_local_source(source):
                    raise PackBuildError("private or local paper Source is forbidden in a Base Pack")
                source_records[source_id] = source
            elif record_type == "Claim":
                claim_id = record["claim_id"]
                if claim_id in claim_records:
                    raise PackBuildError(f"duplicate Claim ID across accepted Commits: {claim_id}")
                claim_records[claim_id] = record
            else:
                raise PackBuildError("unsupported accepted artifact in Base Pack")

    if not source_records or not claim_records:
        raise PackBuildError("Base Pack requires accepted Source and Claim records")
    if any(claim["status"] != "approved" for claim in claim_records.values()):
        raise PackBuildError("Base Pack may contain only approved Claims")
    expert_ids = set(expert_definitions)
    if any(claim["expert_id"] not in expert_ids for claim in claim_records.values()):
        raise PackBuildError("Claim references an expert missing from the pinned Base definitions")
    for claim in claim_records.values():
        try:
            contracts.validate_claim(claim, sources=source_records)
        except contracts.ContractError as exc:
            raise PackBuildError(f"accepted Claim failed Source integrity validation: {exc}") from exc
    try:
        contracts.authorize_route([*source_records.values(), *claim_records.values()],
                                  distribution_route, sources=source_records)
    except (contracts.ContractError, PermissionError) as exc:
        raise PackBuildError(f"Base Pack route is not authorized: {exc}") from exc

    files: list[dict] = []
    file_payloads: list[tuple[str, bytes, str, str | None]] = []
    source_data = b"".join(contracts.canonical_json(source_records[key]) + b"\n"
                            for key in sorted(source_records))
    claim_data = b"".join(contracts.canonical_json(claim_records[key]) + b"\n"
                           for key in sorted(claim_records))
    file_payloads.extend([
        ("knowledge/sources.jsonl", source_data, "knowledge_source", None),
        ("knowledge/claims.jsonl", claim_data, "knowledge_claim", None),
    ])
    for expert_id, data in definition_payloads.items():
        file_payloads.append((f"experts/{expert_id}.json", data, "expert_definition", expert_id))
    for relative, data, role, expert_id in file_payloads:
        item = {"path": relative, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "role": role}
        if expert_id is not None:
            item["expert_id"] = expert_id
        files.append(item)

    manifest = {
        "schema_version": contracts.SCHEMA_VERSION,
        "pack_id": pack_id,
        "flavor": "base",
        # export here is a Source-rights route only; this candidate is not release-approved.
        "stage": "internal_candidate",
        "distribution_route": distribution_route,
        "compiler_version": compiler_version,
        "experts": [{"expert_id": expert_id,
                     "source_note_sha256": source_note_hashes[expert_id],
                     "definition_sha256": actual_definition_hashes[expert_id]}
                    for expert_id in sorted(actual_definition_hashes)],
        "commits": commits,
        "claim_ids": sorted(claim_records),
        "source_ids": sorted(source_records),
        "files": files,
        "base_root_sha256": actual_base_root,
        "overlay_root_sha256": None,
    }
    manifest["root_sha256"] = contracts.sha256_json(manifest)
    try:
        validated_manifest = contracts.validate_pack_manifest(manifest)
    except contracts.ContractError as exc:
        raise PackBuildError(f"generated Pack manifest is invalid: {exc}") from exc

    pack_directory_key = hashlib.sha256(pack_id.encode("utf-8")).hexdigest()
    expected_directory = store.staging_root / "packs" / pack_directory_key
    if expected_directory.exists() or expected_directory.is_symlink() or \
            getattr(expected_directory, "is_junction", lambda: False)():
        raise PackBuildError("Pack staging directory already exists")
    directory = store.pack_staging_dir(pack_id)
    if any(directory.iterdir()):
        raise PackBuildError("Pack staging directory is not empty")
    written: list[Any] = []
    try:
        for relative, data, _role, _expert_id in file_payloads:
            path = store._artifact_path(directory, relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                written.append(path)
                handle.write(data)
        manifest_path = store._artifact_path(directory, "pack-manifest.json")
        with manifest_path.open("xb") as handle:
            written.append(manifest_path)
            handle.write(contracts.canonical_json(validated_manifest))
    except BaseException:
        for path in reversed(written):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        directories = {parent for path in written for parent in path.parents if parent == directory or directory in parent.parents}
        for folder in sorted(directories, key=lambda item: len(item.parts), reverse=True):
            try:
                folder.rmdir()
            except OSError:
                pass
        try:
            directory.rmdir()
        except OSError:
            pass
        raise
    return validated_manifest


def build_base_pack(
    store: KnowledgeJobStore,
    *,
    pack_id: str,
    accepted_job_ids: Sequence[str],
    expected_base_root_sha256: str,
    distribution_route: str,
    compiler_version: str,
) -> dict:
    """Build using only the 17 validated definitions in the base Software Vault."""
    definitions, source_note_hashes, actual_base_root = _load_base_catalog_data()
    if actual_base_root != expected_base_root_sha256:
        raise PackBuildError("Software Vault definitions do not match the pinned Base root")
    return _build_base_pack_from_inputs(
        store, pack_id=pack_id, accepted_job_ids=accepted_job_ids,
        expert_definitions=definitions, source_note_hashes=source_note_hashes,
        expected_base_root_sha256=expected_base_root_sha256,
        distribution_route=distribution_route, compiler_version=compiler_version,
    )


def build_local_papers_overlay(
    store: KnowledgeJobStore,
    *,
    pack_id: str,
    base_pack_path: str | Path,
    expected_base_pack_root_sha256: str,
    installation_id: str,
    accepted_job_ids: Sequence[str],
    adoption_records: Sequence[Mapping[str, Any]],
    compiler_version: str,
) -> dict:
    """Build a local-only additive Pack pinned to one accepted Base Pack.

    Accepted Source and Claim IDs must already use ``local:<installation_id>:``.
    Namespacing must happen before review so that the reviewer approval remains
    bound to the exact Claim that enters the overlay. Each Claim also needs a
    separate adoption record reviewed against this installation, Base root,
    Claim hash, and current cited Source versions.
    """
    if (not accepted_job_ids or any(not isinstance(job_id, str) for job_id in accepted_job_ids) or
            len(set(accepted_job_ids)) != len(accepted_job_ids)):
        raise PackBuildError("accepted_job_ids must be non-empty and unique")
    contracts._id(pack_id, "pack_id")
    try:
        contracts._text(compiler_version, "compiler_version", max_length=200)
        if (not isinstance(installation_id, str) or
                not contracts._INSTALLATION_ID.fullmatch(installation_id)):
            raise contracts.ContractError("invalid installation_id")
        contracts._hash(expected_base_pack_root_sha256, "expected_base_pack_root_sha256")
    except contracts.ContractError as exc:
        raise PackBuildError("invalid Local Papers overlay pin or compiler version") from exc

    base_directory = Path(base_pack_path).resolve()
    try:
        base_manifest = contracts.validate_pack_manifest(
            json.loads((base_directory / "pack-manifest.json").read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, contracts.ContractError) as exc:
        raise PackBuildError("pinned Base Pack manifest is unavailable or invalid") from exc
    if (base_manifest["flavor"] != "base" or base_manifest["stage"] != "internal_candidate" or
            base_manifest["root_sha256"] != expected_base_pack_root_sha256 or
            len(base_manifest["experts"]) != 17):
        raise PackBuildError("Local Papers overlay requires the exact pinned 17-expert Base Pack")
    from .expert_knowledge_context import load_expert_pack
    try:
        base_context = load_expert_pack(base_directory, expected_base_pack_root_sha256, "local",
                                        allow_internal_candidate=True)
    except ValueError as exc:
        raise PackBuildError("pinned Base Pack files failed reader validation") from exc

    base_expert_ids = {item["expert_id"] for item in base_manifest["experts"]}
    base_source_ids = set(base_context.sources)
    base_claim_ids = set(base_context.claims)
    expert_payloads: dict[str, bytes] = {}
    for expert in base_manifest["experts"]:
        descriptor = next((item for item in base_manifest["files"]
                           if item["role"] == "expert_definition" and
                           item.get("expert_id") == expert["expert_id"]), None)
        if descriptor is None:
            raise PackBuildError("pinned Base Pack is missing an expert definition")
        path = (base_directory / descriptor["path"]).resolve()
        if base_directory not in path.parents or path.is_symlink() or not path.is_file():
            raise PackBuildError("pinned Base Pack expert definition path is invalid")
        data = path.read_bytes()
        if len(data) != descriptor["size_bytes"] or hashlib.sha256(data).hexdigest() != descriptor["sha256"]:
            raise PackBuildError("pinned Base Pack expert definition changed during overlay build")
        expert_payloads[expert["expert_id"]] = data

    source_namespace = f"local:{installation_id}:source:"
    claim_namespace = f"local:{installation_id}:claim:"
    commits: list[dict] = []
    source_records: dict[str, dict] = {}
    claim_records: dict[str, dict] = {}
    for job_id in sorted(accepted_job_ids):
        commit = store.accepted_commit(job_id)
        payloads = store._read_and_validate_artifacts(job_id, commit["generation"], commit)
        commits.append({"job_id": job_id, "generation": commit["generation"],
                        "manifest_sha256": commit["manifest_sha256"]})
        for record_type, record in payloads:
            if record_type == "Source":
                source = contracts.validate_source(record)
                source_id = source["source_id"]
                if not source_id.startswith(source_namespace) or len(source_id) == len(source_namespace):
                    raise PackBuildError("Local Papers Source ID is not namespaced to this installation")
                if source_id in source_records:
                    raise PackBuildError(f"duplicate Source ID across accepted Commits: {source_id}")
                if not set(source["rights"]["allowed_routes"]).issubset({"local"}):
                    raise PackBuildError("Local Papers Source permits a non-local route")
                if source["access_scope"] not in {"full_text", "local_private"}:
                    raise PackBuildError("Local Papers Source must represent local full-text material")
                source_records[source_id] = source
            elif record_type == "Claim":
                claim_id = record["claim_id"]
                if not claim_id.startswith(claim_namespace) or len(claim_id) == len(claim_namespace):
                    raise PackBuildError("Local Papers Claim ID is not namespaced to this installation")
                if claim_id in claim_records:
                    raise PackBuildError(f"duplicate Claim ID across accepted Commits: {claim_id}")
                claim_records[claim_id] = record
            else:
                raise PackBuildError("unsupported accepted artifact in Local Papers Pack")

    if not source_records or not claim_records:
        raise PackBuildError("Local Papers Pack requires accepted Source and Claim records")
    if set(source_records) & base_source_ids or set(claim_records) & base_claim_ids:
        raise PackBuildError("Local Papers IDs collide with pinned Base record IDs")
    if any(claim["status"] != "approved" for claim in claim_records.values()):
        raise PackBuildError("Local Papers Pack may contain only approved Claims")
    if any(claim["expert_id"] not in base_expert_ids for claim in claim_records.values()):
        raise PackBuildError("Local Papers Claim references an expert missing from the pinned Base")
    for claim in claim_records.values():
        try:
            contracts.validate_claim(claim, sources=source_records)
        except contracts.ContractError as exc:
            raise PackBuildError(f"Local Papers Claim failed Source integrity validation: {exc}") from exc
    try:
        contracts.authorize_route([*source_records.values(), *claim_records.values()],
                                  "local", sources=source_records)
    except (contracts.ContractError, PermissionError) as exc:
        raise PackBuildError(f"Local Papers Pack is not authorized for local use: {exc}") from exc

    if not isinstance(adoption_records, Sequence) or isinstance(adoption_records, (str, bytes)):
        raise PackBuildError("adoption_records must be a sequence of separate review records")
    approved_adoptions: dict[str, dict] = {}
    for value in adoption_records:
        try:
            adoption = contracts.validate_local_adoption(value)
            claim = claim_records.get(adoption["claim_id"])
            if claim is None:
                raise contracts.ContractError("adoption references a Claim outside this overlay")
            adoption = contracts.validate_local_adoption_binding(
                adoption, claim=claim, sources=source_records,
                installation_id=installation_id,
                base_pack_root_sha256=base_manifest["root_sha256"],
            )
        except (contracts.ContractError, KeyError, TypeError) as exc:
            raise PackBuildError(f"Local Papers adoption record is invalid: {exc}") from exc
        if adoption["claim_id"] in approved_adoptions:
            raise PackBuildError("Local Papers Claim has multiple adoption records")
        approved_adoptions[adoption["claim_id"]] = adoption
    if set(approved_adoptions) != set(claim_records):
        raise PackBuildError("every Local Papers Claim requires one separate adoption record")

    source_data = b"".join(contracts.canonical_json(source_records[key]) + b"\n"
                            for key in sorted(source_records))
    claim_data = b"".join(contracts.canonical_json(claim_records[key]) + b"\n"
                           for key in sorted(claim_records))
    adoption_data = b"".join(contracts.canonical_json(approved_adoptions[key]) + b"\n"
                               for key in sorted(approved_adoptions))
    file_payloads: list[tuple[str, bytes, str, str | None]] = [
        ("knowledge/sources.jsonl", source_data, "knowledge_source", None),
        ("knowledge/claims.jsonl", claim_data, "knowledge_claim", None),
        ("knowledge/adoptions.jsonl", adoption_data, "knowledge_adoption", None),
    ]
    for expert_id in sorted(expert_payloads):
        file_payloads.append((f"experts/{expert_id}.json", expert_payloads[expert_id],
                              "expert_definition", expert_id))
    files = []
    for relative, data, role, expert_id in file_payloads:
        descriptor = {"path": relative, "size_bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest(), "role": role}
        if expert_id is not None:
            descriptor["expert_id"] = expert_id
        files.append(descriptor)

    manifest = {
        "schema_version": contracts.SCHEMA_VERSION,
        "pack_id": pack_id,
        "flavor": "local_papers",
        "stage": "internal_candidate",
        "distribution_route": "local",
        "compiler_version": compiler_version,
        "experts": base_manifest["experts"],
        "commits": commits,
        "claim_ids": sorted(claim_records),
        "source_ids": sorted(source_records),
        "files": files,
        "base_root_sha256": base_manifest["base_root_sha256"],
        "base_pack_root_sha256": base_manifest["root_sha256"],
        "installation_id": installation_id,
        "overlay_root_sha256": None,
    }
    manifest["overlay_root_sha256"] = contracts.compute_local_overlay_root_sha256(
        installation_id=installation_id,
        base_pack_root_sha256=manifest["base_pack_root_sha256"],
        commits=manifest["commits"], claim_ids=manifest["claim_ids"],
        source_ids=manifest["source_ids"], files=files,
    )
    manifest["root_sha256"] = contracts.sha256_json(manifest)
    try:
        validated_manifest = contracts.validate_pack_manifest(manifest)
    except contracts.ContractError as exc:
        raise PackBuildError(f"generated Local Papers manifest is invalid: {exc}") from exc

    pack_directory_key = hashlib.sha256(pack_id.encode("utf-8")).hexdigest()
    expected_directory = store.staging_root / "packs" / pack_directory_key
    if expected_directory.exists() or expected_directory.is_symlink() or \
            getattr(expected_directory, "is_junction", lambda: False)():
        raise PackBuildError("Pack staging directory already exists")
    directory = store.pack_staging_dir(pack_id)
    if any(directory.iterdir()):
        raise PackBuildError("Pack staging directory is not empty")
    written: list[Path] = []
    try:
        for relative, data, _role, _expert_id in file_payloads:
            path = store._artifact_path(directory, relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                written.append(path)
                handle.write(data)
        manifest_path = store._artifact_path(directory, "pack-manifest.json")
        with manifest_path.open("xb") as handle:
            written.append(manifest_path)
            handle.write(contracts.canonical_json(validated_manifest))
    except BaseException:
        for path in reversed(written):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        directories = {parent for path in written for parent in path.parents
                       if parent == directory or directory in parent.parents}
        for folder in sorted(directories, key=lambda item: len(item.parts), reverse=True):
            try:
                folder.rmdir()
            except OSError:
                pass
        try:
            directory.rmdir()
        except OSError:
            pass
        raise
    return validated_manifest
