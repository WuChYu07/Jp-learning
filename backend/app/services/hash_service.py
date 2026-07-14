import hashlib
from io import BytesIO

from pypdf import PdfReader

from app.models.schemas.common import SourceType

ALLOWED_MIME_TYPES: dict[str, SourceType] = {
    "application/pdf": SourceType.PDF,
    "image/jpeg": SourceType.IMAGE,
    "image/png": SourceType.IMAGE,
    "image/webp": SourceType.IMAGE,
}

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def compute_upload_hash(file_bytes: bytes, mime_type: str) -> str:
    """Hash strategy differs by file type — matches Module 0 spec."""
    if mime_type == "application/pdf":
        text = extract_pdf_text(file_bytes)
        return sha256_hex(text.encode("utf-8"))
    return sha256_hex(file_bytes)


def vocab_entry_hash(word: str, reading: str | None) -> str:
    normalized = f"{word.strip()}|{(reading or '').strip()}".lower()
    return sha256_hex(normalized.encode("utf-8"))


def grammar_entry_hash(grammar_point: str) -> str:
    return sha256_hex(grammar_point.strip().lower().encode("utf-8"))


def grammar_source_hash(
    *,
    grammar_point: str,
    image_urls: list[str],
    usages: list[object],
    block_ids: list[str],
) -> str:
    """Hash of parsed Notion slice — detects content changes independent of title."""

    def _example_blob(examples: object) -> str:
        parts: list[str] = []
        for ex in examples or []:
            if hasattr(ex, "japanese"):
                parts.append(
                    "|".join(
                        [
                            getattr(ex, "japanese", "") or "",
                            getattr(ex, "reading", "") or "",
                            getattr(ex, "chinese", "") or "",
                            getattr(ex, "english", "") or "",
                        ]
                    )
                )
            elif isinstance(ex, dict):
                parts.append(
                    "|".join(
                        [
                            ex.get("japanese", "") or "",
                            ex.get("reading", "") or "",
                            ex.get("chinese", "") or "",
                            ex.get("english", "") or "",
                        ]
                    )
                )
        return ";".join(parts)

    usage_parts: list[str] = []
    for usage in usages:
        if hasattr(usage, "semantic_concept"):
            usage_parts.append(
                "|".join(
                    [
                        getattr(usage, "semantic_concept", "") or "",
                        getattr(usage, "connection_rule", "") or "",
                        getattr(usage, "meaning_zh", "") or "",
                        _example_blob(getattr(usage, "example_sentences", None)),
                    ]
                )
            )
        elif isinstance(usage, dict):
            usage_parts.append(
                "|".join(
                    [
                        usage.get("semantic_concept", "") or "",
                        usage.get("connection_rule", "") or "",
                        usage.get("meaning_zh", "") or "",
                        _example_blob(usage.get("example_sentences")),
                    ]
                )
            )

    payload = "\n".join(
        [
            grammar_point.strip(),
            ",".join(sorted(set(block_ids))),
            ",".join(sorted(set(image_urls))),
            "||".join(usage_parts),
        ]
    )
    return sha256_hex(payload.encode("utf-8"))


def vocab_source_hash(
    *,
    word: str,
    reading: str | None,
    definitions: list[object],
) -> str:
    """Hash Notion vocab slice for change detection (meaning, notes, example text)."""

    def _example_blob(examples: object) -> str:
        parts: list[str] = []
        for ex in examples or []:
            if hasattr(ex, "japanese"):
                parts.append(
                    "|".join(
                        [
                            getattr(ex, "japanese", "") or "",
                            getattr(ex, "reading", "") or "",
                            getattr(ex, "chinese", "") or "",
                        ]
                    )
                )
            elif isinstance(ex, dict):
                parts.append(
                    "|".join(
                        [
                            ex.get("japanese", "") or "",
                            ex.get("reading", "") or "",
                            ex.get("chinese", "") or "",
                        ]
                    )
                )
        return ";".join(parts)

    def_parts: list[str] = []
    for definition in definitions:
        if hasattr(definition, "meaning_zh"):
            def_parts.append(
                "|".join(
                    [
                        getattr(definition, "meaning_zh", "") or "",
                        getattr(definition, "notes_zh", "") or "",
                        _example_blob(getattr(definition, "example_sentences", None)),
                    ]
                )
            )
        elif isinstance(definition, dict):
            def_parts.append(
                "|".join(
                    [
                        definition.get("meaning_zh", "") or "",
                        definition.get("notes_zh", "") or "",
                        _example_blob(definition.get("example_sentences")),
                    ]
                )
            )

    payload = "\n".join(
        [
            f"{word.strip()}|{(reading or '').strip()}".lower(),
            "||".join(def_parts),
        ]
    )
    return sha256_hex(payload.encode("utf-8"))
