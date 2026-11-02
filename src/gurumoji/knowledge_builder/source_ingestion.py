"""Private local document ingestion with rights-gated, position-bound excerpts.

Input files and extracted text are kept below the explicitly configured
``knowledge_builder/private/source_extractions`` data root. This is a local-only
P5 ingestion slice: it does not create Claims, call an LLM, upload files, or add
private material to a Base Pack.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from . import contracts

SOFTWARE_VAULT_ROOT = Path(__file__).resolve().parents[3] / "docs" / "program-vault"
MAX_SOURCE_BYTES = 100 * 1024 * 1024
MAX_PDF_PAGES = 20_000
MAX_PARAGRAPHS = 100_000
MAX_EXTRACTED_BYTES = 100 * 1024 * 1024
MAX_EXCERPT_FILE_BYTES = 2 * MAX_EXTRACTED_BYTES + MAX_PARAGRAPHS * 256
MAX_PAGE_PARAGRAPHS = 5_000
MAX_PAGE_EXTRACTED_BYTES = 2 * 1024 * 1024
MAX_PRIVATE_EXTRACTION_RECORDS = 10_000
RIGHTS_REVIEW_FIELDS = {
    "license_id", "license_url", "llm_processing_permission", "llm_allowed_routes",
    "rights_review_status", "rights_reviewed_by", "rights_reviewed_at", "rights_review_basis",
}


class SourceIngestionError(ValueError):
    """Fail-closed input, permission, or extraction error without path details."""


def _fail(message: str) -> None:
    raise SourceIngestionError(message)


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _validate_rights(source_value: Any, review_value: Any, route: str) -> dict:
    """Validate rights data loaded from trusted Software Vault metadata."""
    source = contracts.validate_source(source_value)
    review = contracts._object(review_value, RIGHTS_REVIEW_FIELDS, name="rights review")
    if review["license_id"] != source["license"]["license_id"]:
        _fail("reviewed license ID does not match Source")
    license_url = source.get("license_url")
    if (not isinstance(license_url, dict) or license_url.get("kind") != "https" or
            review["license_url"] != license_url.get("value")):
        _fail("reviewed license URL does not match Source")
    if review["llm_processing_permission"] != "explicitly_permitted":
        _fail("explicit LLM processing permission is required")
    if review["rights_review_status"] != "approved":
        _fail("rights review is not approved")
    for name in ("rights_reviewed_by", "rights_review_basis"):
        contracts._text(review[name], name, max_length=2000)
    contracts._timestamp(review["rights_reviewed_at"], "rights_reviewed_at")
    try:
        timestamp = datetime.fromisoformat(review["rights_reviewed_at"].replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        _fail("rights review time must be a valid timestamp")
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        _fail("rights review time must include a UTC offset")
    routes = review["llm_allowed_routes"]
    if (not isinstance(routes, list) or not routes or
            any(not isinstance(item, str) or item not in contracts.ROUTES for item in routes) or
            len(routes) != len(set(routes))):
        _fail("rights review route allowlist is invalid")
    if source["rights"]["classification"] == "private" and set(routes) != {"local"}:
        _fail("private Source may use only local processing")
    if source["access_scope"] == "local_private" and set(routes) != {"local"}:
        _fail("local-private Source may use only local processing")
    if route not in contracts.ROUTES or route not in routes:
        _fail("requested route is not explicitly authorized")
    if route not in source["rights"]["allowed_routes"]:
        _fail("requested route is not allowed by Source reuse rights")
    return source


def _frontmatter(note_path: Path) -> tuple[dict, str]:
    try:
        raw = note_path.read_bytes()
        text = raw.decode("utf-8-sig")
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            _fail("trusted literature note has no frontmatter")
        end = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
        if end is None:
            _fail("trusted literature note frontmatter is unterminated")
        properties = yaml.safe_load("\n".join(lines[1:end]))
        if not isinstance(properties, dict):
            _fail("trusted literature note frontmatter is invalid")
        return properties, hashlib.sha256(raw).hexdigest()
    except SourceIngestionError:
        raise
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        _fail("trusted literature note could not be read")


def _timestamp_string(value: Any) -> str:
    """Normalize YAML's implicit datetime scalar to a UTC-aware ISO string."""
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return str(value)


