"""Read-only, fail-closed runtime reader for internal candidate expert Packs.

This module reads Pack files only. It does not consult the builder SQLite ledger,
load a model, or expose evaluation cases/answer keys.
"""
from __future__ import annotations

import hashlib
import copy
import json
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from . import contracts

MAX_MEMBERS = 512
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_JSONL_BYTES = 16 * 1024 * 1024
MAX_JSONL_ROWS = 100_000
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_PACKET_CLAIMS = 256
MAX_PACKET_BYTES = 512 * 1024


class ExpertPackError(ValueError):
    """Pack failed validation; messages intentionally omit local paths/content."""


def _fail() -> None:
    raise ExpertPackError("invalid expert Pack")


def _json_bytes(data: bytes) -> Any:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail()
    if contracts.canonical_json(value) != data:
        _fail()
    contracts._reject_answer_material(value)
    return value


class _Bundle:
    def __init__(self, path: Path):
        self.path = path
        self.archive: zipfile.ZipFile | None = None
        self.members: dict[str, zipfile.ZipInfo] = {}
        self.root: Path | None = None

    def __enter__(self):
        if self.path.is_dir():
            if self.path.is_symlink() or getattr(self.path, "is_junction", lambda: False)():
                _fail()
            self.root = self.path.resolve(strict=True)
            return self
        try:
            archive = zipfile.ZipFile(self.path, "r")
            infos = archive.infolist()
            if len(infos) > MAX_MEMBERS:
                _fail()
            total = 0
            for info in infos:
                name = info.filename
                posix = PurePosixPath(name)
                mode = info.external_attr >> 16
                if (not name or "\\" in name or ":" in name or posix.is_absolute()
                        or any(part in {"", ".", ".."} for part in name.rstrip("/").split("/"))
                        or name in self.members or stat.S_ISLNK(mode)):
                    _fail()
                if info.file_size > MAX_MEMBER_BYTES:
                    _fail()
                total += info.file_size
                if total > MAX_TOTAL_BYTES:
                    _fail()
                self.members[name] = info
            self.archive = archive
            return self
        except (OSError, zipfile.BadZipFile, RuntimeError):
            _fail()

    def read(self, relative: str) -> bytes:
        try:
            relative = contracts._relative_path(relative, "pack file path")
            if self.archive is not None:
                info = self.members.get(relative)
                if info is None or info.is_dir():
                    _fail()
                data = self.archive.read(info)
            else:
                assert self.root is not None
                path = self.root
                for part in relative.split("/"):
                    path = path / part
                    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                        _fail()
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(self.root) or not resolved.is_file():
                    _fail()
                if resolved.stat().st_size > MAX_MEMBER_BYTES:
                    _fail()
                with resolved.open("rb") as stream:
                    data = stream.read(MAX_MEMBER_BYTES + 1)
            if len(data) > MAX_MEMBER_BYTES:
                _fail()
            return data
        except (OSError, KeyError, ValueError, RuntimeError, zipfile.BadZipFile):
            _fail()

    def file_names(self) -> set[str]:
        if self.archive is not None:
            return {name for name, info in self.members.items() if not info.is_dir()}
        assert self.root is not None
        names = set()
        total = 0
        entries = 0
        try:
            for item in self.root.rglob("*"):
                entries += 1
                if entries > MAX_MEMBERS:
                    _fail()
                if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
                    _fail()
                if item.is_file():
                    names.add(item.relative_to(self.root).as_posix())
                    size = item.stat().st_size
                    if size > MAX_MEMBER_BYTES:
                        _fail()
                    total += size
                    if total > MAX_TOTAL_BYTES:
                        _fail()
                elif not item.is_dir():
                    _fail()
            return names
        except OSError:
            _fail()

    def __exit__(self, exc_type, exc, tb):
        if self.archive is not None:
            self.archive.close()


def _read_jsonl(bundle: _Bundle, descriptor: dict) -> list[dict]:
    data = bundle.read(descriptor["path"])
    if len(data) > MAX_JSONL_BYTES or not data.endswith(b"\n"):
        _fail()
    lines = data.splitlines()
    if not lines or len(lines) > MAX_JSONL_ROWS:
        _fail()
    records = []
    for line in lines:
        if not line or len(line) > MAX_MEMBER_BYTES:
            _fail()
        records.append(_json_bytes(line))
    return records


