from dataclasses import replace

from briefing.models import BriefingItem, MarketQuote
from briefing.render import Briefing, render_failure, render_markdown, render_slack

MARKETS = [
    MarketQuote("코스피", "index", 2654.12, 0.41, "2026-11-24"),
    MarketQuote("코스닥", "index", 865.3, -0.12, "2026-11-24"),
    MarketQuote("나스닥", "index", 23742.678, -1.2, "2026-11-24"),
    MarketQuote("S&P500", "index", 7205.03, -0.6, "2026-11-24"),
    MarketQuote("원/달러", "krw", 1343.48, 0.2, "2026-11-24"),
    MarketQuote("미 10년물", "pct", 4.898, 1.1, "2026-11-24"),
]
NVIDIA = BriefingItem(
    title_ko="엔비디아 실적 예상 상회, 시간외 주가는 하락",
    why_ko="기대치가 이미 높았다는 뜻. 국내 반도체주 개장 영향 주목.",
    region="US", ongoing=False, outlet_names=["블룸버그", "CNBC", "한국경제"], url="https://example.com/a",
)
TARIFF = BriefingItem(
    title_ko="미·중 관세 협상 2차 회담 일정 확정",
    why_ko="회담이 실제로 열린다는 신호. 관세 인하 기대가 수출주에 반영될 수 있음.",
    region="CN", ongoing=True, outlet_names=["로이터"], url="https://example.com/b",
)
FULL = Briefing(date="2026-11-25", markets=MARKETS, econ=[NVIDIA, TARIFF], general=[],
                failed_outlet_names=["차이신", "NHK 월드"])

EXPECTED = """📊 *11/25(수) 아침 브리핑*
코스피 2,654.12 (+0.4%) | 코스닥 865.30 (-0.1%) | 나스닥 23,742.68 (-1.2%) | S&amp;P500 7,205.03 (-0.6%)
원/달러 1,343.5원 (+0.2%) | 미 10년물 4.90%

💰 *경제·IT (2건)*
• *엔비디아 실적 예상 상회, 시간외 주가는 하락*  [미국]
  → 기대치가 이미 높았다는 뜻. 국내 반도체주 개장 영향 주목.
  블룸버그 · CNBC · 한국경제  <https://example.com/a|원문>
• *미·중 관세 협상 2차 회담 일정 확정* (이어지는 소식)  [중국]
  → 회담이 실제로 열린다는 신호. 관세 인하 기대가 수출주에 반영될 수 있음.
  로이터  <https://example.com/b|원문>

🌍 *그 외 큰 뉴스 (0건)*
오늘은 큰 뉴스 없음

수집 실패: 차이신, NHK 월드"""


def test_full_briefing_matches_expected_text_exactly():
    assert render_slack(FULL) == EXPECTED


def test_empty_sections_show_0_and_no_big_news():
    text = render_slack(replace(FULL, econ=[], general=[]))
    assert "💰 *경제·IT (0건)*\n오늘은 큰 뉴스 없음" in text
    assert "🌍 *그 외 큰 뉴스 (0건)*\n오늘은 큰 뉴스 없음" in text


def test_general_items_are_listed_in_their_section():
    text = render_slack(replace(FULL, general=[replace(NVIDIA, region="EU")]))
    assert "🌍 *그 외 큰 뉴스 (1건)*\n• *엔비디아 실적 예상 상회, 시간외 주가는 하락*  [유럽]" in text


def test_markets_none_omits_market_lines():
    text = render_slack(replace(FULL, markets=None))
    assert text.startswith("📊 *11/25(수) 아침 브리핑*\n\n💰 *경제·IT (2건)*")
    assert "코스피" not in text


def test_stale_market_date_adds_close_date():
    stale = [replace(q, date="2026-11-27") for q in MARKETS]
    lines = render_slack(replace(FULL, date="2026-11-29", markets=stale)).split("\n")
    assert lines[0] == "📊 *11/29(일) 아침 브리핑*"
    assert lines[2].endswith("미 10년물 4.90% (11/27 종가)")


def test_previous_day_close_is_not_marked_stale():
    assert "종가" not in render_slack(FULL)


def test_escapes_special_characters():
    item = replace(NVIDIA, title_ko="AT&T <속보> 합병", url="https://x.com/a|b>c")
    text = render_slack(replace(FULL, econ=[item]))
    assert "*AT&amp;T &lt;속보&gt; 합병*" in text
    assert "<https://x.com/a%7Cb%3Ec|원문>" in text


def test_more_than_4_outlets_shows_n_more():
    item = replace(NVIDIA, outlet_names=["가", "나", "다", "라", "마", "바"])
    assert "  가 · 나 · 다 · 라 외 2곳  <" in render_slack(replace(FULL, econ=[item]))


def test_no_failed_outlets_omits_the_line():
    text = render_slack(replace(FULL, failed_outlet_names=[]))
    assert "수집 실패" not in text and text.endswith("오늘은 큰 뉴스 없음")


def test_render_failure_has_date_and_reason():
    assert render_failure("2026-11-25", "매체 18곳 중 10곳 수집 실패") == (
        "⚠️ *11/25(수) 브리핑 생성 실패*\n이유: 매체 18곳 중 10곳 수집 실패"
    )


def test_markdown_has_title_and_plain_links():
    item = replace(NVIDIA, title_ko="AT&T 합병")
    md = render_markdown(replace(FULL, econ=[item, TARIFF]))
    assert md.startswith("# 2026-11-25 아침 브리핑\n")
    assert "- **AT&T 합병** [미국]" in md and "&amp;" not in md
    assert "[원문](https://example.com/a)" in md
    assert "(이어지는 소식)" in md and "수집 실패: 차이신, NHK 월드" in md