def _trusted_source_authority(source_id: str) -> tuple[dict, dict, str]:
    """Build a local-only Source from an exact reviewed Software Vault note."""
    contracts._id(source_id, "source_id")
    literature_root = SOFTWARE_VAULT_ROOT / "50-Analysis-Methods" / "20-Literature"
    note_path = literature_root / f"{source_id}.md"
    if note_path.is_symlink() or not note_path.is_file() or not _within(note_path, literature_root):
        _fail("source is not registered in the trusted literature catalog")
    props, authority_note_sha256 = _frontmatter(note_path)
    if props.get("note_type") != "literature" or props.get("literature_id") != source_id:
        _fail("trusted literature catalog identity mismatch")
    if props.get("status") != "current":
        _fail("source is not current in the trusted literature catalog")
    if props.get("correction_status") != "none_found":
        _fail("source correction or retraction status is not cleared")
    if props.get("access_scope") != "full_text":
        _fail("reviewed source scope does not authorize full-text extraction")
    if props.get("llm_processing_permission") != "explicitly_permitted" or props.get("rights_review_status") != "approved":
        _fail("source lacks an approved explicit processing review")
    allowed = props.get("llm_allowed_routes")
    if (not isinstance(allowed, list) or not allowed or
            any(not isinstance(route, str) or route not in contracts.ROUTES for route in allowed) or
            len(allowed) != len(set(allowed)) or "local" not in allowed):
        _fail("local route is not explicitly authorized by reviewed Source metadata")
    license_id = props.get("license_id")
    license_url = props.get("license_url")
    if not isinstance(license_id, str) or not license_id.strip():
        _fail("reviewed license ID is missing")
    if not isinstance(license_url, str) or not license_url.startswith("https://"):
        _fail("reviewed HTTPS license URL is missing")
    reviewer = props.get("rights_reviewed_by")
    basis = props.get("rights_review_basis")
    contracts._text(reviewer, "rights_reviewed_by", max_length=2000)
    contracts._text(basis, "rights_review_basis", max_length=4000)
    reviewed_at = _timestamp_string(props.get("rights_reviewed_at"))
    contracts._timestamp(reviewed_at, "rights_reviewed_at")
    try:
        parsed_time = datetime.fromisoformat(str(reviewed_at).replace("Z", "+00:00"))
    except ValueError:
        _fail("rights review timestamp is invalid")
    if parsed_time.tzinfo is None or parsed_time.utcoffset() is None:
        _fail("rights review timestamp must include a timezone")
    title = props.get("title")
    contracts._text(title, "title", max_length=1000)
    doi = props.get("doi")
    url = props.get("url")
    if isinstance(doi, str) and re.fullmatch(r"10\.\d{4,9}/[^\s\\\x00-\x1f\x7f?#]+", doi):
        locator = {"kind": "doi", "value": doi}
    elif isinstance(url, str) and re.fullmatch(r"https://[^\s\\\x00-\x1f\x7f?#]+", url):
        locator = {"kind": "url", "value": url}
    else:
        _fail("trusted literature note has no safe DOI or HTTPS locator")
    authors = props.get("authors", [])
    if not isinstance(authors, list) or any(not isinstance(name, str) or not name.strip() for name in authors):
        _fail("trusted authors metadata is invalid")
    year = props.get("year")
    if isinstance(year, str) and year.isdigit():
        year = int(year)
    if year is not None and (type(year) is not int or not 1000 <= year <= 9999):
        _fail("trusted publication year is invalid")
    document_sha256 = props.get("document_sha256")
    document_version = props.get("document_version")
    contracts._hash(document_sha256, "document_sha256")
    contracts._text(document_version, "document_version", max_length=500)
    source = {
        "schema_version": 1, "source_id": source_id, "version": document_version,
        "sha256": document_sha256, "title": title, "authors": authors,
        "publication_year": year, "source_type": "paper", "locator": locator,
        "access_scope": "full_text",
        "license": {"license_id": license_id, "terms": f"{license_id} ({license_url})"},
        "license_url": {"kind": "https", "value": license_url}, "anchors": [],
        # Extraction remains private/local even when a source note separately permits
        # user-initiated Colab or export. These are independent route decisions.
        "rights": {"classification": "licensed", "allowed_routes": ["local"]},
    }
    adaptation_notice = props.get("adaptation_notice")
    if isinstance(adaptation_notice, str) and adaptation_notice.strip():
        source["adaptation_notice"] = adaptation_notice
    review = {name: (props.get(name) if name != "license_url" else license_url) for name in RIGHTS_REVIEW_FIELDS}
    review["rights_reviewed_at"] = reviewed_at
    review["llm_allowed_routes"] = allowed
    review["license_id"] = license_id
    review["license_url"] = license_url
    return source, review, authority_note_sha256


def _normalise_paragraph(value: str) -> str:
    value = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    return " ".join(part.strip() for part in value.splitlines() if part.strip()).strip()


def _paragraph_rows(text: str, *, kind: str, page_number: int | None = None) -> list[tuple[str, str, str, str]]:
    rows = []
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    for index, raw in enumerate(re.split(r"\n[\t ]*\n+", normalized_text), start=1):
        paragraph = _normalise_paragraph(raw)
        if not paragraph:
            continue
        if kind == "page":
            start = end = str(page_number)
        else:
            start = end = str(index)
        rows.append((paragraph, kind, start, end))
    return rows


