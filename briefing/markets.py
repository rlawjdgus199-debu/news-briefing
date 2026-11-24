"""지수·환율·금리. AI를 거치지 않고 데이터에서 직접 가져온다."""
import json
from datetime import datetime, timezone
from urllib.parse import quote

from briefing.collect import FetchText, http_get_text
from briefing.models import MarketQuote, MarketSpec

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"


def _local_date(timestamp: int, gmtoffset: int) -> str:
    """거래소 현지 날짜. 서울 장과 뉴욕 장은 같은 시각이라도 날짜가 다르다."""
    return datetime.fromtimestamp(timestamp + gmtoffset, tz=timezone.utc).strftime("%Y-%m-%d")


def parse_chart(text: str, spec: MarketSpec) -> MarketQuote:
    try:
        result = json.loads(text)["chart"]["result"][0]
        meta = result["meta"]
        price, price_time, offset = meta["regularMarketPrice"], meta["regularMarketTime"], meta["gmtoffset"]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
        raise ValueError(f"{spec.label}: 시세 응답 형식이 다릅니다") from e
    # 장이 끝난 직후에는 마지막 날의 종가 칸이 비어 있고 최신가에만 값이 있는 경우가 있다.
    # 그래서 값은 최신가를 쓰고, 그 전날까지의 마지막 종가와 비교한다.
    day = _local_date(price_time, offset)
    earlier = [c for t, c in zip(timestamps, closes) if c is not None and _local_date(t, offset) < day]
    if price is None or not earlier:
        raise ValueError(f"{spec.label}: 비교할 이전 종가가 없습니다")
    return MarketQuote(label=spec.label, unit=spec.unit, value=price,
                       change_pct=(price - earlier[-1]) / earlier[-1] * 100, date=day)


def fetch_markets(specs: list[MarketSpec], fetch_text: FetchText = http_get_text) -> list[MarketQuote] | None:
    """하나라도 실패하면 None. 일부만 보여 주면 헷갈리므로 시장 줄 전체를 뺀다."""
    try:
        return [parse_chart(fetch_text(CHART_URL.format(symbol=quote(s.symbol, safe=""))), s) for s in specs]
    except Exception:
        return None
