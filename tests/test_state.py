import json

from briefing.models import BriefingItem, SentRecord
from briefing.state import load_history, save_archive, save_history

TODAY = "2026-11-25"


def item(title):
    return BriefingItem(title_ko=title, why_ko=f"{title} 이유", region="US", ongoing=False,
                        outlet_names=["로이터"], url="https://example.com")


def write(path, dates):
    path.write_text(json.dumps([{"date": d, "title_ko": d, "why_ko": "w"} for d in dates]), encoding="utf-8")


def test_missing_file_gives_empty_history(tmp_path):
    assert load_history(str(tmp_path / "none.json"), TODAY, 7) == []


def test_corrupt_file_gives_empty_history(tmp_path):
    p = tmp_path / "sent.json"
    p.write_text("{not json", encoding="utf-8")
    assert load_history(str(p), TODAY, 7) == []


def test_history_drops_old_entries_and_todays(tmp_path):
    p = tmp_path / "sent.json"
    write(p, ["2026-11-17", "2026-11-18", "2026-11-24", "2026-11-25"])  # 8일 전, 7일 전, 어제, 오늘
    assert load_history(str(p), TODAY, 7) == [
        SentRecord("2026-11-18", "2026-11-18", "w"), SentRecord("2026-11-24", "2026-11-24", "w"),
    ]


def test_second_run_same_day_replaces_todays_entries(tmp_path):
    p = str(tmp_path / "state" / "sent.json")
    save_history(p, TODAY, [item("첫 실행")], 7)
    save_history(p, TODAY, [item("둘째 실행 가"), item("둘째 실행 나")], 7)
    saved = json.loads(open(p, encoding="utf-8").read())
    assert [r["title_ko"] for r in saved] == ["둘째 실행 가", "둘째 실행 나"]
    assert saved[0] == {"date": TODAY, "title_ko": "둘째 실행 가", "why_ko": "둘째 실행 가 이유"}


def test_save_prunes_old_entries_and_keeps_recent(tmp_path):
    p = tmp_path / "sent.json"
    write(p, ["2026-11-17", "2026-11-24"])
    save_history(str(p), TODAY, [item("오늘")], 7)
    assert [r["date"] for r in json.loads(p.read_text(encoding="utf-8"))] == ["2026-11-24", TODAY]


def test_korean_text_is_stored_readable(tmp_path):
    p = tmp_path / "sent.json"
    save_history(str(p), TODAY, [item("금리 인하")], 7)
    raw = p.read_text(encoding="utf-8")
    assert "금리 인하" in raw and "\\u" not in raw


def test_archive_is_written_and_overwritten(tmp_path):
    d = str(tmp_path / "archive")
    save_archive(d, TODAY, "# 첫 번째\n")
    save_archive(d, TODAY, "# 두 번째\n")
    assert (tmp_path / "archive" / "2026-11-25.md").read_text(encoding="utf-8") == "# 두 번째\n"