def _extract_txt(data: bytes) -> tuple[list[tuple[str, str, str, str]], dict]:
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        _fail("text source is not valid UTF-8")
    rows = _paragraph_rows(text, kind="paragraph")
    return rows, {"name": "utf8-paragraph-normalizer", "version": "1", "page_count": None,
                  "completeness": "extracted", "review_reasons": []}


def _extract_pdf(data: bytes) -> tuple[list[tuple[str, str, str, str]], dict]:
    try:
        from pypdf import PdfReader
    except ImportError:
        _fail("PDF extraction requires the declared pypdf dependency")
    try:
        from io import BytesIO
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            _fail("encrypted PDFs are unsupported")
        page_count = len(reader.pages)
        if page_count < 1 or page_count > MAX_PDF_PAGES:
            _fail("PDF page count is invalid")
        rows = []
        accumulated_bytes = 0
        page_extractions = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
                page_rows = _paragraph_rows(page_text, kind="page", page_number=page_number)
                page_bytes = sum(len(row[0].encode("utf-8")) for row in page_rows)
                if len(page_rows) > MAX_PAGE_PARAGRAPHS or page_bytes > MAX_PAGE_EXTRACTED_BYTES:
                    page_extractions.append({"page_number": page_number, "status": "error",
                                             "paragraph_count": 0, "extracted_bytes": 0,
                                             "error_code": "page_limit_exceeded"})
                    continue
                if (len(rows) + len(page_rows) > MAX_PARAGRAPHS or
                        accumulated_bytes + page_bytes > MAX_EXTRACTED_BYTES):
                    page_extractions.append({"page_number": page_number, "status": "error",
                                             "paragraph_count": 0, "extracted_bytes": 0,
                                             "error_code": "document_limit_exceeded"})
                    continue
                rows.extend(page_rows)
                accumulated_bytes += page_bytes
                page_extractions.append({"page_number": page_number,
                                         "status": "extracted" if page_rows else "empty",
                                         "paragraph_count": len(page_rows), "extracted_bytes": page_bytes})
            except Exception:
                page_extractions.append({"page_number": page_number, "status": "error",
                                         "paragraph_count": 0, "extracted_bytes": 0,
                                         "error_code": "page_extraction_failed"})
        version = importlib.metadata.version("pypdf")
        return rows, {"name": "pypdf", "version": version, "page_count": page_count,
                      "page_extractions": page_extractions,
                      "completeness": "requires_human_review",
                      "review_reasons": ["PDF visual content, tables, equations, and OCR were not reviewed"]}
    except SourceIngestionError:
        raise
    except Exception:
        _fail("PDF is malformed or could not be extracted")


def _build_extraction(source: dict, source_bytes: bytes, suffix: str) -> tuple[dict, list[dict], dict]:
    if suffix == ".txt":
        rows, extractor = _extract_txt(source_bytes)
    elif suffix == ".pdf":
        rows, extractor = _extract_pdf(source_bytes)
    else:
        _fail("only local PDF and UTF-8 text files are supported")
    if not rows and suffix == ".txt":
        _fail("document contains no extractable text")
    if len(rows) > MAX_PARAGRAPHS:
        _fail("document paragraph count exceeds limit")
    extracted_total = sum(len(row[0].encode("utf-8")) for row in rows)
    if extracted_total > MAX_EXTRACTED_BYTES:
        _fail("extracted text exceeds size limit")

    anchors: list[dict] = []
    excerpts_by_hash: dict[str, dict] = {}
    for position, (text, kind, start, end) in enumerate(rows, start=1):
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        anchor_id = f"{('p' if kind == 'page' else 'para')}-{position:06d}"
        anchors.append({"anchor_id": anchor_id, "kind": kind, "start": start, "end": end,
                        "extracted_text_sha256": text_hash})
        excerpt = excerpts_by_hash.get(text_hash)
        if excerpt is None:
            excerpt = {"extracted_text_sha256": text_hash, "text": text, "locations": []}
            excerpts_by_hash[text_hash] = excerpt
        excerpt["locations"].append(anchor_id)
    result_source = dict(source)
    result_source["sha256"] = hashlib.sha256(source_bytes).hexdigest()
    result_source["anchors"] = anchors
    result_source = contracts.validate_source(result_source)
    excerpts = [excerpts_by_hash[key] for key in sorted(excerpts_by_hash)]
    return result_source, excerpts, extractor


