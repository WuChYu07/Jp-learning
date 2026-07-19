"""MARUMARU (marumaru-x.com) HTML adapter — search listings + play-page lyrics.

Does NOT hit /*search-result* (disallowed by robots.txt). Search is done by
matching against category / rank / new listing pages.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from app.core.http_client import create_sync_client

logger = logging.getLogger(__name__)

BASE = "https://www.marumaru-x.com"
PLAY_ID_RE = re.compile(r"play-([a-zA-Z0-9]+)", re.I)
DATE_RE = re.compile(r"(?:發行日期|Release Date)\s*(\d{4})[/-](\d{2})[/-](\d{2})")
YOUTUBE_RE = re.compile(
    r"https?://(?:www\.)?(?:youtu\.be/[\w\-]+|youtube\.com/watch\?[^\s\"'<>]+)",
    re.I,
)

# Listing pages used instead of search-result endpoints.
LISTING_PATHS = (
    "/japanese-song/rank",
    "/japanese-song/most-liked",
    "/japanese-song/new",
    "/japanese-song/new-released",
    "/en/japanese-song/filter-category/jpop",
    "/en/japanese-song/filter-category/anm",
    "/japanese-song/filter-category/jpop",
    "/japanese-song/filter-category/anm",
)

SKIP_TITLES = {
    "official full mv",
    "official full audio",
    "official full karaoke",
    "official short special",
    "official full special",
    "official full lyric",
    "full audio",
}


@dataclass
class MarumaruCandidate:
    marumaru_id: str
    title: str
    artist: str = ""
    source_url: str = ""
    release_date: str | None = None  # YYYY-MM-DD
    category: str | None = None


@dataclass
class MarumaruLine:
    line_no: int
    text_ja: str
    text_zh: str | None = None


@dataclass
class MarumaruSongDetail:
    marumaru_id: str
    title: str
    artist: str
    source_url: str
    release_date: date | None = None
    category: str | None = None
    youtube_url: str | None = None
    lines: list[MarumaruLine] = field(default_factory=list)
    has_chinese: bool = False


def extract_marumaru_id(value: str) -> str | None:
    """Extract play id from URL or bare id.

    Bare ids look like ``q9oqljlmn4`` (lowercase alnum with digits). Plain song
    titles such as ``Pretender`` must NOT match.
    """
    value = (value or "").strip()
    if not value:
        return None
    m = PLAY_ID_RE.search(value)
    if m:
        return m.group(1)
    # Bare id: lowercase alphanumeric, must include a digit, length 8–16
    if re.fullmatch(r"[a-z0-9]{8,16}", value) and re.search(r"\d", value):
        return value
    return None


def play_url(marumaru_id: str) -> str:
    return f"{BASE}/japanese-song/play-{marumaru_id}"


def _headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (compatible; Komorebi/1.0; +https://github.com/WuChYu07/Jp-learning)"
        ),
        "Accept-Language": "zh-TW,zh;q=0.9,ja;q=0.8,en;q=0.7",
    }


def _get_html(url: str) -> str:
    with create_sync_client(timeout=45.0, follow_redirects=True) as client:
        resp = client.get(url, headers=_headers())
        resp.raise_for_status()
        return resp.text


def _ruby_ja_text(el: Tag) -> str:
    """Flatten Japanese lyric node: keep kanji/kana, drop furigana <rt>."""
    clone = BeautifulSoup(str(el), "lxml")
    root = clone.body if clone.body else clone
    for rt in root.find_all("rt"):
        rt.decompose()
    for rp in root.find_all("rp"):
        rp.decompose()
    text = root.get_text("", strip=False)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_listing(html: str, page_url: str) -> list[MarumaruCandidate]:
    soup = BeautifulSoup(html, "lxml")
    out: list[MarumaruCandidate] = []
    seen: set[str] = set()

    for title_el in soup.select("h2.card-title.name a[href*='play-'], h2.card-title a[href*='play-']"):
        href = title_el.get("href") or ""
        mid = extract_marumaru_id(href)
        if not mid or mid in seen:
            continue
        title = title_el.get_text(" ", strip=True)
        if not title or title.lower() in SKIP_TITLES:
            continue
        artist = ""
        parent = title_el.find_parent(class_=re.compile(r"card"))
        if parent:
            singer = parent.select_one("h3.card-subtitle.singer, .singer")
            if singer:
                artist = singer.get_text(" ", strip=True)
            badge = parent.select_one(".badge")
            release = None
            if badge:
                bm = re.search(r"(\d{4})-(\d{2})-(\d{2})", badge.get_text())
                if bm:
                    release = f"{bm.group(1)}-{bm.group(2)}-{bm.group(3)}"
            else:
                release = None
        else:
            release = None

        seen.add(mid)
        abs_url = urljoin(BASE + "/", href)
        out.append(
            MarumaruCandidate(
                marumaru_id=mid,
                title=title,
                artist=artist,
                source_url=abs_url if "play-" in abs_url else play_url(mid),
                release_date=release,
            )
        )
    return out


def search_listings(query: str, *, limit: int = 12) -> list[MarumaruCandidate]:
    """Match query against scraped listing pages (title / artist)."""
    q = (query or "").strip().lower()
    if not q:
        return []

    pooled: dict[str, MarumaruCandidate] = {}
    for path in LISTING_PATHS:
        url = urljoin(BASE, path)
        try:
            html = _get_html(url)
            for c in _parse_listing(html, url):
                pooled.setdefault(c.marumaru_id, c)
        except Exception:
            logger.exception("MARUMARU listing fetch failed: %s", url)

    scored: list[tuple[int, MarumaruCandidate]] = []
    for c in pooled.values():
        title_l = c.title.lower()
        artist_l = c.artist.lower()
        score = 0
        if q == title_l:
            score = 100
        elif q in title_l:
            score = 80
        elif title_l in q:
            score = 70
        elif q in artist_l:
            score = 50
        else:
            # token overlap
            tokens = [t for t in re.split(r"\s+", q) if t]
            hits = sum(1 for t in tokens if t in title_l or t in artist_l)
            if hits:
                score = 30 + hits * 10
        if score:
            scored.append((score, c))

    scored.sort(key=lambda x: (-x[0], x[1].title))
    return [c for _, c in scored[:limit]]


def recommend(*, limit: int = 10) -> list[MarumaruCandidate]:
    """Recommend from weekly rank + most-liked (deduped)."""
    pooled: dict[str, MarumaruCandidate] = {}
    for path in ("/japanese-song/rank", "/japanese-song/most-liked"):
        url = urljoin(BASE, path)
        try:
            html = _get_html(url)
            for c in _parse_listing(html, url):
                pooled.setdefault(c.marumaru_id, c)
        except Exception:
            logger.exception("MARUMARU recommend fetch failed: %s", url)
    return list(pooled.values())[:limit]


def parse_play_page(html: str, *, marumaru_id: str, source_url: str) -> MarumaruSongDetail:
    soup = BeautifulSoup(html, "lxml")

    title = ""
    title_el = soup.select_one(".song-title, .font-jp1.song-name, h1")
    if title_el:
        title = title_el.get_text(" ", strip=True)
    if " - " in title:
        # "Pretender - Official髭男dism" → prefer page singer for artist
        pass

    artist = ""
    singer_el = soup.select_one(".singer, h3.card-subtitle.singer, .card-subtitle.singer")
    if singer_el:
        artist = singer_el.get_text(" ", strip=True)
    if not artist and " - " in title:
        parts = title.split(" - ", 1)
        title, artist = parts[0].strip(), parts[1].strip()

    # Clean title if still contains artist suffix
    if artist and title.endswith(artist):
        title = title[: -len(artist)].rstrip(" -–—")

    release: date | None = None
    page_text = soup.get_text("\n", strip=True)
    dm = DATE_RE.search(page_text)
    if dm:
        release = date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))

    category = None
    tag = soup.select_one("a[href*='filter-category']")
    if tag:
        raw = tag.get_text(strip=True).lstrip("#").lower()
        category = raw or None

    youtube_url = None
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        if YOUTUBE_RE.search(href):
            youtube_url = href.strip()
            break
    if not youtube_url:
        ym = YOUTUBE_RE.search(html)
        if ym:
            youtube_url = ym.group(0)

    lines: list[MarumaruLine] = []
    blocks = soup.select(".mr-lyrics-list > div")
    for block in blocks:
        num_el = block.select_one(".lyrics-number")
        src_el = block.select_one("p.lyrics-source, .lyrics-source")
        zh_el = block.select_one(".lyrics-translate-zh, .translate-zh")
        if not src_el:
            continue
        try:
            line_no = int(num_el.get_text(strip=True)) if num_el else len(lines) + 1
        except ValueError:
            line_no = len(lines) + 1
        text_ja = _ruby_ja_text(src_el)
        if not text_ja:
            continue
        text_zh = zh_el.get_text(" ", strip=True) if zh_el else None
        if text_zh and ("目前沒有中文" in text_zh or "no chinese" in text_zh.lower()):
            text_zh = None
        lines.append(MarumaruLine(line_no=line_no, text_ja=text_ja, text_zh=text_zh))

    has_chinese = any(bool(ln.text_zh) for ln in lines)
    if not title:
        title = f"song-{marumaru_id}"

    return MarumaruSongDetail(
        marumaru_id=marumaru_id,
        title=title,
        artist=artist,
        source_url=source_url,
        release_date=release,
        category=category,
        youtube_url=youtube_url,
        lines=lines,
        has_chinese=has_chinese,
    )


def fetch_song(marumaru_id: str) -> MarumaruSongDetail:
    url = play_url(marumaru_id)
    html = _get_html(url)
    return parse_play_page(html, marumaru_id=marumaru_id, source_url=url)


def parse_pasted_lyrics(
    text_ja_block: str,
    text_zh_block: str | None = None,
) -> list[MarumaruLine]:
    """Split pasted multiline lyrics into lines (JA required, ZH optional aligned)."""
    ja_lines = [ln.strip() for ln in (text_ja_block or "").splitlines() if ln.strip()]
    zh_lines = (
        [ln.strip() for ln in (text_zh_block or "").splitlines() if ln.strip()]
        if text_zh_block
        else []
    )
    out: list[MarumaruLine] = []
    for i, ja in enumerate(ja_lines, start=1):
        zh = zh_lines[i - 1] if i - 1 < len(zh_lines) else None
        out.append(MarumaruLine(line_no=i, text_ja=ja, text_zh=zh))
    return out
