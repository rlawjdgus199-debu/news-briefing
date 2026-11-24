"""매체별 피드를 읽어 기사 목록을 만든다."""
import calendar
import html
import re
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

import feedparser

from briefing.models import Article, Outlet, Settings

FetchText = Callable[[str], str]

USER_AGENT = "Mozilla/5.0 (compatible; feed-reader)"
SUMMARY_MAX = 300
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


@dataclass
class CollectResult:
    articles: list[Article]
    failed_outlet_ids: list[str]


def http_get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        if resp.status != 200:
            raise OSError(f"HTTP {resp.status}")
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _clean(text: str) -> str:
    return _SPACE.sub(" ", html.unescape(_TAG.sub(" ", text or ""))).strip()


def _published(entry) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)


def parse_feed(xml: str, outlet: Outlet) -> list[Article]:
    """피드 글을 기사 목록으로 바꾼다. id는 비워 둔다(collect가 붙인다)."""
    feed = feedparser.parse(xml)
    if not feed.entries and feed.bozo:
        raise ValueError("피드를 읽을 수 없습니다")
    articles = []
    for e in feed.entries:
        title = _clean(e.get("title", ""))
        url = (e.get("link") or "").strip()
        if not title or not url:
            continue
        summary = _clean(e.get("summary", ""))[:SUMMARY_MAX]
        if outlet.google_news:
            # 구글 뉴스 제목은 "제목 - 매체이름", 요약은 내용 없는 링크 HTML이다.
            title = title.rsplit(" - ", 1)[0]
            summary = ""
        articles.append(Article("", outlet.id, title, summary, url, _published(e)))
    return articles


def _collect_outlet(outlet: Outlet, settings: Settings, now: datetime, fetch_text: FetchText) -> list[Article]:
    found: list[Article] = []
    for url in outlet.feeds:
        try:
            found.extend(parse_feed(fetch_text(url), outlet))
        except Exception:
            continue  # 피드 하나의 실패는 넘어간다. 전부 실패하면 0건이 되어 실패로 잡힌다.
    cutoff = now - timedelta(hours=settings.window_hours)
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    dated: list[Article] = []
    undated: list[Article] = []
    for a in found:
        if a.url in seen_urls or a.title in seen_titles:
            continue
        seen_urls.add(a.url)
        seen_titles.add(a.title)
        if a.published_at is None:
            undated.append(a)
        elif a.published_at >= cutoff:
            dated.append(a)
    dated.sort(key=lambda a: a.published_at, reverse=True)
    return (dated + undated)[: outlet.max_items]


def collect(outlets: list[Outlet], settings: Settings, now: datetime,
            fetch_text: FetchText = http_get_text) -> CollectResult:
    with ThreadPoolExecutor(max_workers=8) as pool:
        per_outlet = list(pool.map(lambda o: _collect_outlet(o, settings, now, fetch_text), outlets))
    articles: list[Article] = []
    failed: list[str] = []
    for outlet, found in zip(outlets, per_outlet):
        if not found:
            failed.append(outlet.id)
        for a in found:
            articles.append(replace(a, id=f"a{len(articles) + 1}"))
    return CollectResult(articles, failed)