def _canonical_manifest(source: dict, original_sha256: str, extractor: dict,
                        excerpts: list[dict], rights_review: dict, authority_note_sha256: str) -> dict:
    manifest = {
        "schema_version": 1,
        "kind": "private_source_extraction",
        "storage_class": "private_local_only",
        "original_sha256": original_sha256,
        "authority_note_sha256": authority_note_sha256,
        "extractor": extractor,
        "completeness": extractor["completeness"],
        "source": source,
        "excerpt_count": len(excerpts),
        "anchor_count": len(source["anchors"]),
        "duplicate_paragraph_count": len(source["anchors"]) - len(excerpts),
        "rights_review": rights_review,
    }
    manifest["manifest_sha256"] = contracts.sha256_json(manifest)
    return manifest


def _safe_write(output_dir: Path, manifest: dict, excerpts: list[dict]) -> None:
    try:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        if output_dir.exists():
            manifest_path = output_dir / "manifest.json"
            excerpts_path = output_dir / "excerpts.jsonl"
            if (manifest_path.is_file() and excerpts_path.is_file() and
                    manifest_path.read_bytes() == contracts.canonical_json(manifest) and
                    excerpts_path.read_bytes() == _encode_excerpts(excerpts)):
                return
            _fail("immutable private extraction already exists with different content")
        temp_dir = Path(tempfile.mkdtemp(prefix=".source-extract-", dir=output_dir.parent))
        try:
            manifest_data = contracts.canonical_json(manifest)
            excerpt_data = _encode_excerpts(excerpts)
            for name, data in (("manifest.json", manifest_data), ("excerpts.jsonl", excerpt_data)):
                path = temp_dir / name
                with path.open("xb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            os.replace(temp_dir, output_dir)
            temp_dir = None
        finally:
            if temp_dir is not None:
                shutil.rmtree(temp_dir, ignore_errors=True)
    except SourceIngestionError:
        raise
    except OSError:
        _fail("private source extraction could not be safely stored")


def ingest_local_document(source_id: str, source_path: str | Path, *, data_dir: str | Path,
                          route: str = "local") -> dict:
    """Extract a rights-approved local PDF/TXT into an isolated private area.

    Return values contain metadata and excerpts but never disclose local paths.
    An input/source hash mismatch, route mismatch, or existing altered output
    fails closed; outputs are immutable and deterministic for identical inputs.
    """
    if route != "local":
        _fail("local ingestion cannot execute on remote routes")
    # Read the rights authority only from the fixed Software Vault catalog.
    try:
        source_value, rights_review, authority_note_sha256 = _trusted_source_authority(source_id)
        source = _validate_rights(source_value, rights_review, route)
    except contracts.ContractError:
        _fail("trusted Source or rights review contract is invalid")
    input_path = Path(source_path).expanduser()
    if input_path.is_symlink():
        _fail("source file may not be a symbolic link")
    resolved_input = input_path.resolve()
    base_root = SOFTWARE_VAULT_ROOT.resolve()
    if _within(resolved_input, base_root):
        _fail("Software Vault/Base files cannot be imported as private papers")
    if not resolved_input.is_file():
        _fail("source file is unavailable")
    if resolved_input.stat().st_size <= 0 or resolved_input.stat().st_size > MAX_SOURCE_BYTES:
        _fail("source file size is invalid")
    suffix = resolved_input.suffix.lower()
    if suffix not in {".pdf", ".txt"}:
        _fail("only local PDF and UTF-8 text files are supported")
    try:
        source_bytes = resolved_input.read_bytes()
    except OSError:
        _fail("source file could not be read")
    if len(source_bytes) != resolved_input.stat().st_size or len(source_bytes) > MAX_SOURCE_BYTES:
        _fail("source file changed during read")
    original_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source["sha256"] != original_sha256:
        _fail("Source hash does not match local document")
    if source["anchors"]:
        _fail("Source must not contain stale anchors before extraction")
    result_source, excerpts, extractor = _build_extraction(source, source_bytes, suffix)

    requested_data_root = Path(data_dir).expanduser().absolute()
    cursor = Path(requested_data_root.anchor)
    for part in requested_data_root.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            _fail("data directory may not traverse symbolic links")
    data_root = requested_data_root.resolve()
    repository_root = Path(__file__).resolve().parents[3]
    if _within(data_root, repository_root):
        _fail("private output may not be written inside the repository")
    private_root = data_root / "knowledge_builder" / "private" / "source_extractions"
    if _within(private_root, base_root) or not _within(private_root, data_root):
        _fail("private output root overlaps Software Vault/Base")
    source_key = hashlib.sha256(source["source_id"].encode("utf-8")).hexdigest()[:24]
    immutable_key = hashlib.sha256(contracts.canonical_json({
        "source_id": source["source_id"], "source_sha256": original_sha256,
        "authority_note_sha256": authority_note_sha256,
        "extractor_name": extractor["name"], "extractor_version": extractor["version"],
    })).hexdigest()[:24]
    output_dir = private_root / f"{source_key}-{original_sha256}-{immutable_key}"
    cursor = data_root
    for part in private_root.relative_to(data_root).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            _fail("private output path may not traverse symbolic links")
    if _within(private_root.resolve(), repository_root) or _within(private_root.resolve(), base_root):
        _fail("private output root overlaps Software Vault/Base or repository")
    if output_dir.is_symlink():
        _fail("private output path may not traverse symbolic links")
    manifest = _canonical_manifest(result_source, original_sha256, extractor, excerpts,
                                    dict(rights_review), authority_note_sha256)
    _safe_write(output_dir, manifest, excerpts)
    return {"status": "stored_private", "storage_class": "private_local_only",
            "storage_id": output_dir.name, "manifest": manifest, "excerpts": excerpts}


def _is_link_or_junction(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def _reject_path_links(path: Path, *, include_leaf: bool = True) -> None:
    absolute = path.absolute()
    cursor = Path(absolute.anchor)
    parts = absolute.parts[1:] if include_leaf else absolute.parts[1:-1]
    for part in parts:
        cursor = cursor / part
        if _is_link_or_junction(cursor):
            _fail("local paper paths may not traverse symbolic links or junctions")


def _configured_private_root(data_dir: str | Path) -> tuple[Path, Path]:
    try:
        requested = Path(data_dir).expanduser().absolute()
        _reject_path_links(requested)
        data_root = requested.resolve()
        repository_root = Path(__file__).resolve().parents[3]
        if (_within(data_root, repository_root) or _within(repository_root, data_root) or
                _within(data_root, SOFTWARE_VAULT_ROOT) or _within(SOFTWARE_VAULT_ROOT, data_root)):
            _fail("private data directory may not overlap the repository or Software Vault")
        private_root = data_root / "knowledge_builder" / "private" / "source_extractions"
        cursor = data_root
        for part in private_root.relative_to(data_root).parts:
            cursor = cursor / part
            if _is_link_or_junction(cursor):
                _fail("private output path may not traverse symbolic links or junctions")
        return data_root, private_root
    except SourceIngestionError:
        raise
    except OSError:
        _fail("configured private data directory is inaccessible")


def _validate_local_relative_path(relative_path: str) -> PurePosixPath:
    if (not isinstance(relative_path, str) or not relative_path.strip() or
            "\\" in relative_path or ":" in relative_path or
            any(ord(char) < 32 for char in relative_path)):
        _fail("relative path must use forward slashes and stay within the selected folder")
    relative = PurePosixPath(relative_path)
    if (relative.is_absolute() or relative.as_posix() != relative_path or
            any(part in {"", ".", ".."} for part in relative.parts)):
        _fail("relative path must stay within the selected folder")
    return relative


def _contains_local_path(value: str) -> bool:
    return bool(
        re.search(r"(?i)(?<![A-Za-z0-9])[a-z]:", value) or "\\" in value or
        re.search(r"(?i)file:", value) or
        re.search(r"(?<!\w)/(?:[^\s/]+/)+[^\s/]+", value) or
        re.search(r"(?<!\w)/[A-Za-z0-9._~-]+\.[A-Za-z0-9]{1,12}(?=$|[\s,;)]])", value) or
        re.search(r"(?<!\w)~[/\\]", value)
    )


def _local_title_without_path(title: str) -> str:
    contracts._text(title, "title", max_length=1000)
    if _contains_local_path(title):
        _fail("title must not contain a local file path")
    return title.strip()


def _local_author_without_path(author: str) -> str:
    contracts._text(author, "author", max_length=500)
    if _contains_local_path(author):
        _fail("author must not contain a local file path")
    return author.strip()


def _encode_excerpts(excerpts: list[dict]) -> bytes:
    return b"".join(contracts.canonical_json(item) + b"\n" for item in excerpts)


def ingest_user_selected_local_paper(
    source_root: str | Path,
    relative_path: str,
    *,
    data_dir: str | Path,
    installation_id: str,
    expert_id: str,
    title: str,
    authors: list[str] | None = None,
    publication_year: int | None = None,
    confirm_local_processing: bool = False,
) -> dict:
    """Import a user-selected PDF/TXT as a private, local-only paper.

    This path deliberately makes no license or redistribution claim. The
    caller must explicitly attest that the user selected the file and wants
    private local processing. No original file or absolute path is persisted.
    """
    if confirm_local_processing is not True:
        _fail("explicit confirmation of local-only processing is required")
    try:
        if not isinstance(installation_id, str) or not contracts._INSTALLATION_ID.fullmatch(installation_id):
            raise contracts.ContractError("invalid installation ID")
        contracts._id(expert_id, "expert_id")
        if authors is None:
            authors = []
        if (not isinstance(authors, list) or len(authors) > 100 or
                any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in authors) or
                len({item.strip() for item in authors}) != len(authors)):
            raise contracts.ContractError("invalid authors")
        if publication_year is not None and (type(publication_year) is not int or
                                              not 1000 <= publication_year <= 9999):
            raise contracts.ContractError("invalid publication year")
    except contracts.ContractError:
        _fail("installation, expert, author, or publication metadata is invalid")
    clean_title = _local_title_without_path(title)
    try:
        clean_authors = [_local_author_without_path(item) for item in authors]
    except SourceIngestionError:
        raise
    except (TypeError, ValueError):
        _fail("author metadata is invalid")
    relative = _validate_local_relative_path(relative_path)

    try:
        root_requested = Path(source_root).expanduser().absolute()
        _reject_path_links(root_requested)
        if not root_requested.is_dir():
            _fail("selected local paper folder is unavailable")
        root = root_requested.resolve()
        repository_root = Path(__file__).resolve().parents[3]
        software_root = SOFTWARE_VAULT_ROOT.resolve()
        if (_within(root, repository_root) or _within(repository_root, root) or
                _within(root, software_root) or _within(software_root, root)):
            _fail("selected paper folder may not overlap the repository or Software Vault")
    except SourceIngestionError:
        raise
    except (OSError, TypeError, ValueError):
        _fail("selected local paper folder is unavailable")
    data_root, private_root = _configured_private_root(data_dir)
    if _within(root, data_root) or _within(data_root, root):
        _fail("selected paper folder and private data directory must be separate")

    try:
        input_path = root.joinpath(*relative.parts)
        _reject_path_links(input_path)
        resolved_input = input_path.resolve()
        if not _within(resolved_input, root) or not resolved_input.is_file():
            _fail("selected paper file is unavailable")
        if resolved_input.suffix.lower() not in {".pdf", ".txt"}:
            _fail("only local PDF and UTF-8 text files are supported")
        before = resolved_input.stat()
        if before.st_size <= 0 or before.st_size > MAX_SOURCE_BYTES:
            _fail("source file size is invalid")
        source_bytes = resolved_input.read_bytes()
        after = resolved_input.stat()
    except SourceIngestionError:
        raise
    except (OSError, TypeError, ValueError):
        _fail("source file could not be read")
    if (len(source_bytes) != before.st_size or len(source_bytes) > MAX_SOURCE_BYTES or
            (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)):
        _fail("source file changed during read")

    original_sha256 = hashlib.sha256(source_bytes).hexdigest()
    metadata_fingerprint = contracts.sha256_json({
        "content_sha256": original_sha256, "expert_id": expert_id,
        "title": clean_title, "authors": clean_authors,
        "publication_year": publication_year,
    })
    source_id = contracts.local_record_id(
        installation_id, "source", f"paper-{metadata_fingerprint}")
    source = {
        "schema_version": 1,
        "source_id": source_id,
        "version": f"sha256-{original_sha256}",
        "sha256": original_sha256,
        "title": clean_title,
        "authors": clean_authors,
        "publication_year": publication_year,
        "source_type": "paper",
        "locator": {"kind": "local_uri", "value": f"file://local-private/{original_sha256}"},
        "access_scope": "local_private",
        "license": {
            "license_id": "user-private-local-copy",
            "terms": "No redistribution license is asserted; processing is limited to private local analysis.",
        },
        "anchors": [],
        "rights": {"classification": "private", "allowed_routes": ["local"]},
    }
    try:
        source = contracts.validate_source(source)
    except contracts.ContractError:
        _fail("local Source metadata failed contract validation")
    result_source, excerpts, extractor = _build_extraction(source, source_bytes,
                                                            resolved_input.suffix.lower())
    excerpt_bytes = _encode_excerpts(excerpts)
    attestation = {
        "schema_version": 1,
        "user_selected_source": True,
        "explicit_local_processing_confirmation": True,
        "processing_scope": "local_only",
        "redistribution_permission_asserted": False,
    }
    manifest = {
        "schema_version": 1,
        "kind": "private_source_extraction",
        "storage_class": "private_local_only",
        "installation_id": installation_id,
        "expert_id": expert_id,
        "original_sha256": original_sha256,
        "extractor": extractor,
        "completeness": extractor["completeness"],
        "source": result_source,
        "processing_attestation": attestation,
        "excerpt_count": len(excerpts),
        "anchor_count": len(result_source["anchors"]),
        "duplicate_paragraph_count": len(result_source["anchors"]) - len(excerpts),
        "excerpts_sha256": hashlib.sha256(excerpt_bytes).hexdigest(),
        "excerpts_size_bytes": len(excerpt_bytes),
    }
    manifest["manifest_sha256"] = contracts.sha256_json(manifest)
    source_key = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:24]
    immutable_key = hashlib.sha256(contracts.canonical_json({
        "source_id": source_id, "source_sha256": original_sha256,
        "extractor_name": extractor["name"], "extractor_version": extractor["version"],
    })).hexdigest()[:24]
    output_dir = private_root / f"{source_key}-{original_sha256}-{immutable_key}"
    _safe_write(output_dir, manifest, excerpts)
    return {"status": "stored_private", "storage_class": "private_local_only",
            "storage_id": output_dir.name, "manifest": manifest, "excerpts": excerpts}


