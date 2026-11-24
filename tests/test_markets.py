import json
from pathlib import Path

import pytest

from briefing.markets import fetch_markets, parse_chart
from briefing.models import MarketSpec

FIX = Path("tests/fixtures/yahoo-chart.json").read_text(encoding="utf-8")
NASDAQ = MarketSpec(label="나스닥", symbol="^IXIC", unit="index")
KOSPI = MarketSpec(label="코스피", symbol="^KS11", unit="index")


def variant(closes=None, **meta):
    data = json.loads(FIX)
    result = data["chart"]["result"][0]
    if closes is not None:
        result["indicators"]["quote"][0]["close"] = closes
    result["meta"].update(meta)
    return json.dumps(data)


def test_latest_price_compared_with_the_previous_days_close():
    # 일별 종가 [100, 110, null, 121], 최신가 121 (2026-11-24T21:00Z = 뉴욕 11/24 16:00)
    # 최신가와 같은 날의 종가(121)는 건너뛰고 그 전 마지막 종가(110)와 비교한다.
    q = parse_chart(FIX, NASDAQ)
    assert (q.label, q.unit, q.value, q.date) == ("나스닥", "index", 121.0, "2026-11-24")
    assert q.change_pct == pytest.approx(10.0)


def test_works_when_the_latest_days_close_is_still_missing():
    # 실제로 겪은 경우: 장이 끝났는데 마지막 날 종가 칸이 비어 있고 최신가에만 값이 있다.
    q = parse_chart(variant(closes=[100.0, 110.0, 115.0, None]), NASDAQ)
    assert q.value == 121.0 and q.date == "2026-11-24"
    assert q.change_pct == pytest.approx((121 - 115) / 115 * 100)


def test_date_is_the_exchanges_local_date():
    # 2026-11-24T16:30Z 는 서울에서 11/25 01:30
    q = parse_chart(variant(regularMarketTime=1795537800, gmtoffset=32400), KOSPI)
    assert q.date == "2026-11-25"
    assert q.change_pct == pytest.approx(10.0)  # 서울 날짜로 11/25인 마지막 칸(121)은 건너뛰고 110과 비교


def test_no_earlier_close_raises():
    with pytest.raises(ValueError):
        parse_chart(variant(closes=[None, None, None, 121.0]), NASDAQ)


def test_unexpected_shape_raises_value_error():
    with pytest.raises(ValueError):
        parse_chart('{"chart": {"result": null, "error": {"code": "Not Found"}}}', NASDAQ)


def test_any_failure_returns_none_without_raising():
    def fetch(url):
        if "KS11" in url:
            raise OSError("down")
        return FIX
    assert fetch_markets([NASDAQ, KOSPI], fetch) is None


def test_quotes_come_back_in_settings_order_with_encoded_symbol():
    seen = []

    def fetch(url):
        seen.append(url)
        return FIX
    quotes = fetch_markets([KOSPI, NASDAQ], fetch)
    assert [q.label for q in quotes] == ["코스피", "나스닥"]
    assert seen[0] == "https://query1.finance.yahoo.com/v8/finance/chart/%5EKS11?range=5d&interval=1d"
