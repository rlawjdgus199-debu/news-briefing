import json
from datetime import datetime, timezone

import pytest

from briefing.ai import AiError
from briefing.collect import CollectResult
from briefing.config import load_settings
from briefing.models import Article, MarketQuote, Outlet
from briefing.run import Deps, main, run

NOW = datetime(2026, 11, 24, 22, 5, tzinfo=timezone.utc)  # 한국 시간 2026-11-25 07:05
OUTLETS = [
    Outlet(id="reuters", name="로이터", region="UK", feeds=["u"], max_items=5, google_news=True),
    Outlet(id="us1", name="블룸버그", region="US", feeds=["u"], max_items=5),
    Outlet(id="yna", name="연합뉴스", region="KR", feeds=["u"], max_items=5),
    Outlet(id="cn1", name="SCMP", region="CN", feeds=["u"], max_items=5),
]
ARTICLES = [
    Article("a1", "reuters", "Fed cuts rates", "", "https://news.google.com/x", None),
    Article("a2", "us1", "Fed cuts rates again", "The Fed cut.", "https://us1/fed", None),
    Article("a3", "yna", "국회 예산안 통과", "", "https://yna/budget", None),
    Article("a4", "cn1", "China tariff talks set", "", "https://cn1/talks", None),
]
MARKETS = [MarketQuote("코스피", "index", 2654.12, 0.4, "2026-11-24")]


def ev(ids, **kw):
    base = dict(label="x", article_ids=ids, category="econ_it", region="US", domestic_kr=False,
                tier="major", continuity="new")
    return {**base, **kw}


EVENTS = [
    ev(["a1", "a2"]),
    ev(["a4"], region="CN", tier="medium", continuity="ongoing_progress"),
    ev(["a3"], category="general", region="KR", domestic_kr=True, tier=None),  # 한국 매체 1곳뿐 → 탈락
]
RANKED = [
    {"event_key": "e1", "rank": 1, "title_ko": "연준 금리 인하", "why_ko": "대출금리 하락 기대."},
    {"event_key": "e2", "rank": 2, "title_ko": "미·중 관세 회담 확정", "why_ko": "수출주에 영향."},
]


class Harness:
    def __init__(self, tmp_path, *, events=EVENTS, ranked=RANKED, failed=(), markets=MARKETS,
                 cluster_error=None, send_error=None, dry_run=False):
        self.sent, self.logs, self.ask_calls = [], [], []
        self.events, self.ranked, self.cluster_error, self.send_error = events, ranked, cluster_error, send_error
        self.state_path = tmp_path / "state" / "sent.json"
        self.archive_dir = tmp_path / "archive"
        self.deps = Deps(
            now=NOW, outlets=OUTLETS, settings=load_settings(),
            collect=lambda outlets, settings, now: CollectResult(list(ARTICLES), list(failed)),
            ask=self.ask, fetch_markets=lambda specs: markets, send=self.send,
            state_path=str(self.state_path), archive_dir=str(self.archive_dir),
            dry_run=dry_run, log=self.logs.append,
        )

    def ask(self, *, system, user, schema):
        self.ask_calls.append(user)
        if "events" in schema["properties"]:
            if self.cluster_error:
                raise self.cluster_error
            return {"events": self.events}
        return {"items": self.ranked}

    def send(self, text):
        if self.send_error:
            raise self.send_error
        self.sent.append(text)

    def go(self):
        return run(self.deps)


def test_happy_path_sends_once_and_saves(tmp_path):
    h = Harness(tmp_path)
    assert h.go() == "sent"
    assert len(h.sent) == 1
    text = h.sent[0]
    assert "💰 *경제·IT (2건)*" in text and "🌍 *그 외 큰 뉴스 (0건)*\n오늘은 큰 뉴스 없음" in text
    assert "• *연준 금리 인하*  [미국]" in text
    assert "• *미·중 관세 회담 확정* (이어지는 소식)  [중국]" in text
    assert "  로이터 · 블룸버그  <https://us1/fed|원문>" in text
    assert "코스피 2,654.12 (+0.4%)" in text
    archive = (h.archive_dir / "2026-11-25.md").read_text(encoding="utf-8")
    assert archive.startswith("# 2026-11-25 아침 브리핑") and "연준 금리 인하" in archive
    saved = json.loads(h.state_path.read_text(encoding="utf-8"))
    assert [(r["date"], r["title_ko"]) for r in saved] == [
        ("2026-11-25", "연준 금리 인하"), ("2026-11-25", "미·중 관세 회담 확정"),
    ]