def _load_user_selected_extractions(data_dir: str | Path, installation_id: str,
                                    expert_id: str | None = None):
    try:
        if not isinstance(installation_id, str) or not contracts._INSTALLATION_ID.fullmatch(installation_id):
            raise contracts.ContractError("invalid installation ID")
        if expert_id is not None:
            contracts._id(expert_id, "expert_id")
    except contracts.ContractError:
        _fail("installation or expert ID is invalid")
    _data_root, private_root = _configured_private_root(data_dir)
    if _is_link_or_junction(private_root):
        _fail("private paper store is invalid")
    try:
        private_root.stat()
    except FileNotFoundError:
        return []
    except OSError:
        _fail("private paper store is inaccessible")
    if not private_root.is_dir():
        _fail("private paper store is invalid")
    try:
        folders = []
        for index, item in enumerate(private_root.iterdir(), start=1):
            if index > MAX_PRIVATE_EXTRACTION_RECORDS:
                _fail("private paper store record count exceeds limit")
            folders.append(item)
        folders.sort(key=lambda item: item.name)
    except OSError:
        _fail("private paper store is inaccessible")
    for folder in folders:
        if _is_link_or_junction(folder):
            _fail("private paper store may not contain symbolic links or junctions")
        if not folder.is_dir():
            continue
        manifest_path = folder / "manifest.json"
        excerpts_path = folder / "excerpts.jsonl"
        if _is_link_or_junction(manifest_path) or _is_link_or_junction(excerpts_path):
            _fail("private paper records may not contain symbolic links")
        if not manifest_path.is_file() or not excerpts_path.is_file():
            continue
        try:
            with manifest_path.open("rb") as stream:
                manifest_bytes = stream.read(2 * 1024 * 1024 + 1)
            if len(manifest_bytes) > 2 * 1024 * 1024:
                _fail("private paper manifest exceeds limit")
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            _fail("private paper manifest is unreadable")
        if (not isinstance(manifest, dict) or manifest.get("kind") != "private_source_extraction" or
                manifest.get("storage_class") != "private_local_only" or
                manifest.get("installation_id") != installation_id):
            continue
        if expert_id is not None and manifest.get("expert_id") != expert_id:
            continue
        declared_manifest_hash = manifest.get("manifest_sha256")
        unsigned_manifest = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
        if (not isinstance(declared_manifest_hash, str) or
                contracts.sha256_json(unsigned_manifest) != declared_manifest_hash or
                contracts.canonical_json(manifest) != manifest_bytes):
            _fail("private paper manifest integrity check failed")
        try:
            source = contracts.validate_source(manifest.get("source"))
        except contracts.ContractError:
            _fail("private paper Source is invalid")
        if (not source["source_id"].startswith(f"local:{installation_id}:source:") or
                source["access_scope"] != "local_private" or
                source["rights"] != {"classification": "private", "allowed_routes": ["local"]} or
                source["version"] != f"sha256-{source['sha256']}" or
                source["locator"] != {"kind": "local_uri",
                                      "value": f"file://local-private/{source['sha256']}"} or
                source["sha256"] != manifest.get("original_sha256") or
                manifest.get("processing_attestation") != {
                    "schema_version": 1,
                    "user_selected_source": True,
                    "explicit_local_processing_confirmation": True,
                    "processing_scope": "local_only",
                    "redistribution_permission_asserted": False,
                }):
            _fail("private paper local-only boundary is invalid")
        expected_original_id = "paper-" + contracts.sha256_json({
            "content_sha256": source["sha256"], "expert_id": manifest.get("expert_id"),
            "title": source["title"], "authors": source.get("authors", []),
            "publication_year": source.get("publication_year"),
        })
        if source["source_id"] != contracts.local_record_id(
                installation_id, "source", expected_original_id):
            _fail("private paper Source identity does not match its metadata")
        try:
            with excerpts_path.open("rb") as stream:
                excerpt_bytes = stream.read(MAX_EXCERPT_FILE_BYTES + 1)
        except OSError:
            _fail("private paper evidence is unreadable")
        if len(excerpt_bytes) > MAX_EXCERPT_FILE_BYTES:
            _fail("private paper evidence exceeds limit")
        if (len(excerpt_bytes) != manifest.get("excerpts_size_bytes") or
                hashlib.sha256(excerpt_bytes).hexdigest() != manifest.get("excerpts_sha256")):
            _fail("private paper evidence integrity check failed")
        excerpt_rows = []
        try:
            for line in excerpt_bytes.splitlines():
                if not line:
                    _fail("private paper evidence contains an empty record")
                value = json.loads(line.decode("utf-8"))
                if contracts.canonical_json(value) != line:
                    _fail("private paper evidence is not canonical")
                excerpt_rows.append(value)
        except (UnicodeDecodeError, json.JSONDecodeError):
            _fail("private paper evidence is invalid")
        if len(excerpt_rows) != manifest.get("excerpt_count"):
            _fail("private paper evidence count does not match")
        anchors = {item["anchor_id"]: item for item in source["anchors"]}
        if (manifest.get("anchor_count") != len(anchors) or
                manifest.get("duplicate_paragraph_count") != len(anchors) - len(excerpt_rows)):
            _fail("private paper Source and manifest counts do not match")
        seen_locations: set[str] = set()
        seen_hashes: set[str] = set()
        for excerpt in excerpt_rows:
            if (not isinstance(excerpt, dict) or set(excerpt) !=
                    {"extracted_text_sha256", "text", "locations"}):
                _fail("private paper evidence record is invalid")
            text = excerpt["text"]
            digest = excerpt["extracted_text_sha256"]
            locations = excerpt["locations"]
            if (not isinstance(text, str) or not isinstance(digest, str) or
                    hashlib.sha256(text.encode("utf-8")).hexdigest() != digest or
                    digest in seen_hashes or not isinstance(locations, list) or not locations or
                    any(not isinstance(item, str) for item in locations) or
                    len(locations) != len(set(locations))):
                _fail("private paper evidence text or locations are invalid")
            seen_hashes.add(digest)
            for anchor_id in locations:
                anchor = anchors.get(anchor_id)
                if (anchor is None or anchor["extracted_text_sha256"] != digest or
                        anchor_id in seen_locations):
                    _fail("private paper evidence does not match its Source anchors")
                seen_locations.add(anchor_id)
        if seen_locations != set(anchors):
            _fail("private paper evidence does not cover every Source anchor")
        yield manifest, excerpt_rows


