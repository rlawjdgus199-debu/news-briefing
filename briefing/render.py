"""브리핑 글 만들기. 입력만 보고 글을 돌려주는 순수 함수."""
from dataclasses import dataclass
from datetime import date, timedelta

from briefing.models import BriefingItem, MarketQuote

WEEKDAYS = "월화수목금토일"
REGION_KO = {"KR": "한국", "US": "미국", "CN": "중국", "JP": "일본", "EU": "유럽", "OTHER": "세계"}
MAX_OUTLET_NAMES = 4
MARKETS_ON_FIRST_LINE = 4
EMPTY_SECTION = "오늘은 큰 뉴스 없음"


@dataclass
class Briefing:
    date: str  # YYYY-MM-DD, 한국 날짜
    markets: list[MarketQuote] | None
    econ: list[BriefingItem]
    general: list[BriefingItem]
    failed_outlet_names: list[str]


def _same(text: str) -> str:
    return text


def _slack_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _month_day(d: date) -> str:
    return f"{d.month}/{d.day}"


def _day_label(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{_month_day(d)}({WEEKDAYS[d.weekday()]})"


def _quote_text(q: MarketQuote, esc) -> str:
    if q.unit == "pct":
        return f"{esc(q.label)} {q.value:.2f}%"
    value = f"{q.value:,.1f}원" if q.unit == "krw" else f"{q.value:,.2f}"
    return f"{esc(q.label)} {value} ({q.change_pct:+.1f}%)"


def _market_lines(b: Briefing, esc) -> list[str]:
    if not b.markets:
        return []
    texts = [_quote_text(q, esc) for q in b.markets]
    lines = [" | ".join(texts[:MARKETS_ON_FIRST_LINE]), " | ".join(texts[MARKETS_ON_FIRST_LINE:])]
    lines = [line for line in lines if line]
    # 주말·공휴일: 가장 오래된 종가가 전날보다 이르면 그 날짜를 밝힌다.
    oldest = min(date.fromisoformat(q.date) for q in b.markets)
    if oldest < date.fromisoformat(b.date) - timedelta(days=1):
        lines[-1] += f" ({_month_day(oldest)} 종가)"
    return lines


def _outlets_text(names: list[str], esc) -> str:
    text = " · ".join(esc(n) for n in names[:MAX_OUTLET_NAMES])
    extra = len(names) - MAX_OUTLET_NAMES
    return f"{text} 외 {extra}곳" if extra > 0 else text


def _slack_item(item: BriefingItem) -> list[str]:
    ongoing = " (이어지는 소식)" if item.ongoing else ""
    url = item.url.replace("|", "%7C").replace(">", "%3E")
    return [
        f"• *{_slack_escape(item.title_ko)}*{ongoing}  [{REGION_KO[item.region]}]",
        f"  → {_slack_escape(item.why_ko)}",
        f"  {_outlets_text(item.outlet_names, _slack_escape)}  <{url}|원문>",
    ]


def _slack_section(title: str, items: list[BriefingItem]) -> list[str]:
    lines = [f"{title} ({len(items)}건)*"]
    if not items:
        return lines + [EMPTY_SECTION]
    for item in items:
        lines += _slack_item(item)
    return lines


def render_slack(b: Briefing) -> str:
    lines = [f"📊 *{_day_label(b.date)} 아침 브리핑*"]
    lines += _market_lines(b, _slack_escape)
    lines += [""] + _slack_section("💰 *경제·IT", b.econ)
    lines += [""] + _slack_section("🌍 *그 외 큰 뉴스", b.general)
    if b.failed_outlet_names:
        lines += ["", "수집 실패: " + ", ".join(_slack_escape(n) for n in b.failed_outlet_names)]
    return "\n".join(lines)


def _markdown_section(title: str, items: list[BriefingItem]) -> list[str]:
    lines = [f"## {title} ({len(items)}건)", ""]
    if not items:
        return lines + [EMPTY_SECTION]
    for item in items:
        ongoing = " (이어지는 소식)" if item.ongoing else ""
        lines += [
            f"- **{item.title_ko}**{ongoing} [{REGION_KO[item.region]}]",
            f"  - 왜 중요한가: {item.why_ko}",
            f"  - {_outlets_text(item.outlet_names, _same)} · [원문]({item.url})",
        ]
    return lines


def render_markdown(b: Briefing) -> str:
    lines = [f"# {b.date} 아침 브리핑", ""]
    market = _market_lines(b, _same)
    if market:
        lines += ["  \n".join(market), ""]
    lines += _markdown_section("경제·IT", b.econ) + [""]
    lines += _markdown_section("그 외 큰 뉴스", b.general)
    if b.failed_outlet_names:
        lines += ["", "수집 실패: " + ", ".join(b.failed_outlet_names)]
    return "\n".join(lines) + "\n"


def render_failure(date_iso: str, reason: str) -> str:
    return f"⚠️ *{_day_label(date_iso)} 브리핑 생성 실패*\n이유: {_slack_escape(reason)}"