def test_uses_the_korean_date(tmp_path):
    h = Harness(tmp_path)
    h.go()
    assert h.sent[0].startswith("📊 *11/25(수) 아침 브리핑*")


def test_failed_outlets_are_named_at_the_bottom(tmp_path):
    h = Harness(tmp_path, failed=["cn1"])
    assert h.go() == "sent"
    assert h.sent[0].endswith("수집 실패: SCMP")


def test_half_of_outlets_failed_sends_failure_notice(tmp_path):
    h = Harness(tmp_path, failed=["cn1", "yna"])
    assert h.go() == "failed"
    assert h.sent == ["⚠️ *11/25(수) 브리핑 생성 실패*\n이유: 매체 4곳 중 2곳 수집 실패"]
    assert h.ask_calls == []
    assert not h.state_path.exists() and not h.archive_dir.exists()


def test_clustering_error_sends_failure_notice_with_reason(tmp_path):
    h = Harness(tmp_path, cluster_error=AiError("AI 호출 실패 (종료 코드 1): Invalid API key"))
    assert h.go() == "failed"
    assert len(h.sent) == 1 and "브리핑 생성 실패" in h.sent[0] and "Invalid API key" in h.sent[0]
    assert not h.state_path.exists()


def test_unexpected_error_names_its_type_in_the_notice(tmp_path):
    h = Harness(tmp_path, cluster_error=KeyError("oops"))
    assert h.go() == "failed"
    assert "KeyError" in h.sent[0]


def test_nothing_passes_still_sends_with_no_big_news(tmp_path):
    h = Harness(tmp_path, events=[ev(["a1"], tier="routine")], ranked=[])
    assert h.go() == "sent"
    assert "💰 *경제·IT (0건)*\n오늘은 큰 뉴스 없음" in h.sent[0]
    assert len(h.ask_calls) == 1  # 통과한 사건이 없으면 순위 단계는 부르지 않는다
    assert json.loads(h.state_path.read_text(encoding="utf-8")) == []


def test_markets_none_sends_without_market_lines(tmp_path):
    h = Harness(tmp_path, markets=None)
    assert h.go() == "sent"
    assert "코스피" not in h.sent[0] and "연준 금리 인하" in h.sent[0]


def test_dry_run_sends_nothing_and_writes_nothing(tmp_path):
    h = Harness(tmp_path, dry_run=True)
    assert h.go() == "sent"
    assert h.sent == []
    assert any("연준 금리 인하" in line for line in h.logs)
    assert not h.state_path.exists() and not h.archive_dir.exists()


def test_dry_run_failure_is_logged_not_sent(tmp_path):
    h = Harness(tmp_path, dry_run=True, failed=["cn1", "yna"])
    assert h.go() == "failed"
    assert h.sent == [] and any("브리핑 생성 실패" in line for line in h.logs)


def test_event_without_ranked_item_is_left_out(tmp_path):
    h = Harness(tmp_path, ranked=RANKED[:1])
    h.go()
    assert "💰 *경제·IT (1건)*" in h.sent[0] and "관세" not in h.sent[0]


def test_google_news_url_is_used_when_it_is_the_only_one(tmp_path):
    h = Harness(tmp_path, events=[ev(["a1"])], ranked=RANKED[:1])
    h.go()
    assert "<https://news.google.com/x|원문>" in h.sent[0]


def test_second_run_same_day_still_sends_the_same_items(tmp_path):
    first = Harness(tmp_path)
    first.go()
    second = Harness(tmp_path)
    assert second.go() == "sent"
    assert "연준 금리 인하" not in second.ask_calls[0]  # 오늘 보낸 것은 "이미 보낸 소식"에 넣지 않는다
    assert "💰 *경제·IT (2건)*" in second.sent[0]
    assert len(json.loads(second.state_path.read_text(encoding="utf-8"))) == 2


def test_send_failure_on_the_briefing_propagates(tmp_path):
    h = Harness(tmp_path, send_error=RuntimeError("슬랙 전송 실패: HTTP 500"))
    with pytest.raises(RuntimeError, match="HTTP 500"):
        h.go()
    assert not h.state_path.exists()


def test_main_without_webhook_returns_1(monkeypatch, capsys):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    assert main([]) == 1
    assert "SLACK_WEBHOOK_URL" in capsys.readouterr().out
