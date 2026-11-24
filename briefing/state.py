"""보낸 기록(최근 며칠)과 날짜별 보관 파일."""
import json
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

from briefing.models import BriefingItem, SentRecord


def _read(path: str) -> list[SentRecord]:
    """파일이 없거나 깨져 있으면 빈 목록. 기록이 없다고 브리핑이 멈추면 안 된다."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return [SentRecord(r["date"], r["title_ko"], r["why_ko"]) for r in raw]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def _recent(records: list[SentRecord], today: str, history_days: int) -> list[SentRecord]:
    """오늘 이전이면서 history_days일 안쪽인 기록. 오늘 것은 같은 날 재실행에 대비해 뺀다."""
    oldest = (date.fromisoformat(today) - timedelta(days=history_days)).isoformat()
    return [r for r in records if oldest <= r.date < today]


def load_history(path: str, today: str, history_days: int) -> list[SentRecord]:
    return _recent(_read(path), today, history_days)


def save_history(path: str, today: str, items: list[BriefingItem], history_days: int) -> None:
    records = _recent(_read(path), today, history_days)
    records += [SentRecord(today, i.title_ko, i.why_ko) for i in items]
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2) + "\n"
    target.write_text(text, encoding="utf-8", newline="\n")


def save_archive(directory: str, today: str, markdown: str) -> None:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{today}.md").write_text(markdown, encoding="utf-8", newline="\n")
