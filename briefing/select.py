"""통과 규칙, 지역 보장, 개수 자르기. AI도 네트워크도 모르는 순수 함수."""
from dataclasses import dataclass

from briefing.models import Article, NewsEvent, Outlet, RankedItem, Settings


@dataclass
class Passed:
    econ: list[NewsEvent]
    general: list[NewsEvent]


def pass_filter(events: list[NewsEvent], articles: list[Article], outlets: list[Outlet], s: Settings) -> Passed:
    """통과 규칙만 적용한다. 개수 제한은 apply_caps가 한다."""
    outlet_of_article = {a.id: a.outlet_id for a in articles}
    region_of_outlet = {o.id: o.region for o in outlets}
    passed = Passed([], [])
    for e in events:
        if e.continuity == "ongoing_no_progress":
            continue
        if e.category == "econ_it":
            if e.tier in ("major", "medium"):
                passed.econ.append(e)
            continue
        outlet_ids = {outlet_of_article[i] for i in e.article_ids if i in outlet_of_article}
        regions = [region_of_outlet[o] for o in outlet_ids if o in region_of_outlet]
        if e.domestic_kr:
            ok = regions.count("KR") >= s.general.kr_min_outlets
        else:
            ok = len(outlet_ids) >= s.general.min_outlets and len(set(regions)) >= s.general.min_regions
        if ok:
            passed.general.append(e)
    return passed


def _by_rank(events: list[NewsEvent], ranked: list[RankedItem]) -> list[NewsEvent]:
    rank = {r.event_key: r.rank for r in ranked}
    # 순위가 없는 사건은 맨 뒤로. sorted는 안정 정렬이라 원래 순서가 유지된다.
    return sorted(events, key=lambda e: (e.key not in rank, rank.get(e.key, 0)))


def apply_caps(passed: Passed, ranked: list[RankedItem], s: Settings) -> Passed:
    """지역 보장과 개수 제한을 적용한다. 각 목록은 순위순."""
    econ = _by_rank(passed.econ, ranked)
    chosen: set[str] = set()
    for region in s.econ.guaranteed_regions:
        first = next((e for e in econ if e.region == region), None)
        if first is not None and len(chosen) < s.econ.max:
            chosen.add(first.key)
    for e in econ:
        if len(chosen) >= s.econ.max:
            break
        chosen.add(e.key)
    return Passed(
        econ=[e for e in econ if e.key in chosen],
        general=_by_rank(passed.general, ranked)[: s.general.max],
    )
