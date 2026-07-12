"""CLI probe for Notion page blocks — validates API before full sync.

Usage (from backend/):
    python scripts/test_notion_fetch.py --focus vocabulary
    python scripts/test_notion_fetch.py --focus grammar
    python scripts/test_notion_fetch.py --focus both --download-images
    python scripts/test_notion_fetch.py --page-id YOUR_PAGE_ID --focus grammar
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.services.notion.analyzer import (
    analyze_blocks,
    build_validation_checklist,
    sections_to_json,
)
from app.services.notion.client import (
    NotionClient,
    NotionClientError,
    extract_page_id_from_url,
    extract_page_title,
    normalize_page_id,
)
from app.services.notion.pages import NotionPageConfigError, resolve_page_targets


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Notion page blocks and write validation report")
    parser.add_argument(
        "--focus",
        choices=["vocabulary", "grammar", "both"],
        default="both",
        help="Which Notion page(s) to probe (uses NOTION_VOCAB_PAGE_ID / NOTION_GRAMMAR_PAGE_ID)",
    )
    parser.add_argument(
        "--page-id",
        default=None,
        help="Override page ID for single-page probe (use with --focus vocabulary or grammar)",
    )
    parser.add_argument(
        "--page-url",
        default=None,
        help="Notion page URL (alternative to --page-id)",
    )
    parser.add_argument(
        "--token",
        default=settings.NOTION_TOKEN,
        help="Notion integration token (defaults to NOTION_TOKEN from .env)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND_ROOT.parent / "data" / "reports" / "notion_probe",
        help="Directory for JSON reports and optional images",
    )
    parser.add_argument(
        "--download-images",
        action="store_true",
        help="Download up to --max-images sample images per page",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=5,
        help="Max images to download per page when --download-images is set",
    )
    args = parser.parse_args()

    if not args.token:
        raise SystemExit("NOTION_TOKEN is required (set in .env or pass --token)")

    page_id_override = args.page_id
    if args.page_url:
        try:
            page_id_override = extract_page_id_from_url(args.page_url)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

    try:
        targets = resolve_page_targets(args.focus, page_id=page_id_override)
    except NotionPageConfigError as exc:
        raise SystemExit(str(exc)) from exc

    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(UTC).isoformat()

    all_passed = True
    reports: list[str] = []

    for page_focus, page_id in targets:
        page_output = output_root / page_focus if len(targets) > 1 else output_root
        summary, checklist, report_text = _probe_page(
            token=args.token,
            page_id=page_id,
            page_focus=page_focus,
            output_dir=page_output,
            fetched_at=fetched_at,
            download_images=args.download_images,
            max_images=args.max_images,
        )
        reports.append(report_text)
        if not checklist.get("all_passed"):
            all_passed = False

    if len(targets) > 1:
        combined_path = output_root / "validation_report.txt"
        combined_path.write_text("\n\n".join(reports), encoding="utf-8")
        print("\n\n".join(reports))
        print(f"\nCombined report: {combined_path}")
    else:
        print(reports[0])

    if not all_passed:
        raise SystemExit(1)


def _probe_page(
    *,
    token: str,
    page_id: str,
    page_focus: str,
    output_dir: Path,
    fetched_at: str,
    download_images: bool,
    max_images: int,
) -> tuple[dict, dict, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"

    page: dict | None = None
    blocks = []
    api_error: str | None = None
    image_download_ok: bool | None = None
    image_download_successes = 0
    image_download_attempts = 0
    downloaded_images: list[dict] = []

    try:
        page_id = normalize_page_id(page_id)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    try:
        with NotionClient(token) as client:
            page = client.get_page(page_id)
            blocks = client.fetch_all_blocks(page_id)

            if download_images:
                image_blocks = [b for b in blocks if b.type == "image" and b.image_url]
                # Use the most recently fetched blocks — their URLs are least likely expired.
                sample_blocks = image_blocks[-max_images:]
                if sample_blocks:
                    images_dir.mkdir(parents=True, exist_ok=True)
                    successes = 0
                    for index, block in enumerate(sample_blocks, start=1):
                        try:
                            fresh_url = client.refresh_image_url(block.id) or block.image_url
                            content, content_type = client.download_image(fresh_url)
                            ext = _guess_extension(content_type)
                            filename = f"{page_focus}_image_{index:02d}{ext}"
                            path = images_dir / filename
                            path.write_bytes(content)
                            successes += 1
                            downloaded_images.append(
                                {
                                    "block_id": block.id,
                                    "filename": filename,
                                    "bytes": len(content),
                                    "content_type": content_type,
                                }
                            )
                        except NotionClientError:
                            continue
                    image_download_ok = successes > 0
                    image_download_successes = successes
                    image_download_attempts = len(sample_blocks)
                else:
                    image_download_ok = None
                    image_download_successes = 0
                    image_download_attempts = 0
    except NotionClientError as exc:
        api_error = str(exc)
        print(f"ERROR ({page_focus}): {exc}", file=sys.stderr)

    analysis = analyze_blocks(blocks) if blocks else None
    checklist = (
        build_validation_checklist(
            page=page,
            analysis=analysis,
            image_download_ok=image_download_ok,
            api_error=api_error,
            image_download_successes=image_download_successes,
            image_download_attempts=image_download_attempts,
        )
        if analysis
        else {
            "all_passed": False,
            "no_auth_errors": api_error is None,
            "recursive_fetch_complete": False,
        }
    )

    summary = {
        "focus": page_focus,
        "fetched_at": fetched_at,
        "page_id": page_id,
        "page_title": extract_page_title(page) if page else None,
        "last_edited_time": page.get("last_edited_time") if page else None,
        "total_blocks": analysis.total_blocks if analysis else 0,
        "type_counts": analysis.type_counts if analysis else {},
        "image_count": analysis.image_count if analysis else 0,
        "table_count": analysis.type_counts.get("table", 0) if analysis else 0,
        "heading_count": analysis.heading_count if analysis else 0,
        "section_count": len(analysis.sections) if analysis else 0,
        "orphan_image_count": len(analysis.orphan_images) if analysis else 0,
        "image_download_successes": image_download_successes,
        "image_download_attempts": image_download_attempts,
        "api_error": api_error,
        "validation": checklist,
    }

    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if analysis:
        (output_dir / "sections_preview.json").write_text(
            json.dumps(sections_to_json(analysis.sections, limit=20), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raw_sample = [
            {
                "id": block.id,
                "type": block.type,
                "depth": block.depth,
                "text": block.text[:200] if block.text else "",
                "image_url": block.image_url,
            }
            for block in blocks[:50]
        ]
        (output_dir / "raw_blocks_sample.json").write_text(
            json.dumps(raw_sample, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    report_lines = _format_report(summary, checklist, downloaded_images, output_dir)
    report_text = "\n".join(report_lines)
    (output_dir / "validation_report.txt").write_text(report_text, encoding="utf-8")
    return summary, checklist, report_text


def _guess_extension(content_type: str | None) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    if content_type:
        base = content_type.split(";")[0].strip().lower()
        if base in mapping:
            return mapping[base]
    return ".bin"


def _format_report(
    summary: dict,
    checklist: dict,
    downloaded_images: list[dict],
    output_dir: Path,
) -> list[str]:
    lines = [
        f"Notion API Validation Report ({summary.get('focus', 'page')})",
        "=" * 40,
        f"Fetched at: {summary.get('fetched_at')}",
        f"Page title: {summary.get('page_title')}",
        f"Page ID: {summary.get('page_id')}",
        f"Total blocks: {summary.get('total_blocks')}",
        f"Images: {summary.get('image_count')} | Tables: {summary.get('table_count')} | Sections: {summary.get('section_count')}",
        "",
        "Checklist:",
    ]

    labels = {
        "page_metadata_readable": "Page metadata readable",
        "recursive_fetch_complete": "Recursive fetch complete",
        "heading_content_structure": "Heading → content structure",
        "image_blocks_present": "Image blocks present (if note has images)",
        "image_urls_downloadable": "Image URLs downloadable",
        "images_linked_to_sections": "Images linked to sections",
        "table_blocks_parseable": "Table blocks parseable (if note has tables)",
        "no_auth_errors": "No API auth errors",
    }
    for key, label in labels.items():
        status = "PASS" if checklist.get(key) else "FAIL"
        lines.append(f"  [{status}] {label}")

    lines.append("")
    lines.append(f"Overall: {'PASS' if checklist.get('all_passed') else 'FAIL'}")
    if summary.get("api_error"):
        lines.append(f"API error: {summary['api_error']}")
    for note in checklist.get("notes", []):
        lines.append(f"Note: {note}")
    if downloaded_images:
        lines.append("")
        lines.append("Downloaded images:")
        for item in downloaded_images:
            lines.append(f"  - {item['filename']} ({item['bytes']:,} bytes)")
    lines.append("")
    lines.append(f"Reports written to: {output_dir}")
    return lines


if __name__ == "__main__":
    main()