@dataclass(frozen=True)
class ExpertKnowledgeContext:
    manifest: dict
    sources: dict[str, dict]
    claims: dict[str, dict]

    @property
    def pack_root_sha256(self) -> str:
        return self.manifest["root_sha256"]

    @classmethod
    def load(cls, path: str | Path, *, expected_pack_root: str, route: str,
             allow_internal_candidate: bool = False) -> "ExpertKnowledgeContext":
        context = cls._load_pack(
            path, expected_pack_root=expected_pack_root, route=route,
            allow_internal_candidate=allow_internal_candidate,
        )
        if context.manifest["flavor"] != "base":
            _fail()
        return context

    @classmethod
    def _load_pack(cls, path: str | Path, *, expected_pack_root: str, route: str,
                   allow_internal_candidate: bool = False,
                   allow_local_overlay: bool = False,
                   expected_installation_id: str | None = None,
                   expected_base_pack_root_sha256: str | None = None) -> "ExpertKnowledgeContext":
        try:
            contracts._hash(expected_pack_root, "expected_pack_root")
            if route not in contracts.ROUTES:
                _fail()
            with _Bundle(Path(path)) as bundle:
                manifest_data = bundle.read("pack-manifest.json")
                if len(manifest_data) > MAX_MANIFEST_BYTES:
                    _fail()
                manifest = contracts.validate_pack_manifest(_json_bytes(manifest_data))
                if manifest["root_sha256"] != expected_pack_root:
                    _fail()
                if manifest["stage"] != "internal_candidate" or not (
                    allow_internal_candidate and route == "local"
                ):
                    _fail()
                is_local_overlay = manifest["flavor"] == "local_papers"
                if is_local_overlay:
                    if (not allow_local_overlay or route != "local" or expected_installation_id is None or
                            expected_base_pack_root_sha256 is None or
                            manifest["installation_id"] != expected_installation_id or
                            manifest["base_pack_root_sha256"] != expected_base_pack_root_sha256):
                        _fail()
                elif manifest["flavor"] != "base":
                    _fail()

                expected_names = {"pack-manifest.json", *(item["path"] for item in manifest["files"])}
                if bundle.file_names() != expected_names:
                    _fail()

                by_role: dict[str, list[dict]] = {}
                for descriptor in manifest["files"]:
                    data = bundle.read(descriptor["path"])
                    if len(data) != descriptor["size_bytes"] or hashlib.sha256(data).hexdigest() != descriptor["sha256"]:
                        _fail()
                    by_role.setdefault(descriptor["role"], []).append(descriptor)
                expected_roles = {"knowledge_source", "knowledge_claim", "expert_definition"}
                if is_local_overlay:
                    expected_roles.add("knowledge_adoption")
                if set(by_role) != expected_roles:
                    _fail()
                if len(by_role["knowledge_source"]) != 1 or len(by_role["knowledge_claim"]) != 1:
                    _fail()

                source_records = _read_jsonl(bundle, by_role["knowledge_source"][0])
                claim_records = _read_jsonl(bundle, by_role["knowledge_claim"][0])
                sources: dict[str, dict] = {}
                for record in source_records:
                    source = contracts.validate_source(record)
                    if source["source_id"] in sources:
                        _fail()
                    if is_local_overlay and not source["source_id"].startswith(
                            f"local:{expected_installation_id}:source:"):
                        _fail()
                    if not is_local_overlay and (
                            source["access_scope"] == "local_private" or
                            source["rights"]["classification"] == "private" or
                            source["locator"]["kind"] == "local_uri" or
                            set(source["rights"]["allowed_routes"]) == {"local"}):
                        _fail()
                    sources[source["source_id"]] = source
                claims: dict[str, dict] = {}
                for record in claim_records:
                    claim = contracts.validate_claim(record, sources)
                    if claim["status"] != "approved" or claim["claim_id"] in claims:
                        _fail()
                    if is_local_overlay and not claim["claim_id"].startswith(
                            f"local:{expected_installation_id}:claim:"):
                        _fail()
                    claims[claim["claim_id"]] = claim
                if set(sources) != set(manifest["source_ids"]) or set(claims) != set(manifest["claim_ids"]):
                    _fail()

                if is_local_overlay:
                    adoption_records = _read_jsonl(bundle, by_role["knowledge_adoption"][0])
                    adoptions = {}
                    for record in adoption_records:
                        adoption = contracts.validate_local_adoption(record)
                        claim = claims.get(adoption["claim_id"])
                        if claim is None or adoption["claim_id"] in adoptions:
                            _fail()
                        contracts.validate_local_adoption_binding(
                            adoption, claim=claim, sources=sources,
                            installation_id=expected_installation_id,
                            base_pack_root_sha256=expected_base_pack_root_sha256,
                        )
                        adoptions[adoption["claim_id"]] = adoption
                    if set(adoptions) != set(claims):
                        _fail()

                expert_map = {entry["expert_id"]: entry for entry in manifest["experts"]}
                if len(by_role["expert_definition"]) != len(expert_map):
                    _fail()
                definition_ids = set()
                for descriptor in by_role["expert_definition"]:
                    data = bundle.read(descriptor["path"])
                    definition = _json_bytes(data)
                    expert_id = descriptor.get("expert_id")
                    if expert_id not in expert_map or expert_id in definition_ids:
                        _fail()
                    if definition.get("expert_id") != expert_id:
                        _fail()
                    if hashlib.sha256(data).hexdigest() != expert_map[expert_id]["definition_sha256"]:
                        _fail()
                    definition_ids.add(expert_id)
                if definition_ids != set(expert_map) or any(claim["expert_id"] not in expert_map for claim in claims.values()):
                    _fail()
                contracts.authorize_route([*sources.values(), *claims.values()], route, sources=sources)
                return cls(manifest=manifest, sources=sources, claims=claims)
        except ExpertPackError:
            raise
        except (OSError, ValueError, TypeError, KeyError, AssertionError):
            _fail()

    def build_expert_packet(self, expert_id: str, query: str, route: str) -> dict:
        """Include every approved Claim for this expert in stable ID order.

        Query-based ranking is deliberately not inferred here: callers get the
        expert's complete reviewed knowledge or a fail-closed size-limit error.
        """
        try:
            contracts._id(expert_id, "expert_id")
            contracts._text(query, "query", max_length=10000)
            if route != "local" or route not in contracts.ROUTES:
                _fail()
            selected = [claim for claim in self.claims.values() if claim["expert_id"] == expert_id
                        and claim["status"] == "approved"]
            if not selected or len(selected) > MAX_PACKET_CLAIMS:
                _fail()
            used_source_ids = sorted({e["source_id"] for claim in selected for e in claim["evidence"]})
            selected_sources = {source_id: self.sources[source_id] for source_id in used_source_ids}
            contracts.authorize_route([*selected_sources.values(), *selected], route, sources=selected_sources)
            claim_rows = []
            evidence = []
            for claim in sorted(selected, key=lambda item: item["claim_id"]):
                claim_hash = contracts.sha256_json(claim)
                claim_rows.append({"claim": claim, "claim_sha256": claim_hash})
                for span in claim["evidence"]:
                    source = selected_sources[span["source_id"]]
                    evidence.append({"claim_id": claim["claim_id"], "claim_sha256": claim_hash,
                                     "source_id": source["source_id"],
                                     "source_record_sha256": contracts.sha256_json(source),
                                     "source_sha256": source["sha256"], "anchor_id": span["anchor_id"],
                                     "extracted_text_sha256": span["extracted_text_sha256"]})
            packet = {"schema_version": 1, "pack_root_sha256": self.pack_root_sha256,
                      "expert_id": expert_id, "route": route, "query": query,
                      "claims": claim_rows, "sources": selected_sources, "evidence": evidence}
            packet["packet_sha256"] = contracts.sha256_json(packet)
            validate_packet(packet)
            return packet
        except ExpertPackError:
            raise
        except (KeyError, TypeError, ValueError, PermissionError):
            _fail()

    def build_selected_expert_packet(self, expert_id: str, query: str, route: str, *, policy: dict) -> dict:
        """Opt-in v2: a reviewed, root-pinned policy determines mandatory knowledge.

        No relevance ranking or generated policy can silently replace v1. Whole
        Claims retain applicability, exceptions, contradictions and citations.
        """
        full = self.build_expert_packet(expert_id, query, route)
        selected = _selection_ids(policy, full)
        packet = copy.deepcopy(full)
        packet["schema_version"] = 2
        packet["claims"] = [row for row in full["claims"] if row["claim"]["claim_id"] in selected]
        packet["evidence"] = [row for row in full["evidence"] if row["claim_id"] in selected]
        used = {row["source_id"] for row in packet["evidence"]}
        packet["sources"] = {key: row for key, row in full["sources"].items() if key in used}
        packet["selection"] = {"policy": copy.deepcopy(policy), "policy_sha256": contracts.sha256_json(policy),
            "full_packet_sha256": full["packet_sha256"],
            "omitted_claim_ids": sorted(set(policy["claim_hashes"]) - selected)}
        packet["packet_sha256"] = contracts.sha256_json({key: value for key, value in packet.items() if key != "packet_sha256"})
        validate_packet(packet)
        return packet


