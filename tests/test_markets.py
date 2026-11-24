import json
from pathlib import Path

import pytest

from briefing.markets import fetch_markets, parse_chart
from briefing.models import MarketSpec

FIX = Path("tests/fixtures/yahoo-chart.json").read_text(encoding="utf-8")
NASDAQ = MarketSpec(label="나스닥", symbol="^IXIC", unit="index")
KOSPI = MarketSpec(label="코스피", symbol="^KS11", unit="index")


def test_uses_the_last_two_non_null_closes():
    # close: [100, 110, null, 121], 마지막 timestamp 1795554000 = 2026-11-24T21:00:00Z
    q = parse_chart(FIX, NASDAQ)
    assert (q.label, q.unit, q.value, q.date) == ("나스닥", "index", 121.0, "2026-11-24")
    assert q.change_pct == pytest.approx(10.0)


def test_fewer_than_two_closes_raises():
    data = json.loads(FIX)
    data["chart"]["result"][0]["indicators"]["quote"][0]["close"] = [None, None, None, 121.0]
    with pytest.raises(ValueError):
        parse_chart(json.dumps(data), NASDAQ)


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
