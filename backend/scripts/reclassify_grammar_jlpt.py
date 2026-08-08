"""One-off maintenance: fill missing grammar content from Notion images and
classify a JLPT level for every grammar currently at jlpt_level='unknown'.

Two paths per grammar with no real content yet (no meaning_zh/examples,
i.e. only ever raw-parsed from Notion headings):
  - has images -> enrich_grammar() (AI reads the actual images; also sets
    jlpt_level as a side effect of full content generation)
  - no images  -> explain_grammar() (AI teacher rewrite from grammar_point
    + whatever sparse usages exist)

Grammar that already has real content just gets a JLPT level via the
existing lightweight batch classifier (jlpt_enrichment_service), without
rewriting its content.

Deliberately skips grammar that already has a non-unknown jlpt_level —
same safety guard jlpt_enrichment_service.apply() already uses.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.reclassify_grammar_jlpt
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.supabase import get_supabase_client  # noqa: E402
from app.services.grammar_enrichment_service import grammar_enrichment_service  # noqa: E402
from app.services.jlpt_enrichment_service import jlpt_enrichment_service  # noqa: E402
from app.models.schemas.jlpt import JlptApplyItem  # noqa: E402

LOG_PATH = Path(__file__).resolve().parent / "reclassify_grammar_jlpt.log"
DELAY_SECONDS = 2.5


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def has_real_content(usages: list[dict]) -> bool:
    return any((u.get("meaning_zh") or "").strip() for u in usages) or any(
        u.get("example_sentences") for u in usages
    )


def main() -> None:
    db = get_supabase_client()
    rows = db.table("grammars").select("id, grammar_point, jlpt_level, image_urls").execute().data or []
    unknown_rows = [r for r in rows if r.get("jlpt_level") == "unknown"]
    ids = [r["id"] for r in unknown_rows]

    usage_rows = (
        db.table("grammar_usages")
        .select("grammar_id, meaning_zh, example_sentences")
        .in_("grammar_id", ids)
        .execute()
        .data
        or []
    )
    from collections import defaultdict

    usages_by_gid: dict[str, list[dict]] = defaultdict(list)
    for u in usage_rows:
        usages_by_gid[u["grammar_id"]].append(u)

    sparse = [r for r in unknown_rows if not has_real_content(usages_by_gid.get(r["id"], []))]
    has_content = [r for r in unknown_rows if has_real_content(usages_by_gid.get(r["id"], []))]

    log(
        f"total unknown={len(unknown_rows)} sparse(needs content)={len(sparse)} "
        f"has_content(needs jlpt only)={len(has_content)}"
    )

    ok, failed = 0, []
    for i, row in enumerate(sparse, 1):
        gid, name = row["id"], row["grammar_point"]
        has_images = bool(row.get("image_urls"))
        label = "enrich_grammar(images)" if has_images else "explain_grammar(text)"
        try:
            if has_images:
                grammar_enrichment_service.enrich_grammar(gid)
            else:
                grammar_enrichment_service.explain_grammar(gid)
            ok += 1
            log(f"[{i}/{len(sparse)}] OK  {label:24s} {name}")
        except Exception as exc:  # noqa: BLE001
            failed.append((name, str(exc)))
            log(f"[{i}/{len(sparse)}] FAIL {label:24s} {name} :: {exc}")
        time.sleep(DELAY_SECONDS)

    log(f"content-fill pass done: {ok} ok, {len(failed)} failed")

    # Lightweight JLPT-only classification for everything still unknown
    # (has_content group, plus any sparse items where enrichment ran but the
    # AI genuinely returned jlpt_level=unknown).
    classified = 0
    while True:
        try:
            preview = jlpt_enrichment_service.preview(entity="grammar", limit=20)
        except Exception as exc:  # noqa: BLE001
            log(f"jlpt batch classify: stopped early :: {exc}")
            break
        if not preview.items:
            break
        items = [
            JlptApplyItem(entity=it.entity, id=it.id, jlpt_level=it.suggested_jlpt)
            for it in preview.items
        ]
        try:
            result = jlpt_enrichment_service.apply(items)
        except Exception as exc:  # noqa: BLE001
            log(f"jlpt batch apply: stopped early :: {exc}")
            break
        classified += result.updated
        log(f"jlpt batch classify: +{result.updated} (remaining_unknown was {preview.remaining_unknown})")
        if result.updated == 0:
            break
        time.sleep(DELAY_SECONDS)

    log(f"DONE. content-filled={ok}/{len(sparse)} (failed={len(failed)}), jlpt-classified={classified}")
    if failed:
        log("failures:")
        for name, err in failed:
            log(f"  - {name}: {err}")


if __name__ == "__main__":
    main()