def load_expert_pack(path: str | Path, expected_pack_root: str, route: str,
                     allow_internal_candidate: bool = False) -> ExpertKnowledgeContext:
    return ExpertKnowledgeContext.load(path, expected_pack_root=expected_pack_root, route=route,
                                       allow_internal_candidate=allow_internal_candidate)


def load_local_papers_pack(
    base_pack_path: str | Path,
    overlay_pack_path: str | Path,
    *,
    expected_base_pack_root_sha256: str,
    expected_overlay_pack_root_sha256: str,
    expected_installation_id: str,
) -> ExpertKnowledgeContext:
    """Compose one pinned Base Pack with one installation-local overlay."""
    try:
        base = load_expert_pack(base_pack_path, expected_base_pack_root_sha256, "local",
                                allow_internal_candidate=True)
        if base.manifest["flavor"] != "base":
            _fail()
        overlay = ExpertKnowledgeContext._load_pack(
            overlay_pack_path, expected_pack_root=expected_overlay_pack_root_sha256, route="local",
            allow_internal_candidate=True,
            allow_local_overlay=True,
            expected_installation_id=expected_installation_id,
            expected_base_pack_root_sha256=expected_base_pack_root_sha256,
        )
        if (overlay.manifest["flavor"] != "local_papers" or
                overlay.manifest["base_root_sha256"] != base.manifest["base_root_sha256"] or
                contracts.canonical_json(overlay.manifest["experts"]) !=
                contracts.canonical_json(base.manifest["experts"])):
            _fail()
        if set(base.sources) & set(overlay.sources) or set(base.claims) & set(overlay.claims):
            _fail()
        sources = {**base.sources, **overlay.sources}
        claims = {**base.claims, **overlay.claims}
        combined_root = contracts.sha256_json({
            "base_pack_root_sha256": base.manifest["root_sha256"],
            "overlay_pack_root_sha256": overlay.manifest["root_sha256"],
        })
        manifest = {
            "flavor": "local_papers_combined",
            "base_pack_root_sha256": base.manifest["root_sha256"],
            "overlay_pack_root_sha256": overlay.manifest["root_sha256"],
            "root_sha256": combined_root,
        }
        return ExpertKnowledgeContext(manifest=manifest, sources=sources, claims=claims)
    except ExpertPackError:
        raise
    except (KeyError, TypeError, ValueError, PermissionError, contracts.ContractError):
        _fail()


