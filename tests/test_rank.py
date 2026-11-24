import pytest

from briefing.ai import AiError
from briefing.models import Article, NewsEvent, RankedItem
from briefing.rank import rank_events

ARTICLES = [
    Article("a1", "reuters", "Fed cuts rates", "The Fed cut rates by 25bp.", "https://r/1", None),
    Article("a2", "yna", "미 연준 금리 인하", "", "https://y/2", None),
    Article("a3", "yna", "국회 예산안 통과", "", "https://y/3", None),
]
EVENTS = [
    NewsEvent("e1", "Fed cut", ["a1", "a2"], "econ_it", "US", False, "major", "new"),
    NewsEvent("e2", "예산안", ["a3"], "general", "KR", True, None, "new"),
]


class FakeAsk:
    def __init__(self, response):
        self.response, self.calls = response, []

    def __call__(self, *, system, user, schema):
        self.calls.append(dict(system=system, user=user, schema=schema))
        return self.response


def item(key, rank=1, title="제목", why="이유"):
    return {"event_key": key, "rank": rank, "title_ko": title, "why_ko": why}


def test_maps_items_to_ranked_items():
    ask = FakeAsk({"items": [item("e1", 1, "연준 금리 인하", "대출금리 하락"), item("e2", 1)]})
    assert rank_events(EVENTS, ARTICLES, ask) == [
        RankedItem("e1", 1, "연준 금리 인하", "대출금리 하락"), RankedItem("e2", 1, "제목", "이유"),
    ]


def test_no_events_means_no_ai_call():
    ask = FakeAsk({"items": []})
    assert rank_events([], ARTICLES, ask) == [] and ask.calls == []


def test_unknown_event_key_dropped_and_first_duplicate_kept():
    ask = FakeAsk({"items": [item("e1", 1, "첫째"), item("e9", 2), item("e1", 3, "둘째")]})
    assert rank_events(EVENTS, ARTICLES, ask) == [RankedItem("e1", 1, "첫째", "이유")]


def test_prompt_shows_each_event_with_its_articles():
    ask = FakeAsk({"items": []})
    rank_events(EVENTS, ARTICLES, ask)
    user = ask.calls[0]["user"]
    assert "e1 | econ_it | US | major" in user and "e2 | general | KR" in user
    assert "Fed cuts rates — The Fed cut rates by 25bp." in user and "국회 예산안 통과" in user


def test_system_prompt_forbids_advice_and_invented_numbers():
    ask = FakeAsk({"items": []})
    rank_events(EVENTS, ARTICLES, ask)
    system = ask.calls[0]["system"]
    assert "투자 조언" in system and "없는 숫자" in system


def test_malformed_response_raises_ai_error():
    with pytest.raises(AiError):
        rank_events(EVENTS, ARTICLES, FakeAsk({"items": [{"event_key": "e1"}]}))
