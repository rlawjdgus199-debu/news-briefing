"""하루 한 번의 실행: 수집 → 묶기 → 통과 계산 → 순위 → 자르기 → 시장 → 전송 → 보관."""
import argparse
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from briefing.ai import AiError, AskJson, make_ask_json
from briefing.cluster import cluster_events
from briefing.collect import CollectResult, collect
from briefing.config import load_settings, load_sources
from briefing.markets import fetch_markets
from briefing.models import Article, BriefingItem, MarketQuote, MarketSpec, NewsEvent, Outlet, RankedItem, Settings
from briefing.rank import rank_events
from briefing.render import Briefing, render_failure, render_markdown, render_slack
from briefing.select import apply_caps, pass_filter
from briefing.slack import send_slack
from briefing.state import load_history, save_archive, save_history

KST = timezone(timedelta(hours=9))


class BriefingError(Exception):
    """브리핑을 만들 수 없는 상황. 메시지를 그대로 사용자에게 보여 준다."""


@dataclass
class Deps:
    now: datetime
    outlets: list[Outlet]
    settings: Settings
    collect: Callable[[list[Outlet], Settings, datetime], CollectResult]
    ask: AskJson
    fetch_markets: Callable[[list[MarketSpec]], list[MarketQuote] | None]
    send: Callable[[str], None]
    state_path: str
    archive_dir: str
    dry_run: bool
    log: Callable[[str], None]


def _to_items(events: list[NewsEvent], ranked: list[RankedItem], articles: list[Article],
              outlets: list[Outlet]) -> list[BriefingItem]:
    written = {r.event_key: r for r in ranked}
    article_of = {a.id: a for a in articles}
    items = []
    for e in events:
        r = written.get(e.key)
        if r is None:
            continue  # AI가 제목과 설명을 쓰지 않은 사건은 싣지 않는다
        found = [article_of[i] for i in e.article_ids if i in article_of]
        outlet_ids = {a.outlet_id for a in found}
        direct = {o.id for o in outlets if not o.google_news}
        # 구글 뉴스 링크는 한 번 거쳐 가는 주소라, 매체로 바로 가는 링크를 먼저 고른다.
        best = next((a for a in found if a.outlet_id in direct), found[0])
        items.append(BriefingItem(
            title_ko=r.title_ko, why_ko=r.why_ko, region=e.region,
            ongoing=e.continuity == "ongoing_progress",
            outlet_names=[o.name for o in outlets if o.id in outlet_ids], url=best.url,
        ))
    return items


def _build(deps: Deps, today: str) -> Briefing:
    s = deps.settings
    collected = deps.collect(deps.outlets, s, deps.now)
    failed = collected.failed_outlet_ids
    deps.log(f"수집: 기사 {len(collected.articles)}건, 실패 매체 {len(failed)}곳")
    if len(failed) * 2 >= len(deps.outlets):
        raise BriefingError(f"매체 {len(deps.outlets)}곳 중 {len(failed)}곳 수집 실패")

    history = load_history(deps.state_path, today, s.history_days)
    events = cluster_events(collected.articles, deps.outlets, history, deps.ask)
    passed = pass_filter(events, collected.articles, deps.outlets, s)
    deps.log(f"사건 {len(events)}건 중 통과: 경제·IT {len(passed.econ)}건, 그 외 {len(passed.general)}건")
    ranked = rank_events(passed.econ + passed.general, collected.articles, deps.ask)
    final = apply_caps(passed, ranked, s)

    return Briefing(
        date=today,
        markets=deps.fetch_markets(s.markets),
        econ=_to_items(final.econ, ranked, collected.articles, deps.outlets),
        general=_to_items(final.general, ranked, collected.articles, deps.outlets),
        failed_outlet_names=[o.name for o in deps.outlets if o.id in failed],
    )


def run(deps: Deps) -> Literal["sent", "failed"]:
    today = deps.now.astimezone(KST).strftime("%Y-%m-%d")
    deliver = deps.log if deps.dry_run else deps.send
    try:
        briefing = _build(deps, today)
    except Exception as e:
        # 아무 말 없이 브리핑이 안 오는 일이 없도록, 실패했다는 사실을 알린다.
        known = isinstance(e, (BriefingError, AiError))
        reason = str(e) if known else f"{type(e).__name__}: {e}"
        deps.log(f"브리핑 생성 실패: {reason}")  # 슬랙 전송까지 실패해도 실행 기록에는 이유가 남는다
        deliver(render_failure(today, reason))
        return "failed"
    deliver(render_slack(briefing))
    if not deps.dry_run:
        save_archive(deps.archive_dir, today, render_markdown(briefing))
        save_history(deps.state_path, today, briefing.econ + briefing.general, deps.settings.history_days)
    return "sent"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="briefing", description="매일 아침 뉴스 브리핑")
    parser.add_argument("--dry-run", action="store_true", help="슬랙으로 보내지 않고 화면에만 출력한다")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # 윈도우 콘솔에서 한글과 이모지가 깨지지 않게

    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not args.dry_run and not webhook:
        print("SLACK_WEBHOOK_URL 환경 변수가 필요합니다. 연습 실행은 --dry-run을 붙이세요.")
        return 1

    now = datetime.now(timezone.utc)
    try:
        settings, outlets = load_settings(), load_sources()
    except Exception as e:
        # 설정 파일을 잘못 고친 경우에도 아무 말 없이 멈추지 않는다.
        reason = f"설정 파일 오류 ({type(e).__name__}): {str(e)[:300]}"
        print(f"브리핑 생성 실패: {reason}")
        if not args.dry_run:
            send_slack(render_failure(now.astimezone(KST).strftime("%Y-%m-%d"), reason), webhook)
        return 1
    deps = Deps(
        now=now, outlets=outlets, settings=settings,
        collect=collect, ask=make_ask_json(settings.model), fetch_markets=fetch_markets,
        send=lambda text: send_slack(text, webhook),
        state_path="state/sent.json", archive_dir="archive",
        dry_run=args.dry_run, log=print,
    )
    return 0 if run(deps) == "sent" else 1
