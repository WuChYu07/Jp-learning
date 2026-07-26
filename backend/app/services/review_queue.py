"""Mixed flashcard queues: due + new + low-score, day-stable shuffle."""

from __future__ import annotations

import hashlib
import random
from datetime import UTC, datetime


def daily_seed(user_id: str, salt: str = "") -> int:
    day = datetime.now(UTC).date().isoformat()
    digest = hashlib.sha256(f"{user_id}:{day}:{salt}".encode()).hexdigest()
    return int(digest[:8], 16)


def seeded_shuffle(ids: list[str], seed: int) -> list[str]:
    rng = random.Random(seed)
    out = list(ids)
    rng.shuffle(out)
    return out


def weighted_order(
    ids: list[str],
    score_by_id: dict[str, float],
    seed: int,
) -> list[str]:
    """Order ids with low-score bias without depleting randomness across the day.

    Linear weight (not squared) so a handful of rock-bottom scores don't
    monopolize every draw and crowd out other below-average words.
    """
    if not ids:
        return []
    rng = random.Random(seed)
    # Soft ranking: sample without replacement using score weights
    remaining = list(ids)
    ordered: list[str] = []
    while remaining:
        weights = [(100.0 - float(score_by_id.get(vid, 0.0)) + 1.0) for vid in remaining]
        pick = rng.choices(remaining, weights=weights, k=1)[0]
        ordered.append(pick)
        remaining.remove(pick)
    return ordered


def build_mixed_review_queue(
    *,
    due_ids: list[str],
    new_ids: list[str],
    score_by_id: dict[str, float],
    seed: int,
    due_per_block: int = 4,
    new_per_block: int = 4,
    low_per_block: int = 2,
    cooldown_ids: set[str] | None = None,
) -> list[str]:
    """
    Build a day-stable mixed deck.

    Each block prefers: due / never-seen / low-score (including not-yet-due).
    Empty pools are filled from whatever remains so pagination still works.
    `cooldown_ids` (e.g. reviewed in the last 24h) are excluded from the
    low-score pool so the same worst-scoring words don't get pulled back in
    on the very next session before their score has a chance to move.
    """
    due = seeded_shuffle(due_ids, seed)
    new = seeded_shuffle(new_ids, seed + 1)
    excluded = set(due_ids) | (cooldown_ids or set())
    early_pool = [vid for vid in score_by_id if vid not in excluded]
    early = weighted_order(early_pool, score_by_id, seed + 2)

    queue: list[str] = []
    seen: set[str] = set()
    di = ni = ei = 0
    block_size = due_per_block + new_per_block + low_per_block

    def take(src: list[str], idx: int, n: int) -> tuple[list[str], int]:
        picked: list[str] = []
        while n > 0 and idx < len(src):
            vid = src[idx]
            idx += 1
            if vid in seen:
                continue
            seen.add(vid)
            picked.append(vid)
            n -= 1
        return picked, idx

    while di < len(due) or ni < len(new) or ei < len(early):
        block: list[str] = []
        chunk, di = take(due, di, due_per_block)
        block.extend(chunk)
        chunk, ni = take(new, ni, new_per_block)
        block.extend(chunk)
        chunk, ei = take(early, ei, low_per_block)
        block.extend(chunk)

        # Fill shortfall from any remaining pool
        while len(block) < block_size:
            if di < len(due):
                chunk, di = take(due, di, 1)
            elif ni < len(new):
                chunk, ni = take(new, ni, 1)
            elif ei < len(early):
                chunk, ei = take(early, ei, 1)
            else:
                break
            if not chunk:
                # take skipped duplicates; avoid infinite loop
                if di >= len(due) and ni >= len(new) and ei >= len(early):
                    break
                continue
            block.extend(chunk)

        if not block:
            break
        queue.extend(block)

    return queue
