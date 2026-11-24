from dataclasses import replace

from briefing.config import load_settings
from briefing.models import Article, NewsEvent, Outlet, RankedItem
from briefing.select import Passed, apply_caps, pass_filter

S = load_settings()
OUTLETS = [
    Outlet(id=i, name=i, region=r, feeds=["u"], max_items=5)
    for i, r in [("yna", "KR"), ("hankyung", "KR"), ("mk", "KR"), ("us1", "US"), ("us2", "US"),
                 ("us3", "US"), ("uk1", "UK"), ("uk2", "UK"), ("cn1", "CN"), ("jp1", "JP")]
]


class World:
    """기사와 사건을 함께 쌓아 주는 테스트 도우미."""

    def __init__(self):
        self.articles = []
        self.events = []

    def ev(self, outlet_ids, **overrides):
        ids = []
        for oid in outlet_ids:
            aid = f"a{len(self.articles) + 1}"
            self.articles.append(Article(aid, oid, "t", "", "u", None))
            ids.append(aid)
        e = NewsEvent(key=f"e{len(self.events) + 1}", label="x", article_ids=ids, category="econ_it",
                      region="US", domestic_kr=False, tier="medium", continuity="new")
        e = replace(e, **overrides)
        self.events.append(e)
        return e

    def passed(self):
        return pass_filter(self.events, self.articles, OUTLETS, S)


def general(**kw):
    return dict(category="general", tier=None, **kw)


def keys(events):
    return [e.key for e in events]


def ranks(events):
    return [RankedItem(e.key, i + 1, "t", "w") for i, e in enumerate(events)]


# --- pass_filter ---

def test_econ_medium_passes_with_a_single_outlet():
    w = World()
    w.ev(["us1"], tier="medium")
    assert keys(w.passed().econ) == ["e1"] and w.passed().general == []


def test_econ_routine_and_none_tier_are_dropped():
    w = World()
    w.ev(["us1", "uk1", "yna"], tier="routine")
    w.ev(["us1"], tier=None)
    assert w.passed().econ == []


def test_ongoing_no_progress_is_dropped_even_when_major():
    w = World()
    w.ev(["us1", "uk1"], tier="major", continuity="ongoing_no_progress")
    assert w.passed().econ == []


def test_ongoing_progress_passes_like_a_new_event():
    w = World()
    w.ev(["us1"], tier="major", continuity="ongoing_progress")
    assert keys(w.passed().econ) == ["e1"]


def test_general_world_3_outlets_in_2_regions_passes():
    w = World()
    w.ev(["us1", "us2", "uk1"], **general())
    assert keys(w.passed().general) == ["e1"] and w.passed().econ == []


def test_general_world_3_outlets_in_1_region_fails():
    w = World()
    w.ev(["us1", "us2", "us3"], **general())
    assert w.passed().general == []


def test_general_world_2_outlets_in_2_regions_fails():
    w = World()
    w.ev(["us1", "uk1"], **general())
    assert w.passed().general == []


def test_general_domestic_kr_2_korean_outlets_passes():
    w = World()
    w.ev(["yna", "mk"], **general(domestic_kr=True, region="KR"))
    assert keys(w.passed().general) == ["e1"]


def test_general_domestic_kr_1_korean_plus_2_foreign_fails():
    w = World()
    w.ev(["yna", "us1", "uk1"], **general(domestic_kr=True, region="KR"))
    assert w.passed().general == []


def test_two_articles_from_one_outlet_count_once():
    w = World()
    w.ev(["yna", "yna"], **general(domestic_kr=True, region="KR"))
    assert w.passed().general == []


def test_unknown_article_ids_are_ignored():
    w = World()
    e = w.ev(["yna"], **general(domestic_kr=True, region="KR"))
    e.article_ids.extend(["a998", "a999"])
    assert w.passed().general == []


# --- apply_caps ---

def test_econ_caps_at_10_in_rank_order():
    w = World()
    evs = [w.ev(["us1"]) for _ in range(14)]
    out = apply_caps(Passed(evs, []), ranks(evs), S)
    assert keys(out.econ) == [f"e{i}" for i in range(1, 11)]


def test_econ_guaranteed_regions_get_a_slot_even_when_ranked_last():
    w = World()
    us = [w.ev(["us1"]) for _ in range(12)]
    cn = w.ev(["cn1"], region="CN")
    jp = [w.ev(["jp1"], region="JP") for _ in range(2)]
    evs = us + [cn] + jp
    out = apply_caps(Passed(evs, []), ranks(evs), S)
    assert keys(out.econ) == [f"e{i}" for i in range(1, 9)] + ["e13", "e14"]


def test_econ_no_padding_when_a_guaranteed_region_is_absent():
    w = World()
    evs = [w.ev(["us1"]) for _ in range(3)]
    out = apply_caps(Passed(evs, []), ranks(evs), S)
    assert keys(out.econ) == ["e1", "e2", "e3"]


def test_econ_guaranteed_region_already_in_top_is_not_doubled():
    w = World()
    evs = [w.ev(["us1"])]
    evs.append(w.ev(["cn1"], region="CN"))  # 2위
    evs += [w.ev(["us1"]) for _ in range(10)]  # 3~12위
    evs.append(w.ev(["cn1"], region="CN"))  # 13위
    out = apply_caps(Passed(evs, []), ranks(evs), S)
    assert keys(out.econ) == [f"e{i}" for i in range(1, 11)]


def test_econ_result_follows_rank_not_input_order():
    w = World()
    evs = [w.ev(["us1"]) for _ in range(3)]
    ranked = [RankedItem("e3", 1, "t", "w"), RankedItem("e1", 2, "t", "w"), RankedItem("e2", 3, "t", "w")]
    assert keys(apply_caps(Passed(evs, []), ranked, S).econ) == ["e3", "e1", "e2"]


def test_general_caps_at_3():
    w = World()
    evs = [w.ev(["us1", "us2", "uk1"], **general()) for _ in range(5)]
    out = apply_caps(Passed([], evs), ranks(evs), S)
    assert keys(out.general) == ["e1", "e2", "e3"] and out.econ == []


def test_events_missing_from_ranked_go_last():
    w = World()
    evs = [w.ev(["us1"]) for _ in range(3)]
    out = apply_caps(Passed(evs, []), [RankedItem("e3", 1, "t", "w")], S)
    assert keys(out.econ) == ["e3", "e1", "e2"]