def _selection_ids(policy: dict, packet: dict) -> set[str]:
    try:
        contracts._object(policy, {"schema_version", "pack_root_sha256", "expert_id", "stage", "claim_hashes",
                          "required_claim_ids", "task_claim_ids", "dependencies", "reviewer"}, name="selection policy")
        if policy["schema_version"] != 1 or policy["pack_root_sha256"] != packet["pack_root_sha256"] or policy["expert_id"] != packet["expert_id"]:
            _fail()
        contracts._text(policy["stage"], "stage", max_length=100)
        hashes = policy["claim_hashes"]
        if not isinstance(hashes, dict) or not hashes or len(hashes) > MAX_PACKET_CLAIMS:
            _fail()
        for key, value in hashes.items():
            contracts._id(key, "claim_id")
            contracts._hash(value, "claim_sha256")
        available = {row["claim"]["claim_id"]: row["claim_sha256"] for row in packet["claims"]}
        if packet["schema_version"] == 1 and available != hashes:
            _fail()
        if any(hashes.get(key) != value for key, value in available.items()):
            _fail()
        dependencies = policy["dependencies"]
        if not isinstance(dependencies, dict) or set(dependencies) != set(hashes):
            _fail()
        for ids in [policy["required_claim_ids"], policy["task_claim_ids"], *dependencies.values()]:
            if not isinstance(ids, list) or len(ids) != len(set(ids)) or any(ref not in hashes for ref in ids):
                _fail()
        reviewer = policy["reviewer"]
        contracts._object(reviewer, {"identity", "reviewed_at", "target_sha256"}, name="selection reviewer")
        contracts._text(reviewer["identity"], "identity")
        contracts._text(reviewer["reviewed_at"], "reviewed_at")
        unsigned = {key: value for key, value in policy.items() if key != "reviewer"}
        if reviewer["target_sha256"] != contracts.sha256_json(unsigned):
            _fail()
        selected = set(policy["required_claim_ids"]) | set(policy["task_claim_ids"])
        while True:
            expanded = selected | {ref for key in selected for ref in dependencies[key]}
            if selected == expanded:
                break
            selected = expanded
        if not selected:
            _fail()
        return selected
    except ExpertPackError:
        raise
    except (KeyError, TypeError, ValueError):
        _fail()


