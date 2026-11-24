"""지수·환율·금리. AI를 거치지 않고 데이터에서 직접 가져온다."""
import json
from datetime import datetime, timezone
from urllib.parse import quote

from briefing.collect import FetchText, http_get_text
from briefing.models import MarketQuote, MarketSpec

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"


def parse_chart(text: str, spec: MarketSpec) -> MarketQuote:
    try:
        result = json.loads(text)["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
        raise ValueError(f"{spec.label}: 시세 응답 형식이 다릅니다") from e
    points = [(t, c) for t, c in zip(timestamps, closes) if c is not None]
    if len(points) < 2:
        raise ValueError(f"{spec.label}: 종가가 2개 미만입니다")
    (_, prev), (last_time, last) = points[-2], points[-1]
    return MarketQuote(
        label=spec.label,
        unit=spec.unit,
        value=last,
        change_pct=(last - prev) / prev * 100,
        date=datetime.fromtimestamp(last_time, tz=timezone.utc).strftime("%Y-%m-%d"),
    )


def fetch_markets(specs: list[MarketSpec], fetch_text: FetchText = http_get_text) -> list[MarketQuote] | None:
    """하나라도 실패하면 None. 일부만 보여 주면 헷갈리므로 시장 줄 전체를 뺀다."""
    try:
        return [parse_chart(fetch_text(CHART_URL.format(symbol=quote(s.symbol, safe=""))), s) for s in specs]
    except Exception:
        return None
