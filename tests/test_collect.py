from datetime import datetime, timezone
from pathlib import Path

from briefing.collect import collect, parse_feed
from briefing.config import load_settings
from briefing.models import Outlet

NOW = datetime(2026, 11, 25, 22, tzinfo=timezone.utc)
SETTINGS = load_settings()
FIX = Path("tests/fixtures")


def fx(name):
    return (FIX / name).read_text(encoding="utf-8")


def outlet(**kw):
    base = dict(id="x", name="X", region="US", feeds=["u1"], max_items=25, google_news=False)
    return Outlet(**{**base, **kw})


def serve(mapping):
    def fetch(url):
        if url not in mapping:
            raise OSError("404")
        return mapping[url]
    return fetch


def test_rss_summary_has_no_html_and_is_capped_at_300():
    a = parse_feed(fx("rss.xml"), outlet())[0]
    assert a.title == "Fed cuts rates" and a.url == "https://ex.com/1"
    assert a.summary.startswith("The Fed cut rates.")
    assert "<" not in a.summary and len(a.summary) == 300
    assert a.published_at == datetime(2026, 11, 25, 20, tzinfo=timezone.utc)


def test_atom_entries_are_parsed():
    arts = parse_feed(fx("atom.xml"), outlet())
    assert [(a.title, a.url) for a in arts] == [("Atom one", "https://ex.com/a1"), ("Atom two", "https://ex.com/a2")]
    assert arts[0].published_at == datetime(2026, 11, 25, 17, tzinfo=timezone.utc)


def test_undated_rdf_items_are_kept():
    r = collect([outlet()], SETTINGS, NOW, serve({"u1": fx("rdf-nodate.xml")}))
    assert [a.title for a in r.articles] == ["Rdf one", "Rdf two", "Rdf three"]
    assert all(a.published_at is None for a in r.articles)
    assert r.failed_outlet_ids == []


def test_google_news_strips_outlet_suffix_and_blanks_summary():
    arts = parse_feed(fx("googlenews.xml"), outlet(google_news=True))
    assert arts[0].title == "Fed cuts rates by quarter point" and arts[0].summary == ""
    assert arts[1].title == "Oil - gas prices rise"


def test_old_articles_and_duplicate_urls_are_dropped():
    r = collect([outlet()], SETTINGS, NOW, serve({"u1": fx("rss.xml")}))
    assert [a.title for a in r.articles] == ["Fed cuts rates", "Third", "Dup A"]


def test_same_title_from_two_feeds_is_kept_once():
    twin = fx("atom.xml").replace("https://ex.com/", "https://other.com/")
    r = collect([outlet(feeds=["u1", "u2"])], SETTINGS, NOW, serve({"u1": fx("atom.xml"), "u2": twin}))
    assert [a.url for a in r.articles] == ["https://ex.com/a1", "https://ex.com/a2"]


def test_cap_keeps_the_newest():
    r = collect([outlet(max_items=2)], SETTINGS, NOW, serve({"u1": fx("rss.xml")}))
    assert [a.title for a in r.articles] == ["Fed cuts rates", "Third"]


def test_empty_feed_marks_outlet_failed():
    r = collect([outlet()], SETTINGS, NOW, serve({"u1": fx("empty.xml")}))
    assert r.articles == [] and r.failed_outlet_ids == ["x"]


def test_broken_feed_marks_outlet_failed():
    r = collect([outlet()], SETTINGS, NOW, serve({"u1": fx("broken.xml")}))
    assert r.articles == [] and r.failed_outlet_ids == ["x"]


def test_unreachable_outlet_is_failed_and_others_continue():
    r = collect([outlet(id="dead", feeds=["nope"]), outlet(id="ok")], SETTINGS, NOW, serve({"u1": fx("atom.xml")}))
    assert r.failed_outlet_ids == ["dead"] and {a.outlet_id for a in r.articles} == {"ok"}


def test_one_failing_feed_of_two_is_not_a_failure():
    r = collect([outlet(feeds=["u1", "u2"])], SETTINGS, NOW, serve({"u1": fx("atom.xml")}))
    assert r.failed_outlet_ids == [] and len(r.articles) == 2


def test_ids_run_a1_to_aN_across_outlets():
    r = collect([outlet(id="p"), outlet(id="q", feeds=["u2"])], SETTINGS, NOW,
                serve({"u1": fx("atom.xml"), "u2": fx("rdf-nodate.xml")}))
    assert [a.id for a in r.articles] == ["a1", "a2", "a3", "a4", "a5"]
    assert [a.outlet_id for a in r.articles] == ["p", "p", "q", "q", "q"]
