import pytest

from briefing.ai import AiError
from briefing.cluster import cluster_events
from briefing.models import Article, Outlet, SentRecord

OUTLETS = [Outlet(id="reuters", name="로이터", region="UK", feeds=["u"], max_items=5),
           Outlet(id="yna", name="연합뉴스", region="KR", feeds=["u"], max_items=5)]
ARTICLES = [
    Article("a1", "reuters", "Fed cuts rates", "The Fed cut rates by 25bp.", "https://r/1", None),
    Article("a2", "yna", "미 연준 금리 인하", "", "https://y/2", None),
    Article("a3", "yna", "국회 예산안 통과", "", "https://y/3", None),
]
HISTORY = [SentRecord("2026-11-24", "미·중 관세 협상 재개", "수출주 영향")]


def event(ids, **kw):
    base = dict(label="x", article_ids=ids, category="econ_it", region="US", domestic_kr=False,
                tier="major", continuity="new")
    return {**base, **kw}


class FakeAsk:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def __call__(self, *, system, user, schema):
        self.calls.append(dict(system=system, user=user, schema=schema))
        if self.error:
            raise self.error
        return self.response


def run(events, articles=ARTICLES, history=HISTORY):
    ask = FakeAsk({"events": events})
    return cluster_events(articles, OUTLETS, history, ask), ask


def test_maps_response_to_events_with_keys_e1_to_eN():
    out, _ = run([event(["a1", "a2"], label="Fed cut"),
                  event(["a3"], category="general", region="KR", domestic_kr=True, tier=None)])
    assert [e.key for e in out] == ["e1", "e2"]
    first = out[0]
    assert (first.label, first.article_ids, first.category, first.region, first.domestic_kr, first.tier,
            first.continuity) == ("Fed cut", ["a1", "a2"], "econ_it", "US", False, "major", "new")
    assert out[1].domestic_kr is True and out[1].tier is None


def test_unknown_article_ids_are_dropped():
    out, _ = run([event(["a1", "a999"])])
    assert out[0].article_ids == ["a1"]


def test_article_claimed_twice_stays_in_the_first_event():
    out, _ = run([event(["a1", "a2"]), event(["a2", "a3"])])
    assert [e.article_ids for e in out] == [["a1", "a2"], ["a3"]]


def test_event_left_with_no_articles_is_dropped_and_keys_stay_dense():
    out, _ = run([event(["a999"]), event(["a1", "a1"]), event(["a1"]), event(["a3"])])
    assert [(e.key, e.article_ids) for e in out] == [("e1", ["a1"]), ("e2", ["a3"])]


def test_general_event_gets_tier_none_even_if_model_set_one():
    out, _ = run([event(["a3"], category="general", tier="major")])
    assert out[0].tier is None


def test_prompt_lists_every_article_with_outlet_name_and_the_history():
    _, ask = run([event(["a1"])])
    user = ask.calls[0]["user"]
    assert "a1 | 로이터 | Fed cuts rates | The Fed cut rates by 25bp." in user
    assert "a2 | 연합뉴스 | 미 연준 금리 인하" in user and "a3 | 연합뉴스 | 국회 예산안 통과" in user
    assert "2026-11-24 | 미·중 관세 협상 재개 | 수출주 영향" in user


def test_empty_history_is_stated():
    _, ask = run([event(["a1"])], history=[])
    assert "없음" in ask.calls[0]["user"]


def test_system_prompt_carries_the_spec_rules():
    _, ask = run([event(["a1"])])
    system = ask.calls[0]["system"]
    for phrase in ["연예", "스포츠", "칼럼", "기준금리 결정", "인수합병", "증권사 전망", "ongoing_no_progress"]:
        assert phrase in system


def test_no_articles_means_no_ai_call():
    out, ask = run([], articles=[])
    assert out == [] and ask.calls == []


def test_malformed_response_raises_ai_error():
    ask = FakeAsk({"events": [{"label": "x"}]})
    with pytest.raises(AiError):
        cluster_events(ARTICLES, OUTLETS, HISTORY, ask)


def test_error_from_ask_propagates():
    with pytest.raises(AiError, match="down"):
        cluster_events(ARTICLES, OUTLETS, HISTORY, FakeAsk(error=AiError("down")))