def validate_packet(packet: dict) -> dict:
    try:
        if packet.get("schema_version") == 2:
            selection = packet.get("selection", {})
            contracts._object(selection, {"policy", "policy_sha256", "full_packet_sha256", "omitted_claim_ids"}, name="selection")
            if selection["policy_sha256"] != contracts.sha256_json(selection["policy"]):
                _fail()
            contracts._hash(selection["full_packet_sha256"], "full_packet_sha256")
            selected = _selection_ids(selection["policy"], packet)
            actual = {row["claim"]["claim_id"] for row in packet["claims"]}
            if actual != selected or selection["omitted_claim_ids"] != sorted(set(selection["policy"]["claim_hashes"]) - selected):
                _fail()
            unsigned = {key: value for key, value in packet.items() if key != "packet_sha256"}
            if contracts.sha256_json(unsigned) != packet["packet_sha256"] or len(contracts.canonical_json(unsigned)) > MAX_PACKET_BYTES:
                _fail()
            inner = {key: copy.deepcopy(value) for key, value in packet.items() if key != "selection"}
            inner["schema_version"] = 1
            inner["packet_sha256"] = contracts.sha256_json({key: value for key, value in inner.items() if key != "packet_sha256"})
            validate_packet(inner)
            return packet
        contracts._object(packet, {"schema_version", "pack_root_sha256", "expert_id", "route", "query",
                                   "claims", "sources", "evidence", "packet_sha256"}, name="packet")
        if packet["schema_version"] != 1:
            _fail()
        contracts._hash(packet["pack_root_sha256"], "pack_root_sha256")
        contracts._id(packet["expert_id"], "expert_id")
        contracts._text(packet["query"], "query", max_length=10000)
        if packet["route"] != "local" or not isinstance(packet["sources"], dict):
            _fail()
        sources = {key: contracts.validate_source(value) for key, value in packet["sources"].items()}
        if any(key != value["source_id"] for key, value in sources.items()):
            _fail()
        if not isinstance(packet["claims"], list) or not 0 < len(packet["claims"]) <= MAX_PACKET_CLAIMS:
            _fail()
        claims = []
        allowed = set()
        for row in packet["claims"]:
            contracts._object(row, {"claim", "claim_sha256"}, name="packet claim")
            claim = contracts.validate_claim(row["claim"], sources)
            if claim["status"] != "approved" or claim["expert_id"] != packet["expert_id"]:
                _fail()
            if contracts.sha256_json(claim) != row["claim_sha256"]:
                _fail()
            claims.append(claim)
            for span in claim["evidence"]:
                source = sources[span["source_id"]]
                allowed.add((claim["claim_id"], row["claim_sha256"], source["source_id"],
                             contracts.sha256_json(source), source["sha256"], span["anchor_id"],
                             span["extracted_text_sha256"]))
        claim_ids = [claim["claim_id"] for claim in claims]
        if len(set(claim_ids)) != len(claim_ids):
            _fail()
        contracts.authorize_route([*sources.values(), *claims], "local", sources=sources)
        if not isinstance(packet["evidence"], list):
            _fail()
        actual = set()
        for row in packet["evidence"]:
            contracts._object(row, {"claim_id", "claim_sha256", "source_id", "source_record_sha256",
                                    "source_sha256", "anchor_id", "extracted_text_sha256"}, name="packet evidence")
            key = tuple(row[field] for field in ("claim_id", "claim_sha256", "source_id", "source_record_sha256",
                                                  "source_sha256", "anchor_id", "extracted_text_sha256"))
            if key not in allowed or key in actual:
                _fail()
            actual.add(key)
        if actual != allowed:
            _fail()
        unsigned = {key: value for key, value in packet.items() if key != "packet_sha256"}
        if len(contracts.canonical_json(unsigned)) > MAX_PACKET_BYTES:
            _fail()
        if contracts.sha256_json(unsigned) != packet["packet_sha256"]:
            _fail()
        return packet
    except ExpertPackError:
        raise
    except (contracts.ContractError, KeyError, TypeError, ValueError, PermissionError):
        _fail()