def search_local_papers(query: str, *, data_dir: str | Path, installation_id: str,
                        expert_id: str, limit: int = 10) -> list[dict]:
    """Search only explicitly imported private papers for one expert/install."""
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        _fail("search query is invalid")
    if type(limit) is not int or not 1 <= limit <= 100:
        _fail("search result limit is invalid")
    entries = _load_user_selected_extractions(data_dir, installation_id, expert_id)
    terms = [term.casefold() for term in re.split(r"\s+", unicodedata.normalize("NFC", query).strip())
             if term]
    results = []
    for manifest, excerpts in entries:
        source = manifest["source"]
        anchors = {item["anchor_id"]: item for item in source["anchors"]}
        for excerpt in excerpts:
            lowered = excerpt["text"].casefold()
            matched = [term for term in terms if term in lowered]
            if not matched:
                continue
            for anchor_id in excerpt["locations"]:
                anchor = anchors[anchor_id]
                results.append({
                    "expert_id": manifest["expert_id"], "source_id": source["source_id"],
                    "source_version": source["version"], "source_sha256": source["sha256"],
                    "title": source["title"], "anchor_id": anchor_id,
                    "location": {"kind": anchor["kind"], "start": anchor["start"], "end": anchor["end"]},
                    "extracted_text_sha256": excerpt["extracted_text_sha256"],
                    "matched_terms": matched, "score": len(matched), "text": excerpt["text"],
                })
    return sorted(results, key=lambda item: (-item["score"], item["source_id"], item["anchor_id"]))[:limit]


def read_local_evidence(source_id: str, anchor_id: str, *, data_dir: str | Path,
                        installation_id: str, expert_id: str) -> dict:
    """Read one exact private page/paragraph after rechecking all stored hashes."""
    try:
        contracts._id(source_id, "source_id")
        contracts._id(anchor_id, "anchor_id")
    except contracts.ContractError:
        _fail("private evidence ID is invalid")
    for manifest, excerpts in _load_user_selected_extractions(data_dir, installation_id, expert_id):
        source = manifest["source"]
        if source["source_id"] != source_id:
            continue
        anchor = next((item for item in source["anchors"] if item["anchor_id"] == anchor_id), None)
        excerpt = next((item for item in excerpts if anchor_id in item["locations"]), None)
        if anchor is None or excerpt is None:
            break
        return {
            "expert_id": expert_id, "source_id": source_id,
            "source_version": source["version"], "source_sha256": source["sha256"],
            "title": source["title"], "anchor_id": anchor_id,
            "location": {"kind": anchor["kind"], "start": anchor["start"], "end": anchor["end"]},
            "extracted_text_sha256": excerpt["extracted_text_sha256"], "text": excerpt["text"],
        }
    _fail("private paper evidence was not found for this installation and expert")