_FILE_URI_RE = re.compile(r"(?i)file:[^\s\"'<>]+")
_WINDOWS_PATH_RE = re.compile(r"(?i)(?<![\w])[a-z]:(?:[\\/]|(?=[^\s\"'<>|]))")
_UNC_PATH_RE = re.compile(r"\\\\[^\\/\s]+[\\/][^\\/\s]+")
_UNC_SLASH_PATH_RE = re.compile(r"(?<!:)//[^/\s]+/[^/\s]+")
_ROOTED_BACKSLASH_PATH_RE = re.compile(r"(?<![\w])\\[^\\/\s]+(?:[\\/][^\\/\s]+)*")
_TILDE_PATH_RE = re.compile(r"(?<![\w])~(?:[\\/]|[^\\/\s]+[\\/])[^\s\"'<>|]+")
_POSIX_PATH_RE = re.compile(
    r"(?<![\w/])/(?!/)[^/\s\"'<>|]+(?:/[^/\s\"'<>|]+)*"
)


def _redact_local_paths(value: Any) -> Any:
    """Remove any whole text field containing an absolute local path."""
    if isinstance(value, dict):
        redacted = {key: _redact_local_paths(item) for key, item in value.items()}
        if value.get("kind") == "local_uri" and "value" in redacted:
            redacted["value"] = "[local paper path withheld]"
        return redacted
    if isinstance(value, list):
        return [_redact_local_paths(item) for item in value]
    if isinstance(value, str) and (
        _FILE_URI_RE.search(value) or _WINDOWS_PATH_RE.search(value)
        or _UNC_PATH_RE.search(value) or _UNC_SLASH_PATH_RE.search(value)
        or _ROOTED_BACKSLASH_PATH_RE.search(value) or _TILDE_PATH_RE.search(value)
        or _POSIX_PATH_RE.search(value)
    ):
        return "[text withheld: local path present]"
    return value


def render_agent_request(packet: dict) -> str:
    validate_packet(packet)
    payload = {
        "expert_id": packet["expert_id"],
        "query": packet["query"],
        "approved_claims": packet["claims"],
        "sources": packet["sources"],
        "allowed_evidence": packet["evidence"],
    }
    if packet["schema_version"] == 2:
        payload["knowledge_scope"] = {"stage": packet["selection"]["policy"]["stage"],
            "policy_sha256": packet["selection"]["policy_sha256"],
            "omitted_claim_count": len(packet["selection"]["omitted_claim_ids"])}
    payload = _redact_local_paths(payload)
    instructions = (
        "Use only the approved Claims and their cited evidence below. Answer in Japanese. "
        "Do not add facts absent from the Claims. If evidence is insufficient, state what is missing. "
        "Preserve source titles, authors, dates, identifiers, license details, and evidence fields as written; "
        "do not invent or alter citations."
    )
    rendered = instructions + "\n\n[PACKET_JSON]\n" + contracts.canonical_json(payload).decode("utf-8")
    if len(rendered.encode("utf-8")) > MAX_PACKET_BYTES:
        _fail()
    return rendered


def validate_output_evidence(packet: dict, output: dict) -> dict:
    validate_packet(packet)
    try:
        contracts._object(output, {"answer", "evidence"}, name="expert output")
        contracts._text(output["answer"], "answer", max_length=20000)
        if not isinstance(output["evidence"], list):
            _fail()
        allowed = {tuple(row[field] for field in ("claim_id", "claim_sha256", "source_id", "source_record_sha256",
                                                   "source_sha256", "anchor_id", "extracted_text_sha256"))
                   for row in packet["evidence"]}
        seen = set()
        for row in output["evidence"]:
            contracts._object(row, {"claim_id", "claim_sha256", "source_id", "source_record_sha256",
                                    "source_sha256", "anchor_id", "extracted_text_sha256"}, name="output evidence")
            key = tuple(row[field] for field in ("claim_id", "claim_sha256", "source_id", "source_record_sha256",
                                                  "source_sha256", "anchor_id", "extracted_text_sha256"))
            if key not in allowed or key in seen:
                _fail()
            seen.add(key)
        return output
    except ExpertPackError:
        raise
    except (contracts.ContractError, KeyError, TypeError, ValueError):
        _fail()
