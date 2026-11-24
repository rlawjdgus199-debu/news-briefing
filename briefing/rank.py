"""AI 2단계: 통과한 사건의 순위를 매기고 한국어 제목과 "왜 중요한가"를 쓴다."""
from pydantic import BaseModel, ValidationError

from briefing.ai import AiError, AskJson
from briefing.models import Article, NewsEvent, RankedItem

MAX_ARTICLES_PER_EVENT = 5

SYSTEM = """당신은 한국 개인 투자자를 위한 아침 뉴스 브리핑의 편집자입니다.
독자는 주식 투자를 하고 있고, 경제가 어떻게 돌아가는지 이해하고 싶어 합니다.
이미 골라진 사건 목록을 받아 순위를 매기고, 사건마다 한국어 제목과 "그래서 왜 중요한가"를 씁니다.
입력에 있는 모든 사건에 대해 항목을 하나씩 돌려줍니다.

rank
- 기준: 시장·금리·환율·기업 실적에 주는 영향, 영향받는 사람의 수, 일주일 뒤에도 의미가 있는가.
- econ_it 사건끼리 1위부터, general 사건끼리 1위부터 따로 매깁니다.

title_ko
- 한국어 한 줄 제목, 40자 안팎. 외국어 기사는 번역합니다.

why_ko
- "그래서 왜 중요한가"를 한두 문장, 80자 안팎으로 씁니다.
- 이 뉴스가 시장이나 경제에 어떻게 이어지는지(예: 금리 인하 → 대출이자 하락 → 성장주에 유리) 연결고리를 보여 줍니다.

지킬 것
- 주어진 제목과 요약에 없는 숫자나 사실은 쓰지 않습니다. 확실하지 않으면 숫자를 빼고 씁니다.
- "사라", "팔아라", 매수·매도 추천 같은 투자 조언은 쓰지 않습니다. 영향과 맥락만 설명합니다."""

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "event_key": {"type": "string"},
                    "rank": {"type": "integer"},
                    "title_ko": {"type": "string"},
                    "why_ko": {"type": "string"},
                },
                "required": ["event_key", "rank", "title_ko", "why_ko"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


class _ItemOut(BaseModel):
    event_key: str
    rank: int
    title_ko: str
    why_ko: str


class _RankOut(BaseModel):
    items: list[_ItemOut]


def _user_text(events: list[NewsEvent], articles: list[Article]) -> str:
    by_id = {a.id: a for a in articles}
    lines = ["사건 목록 (번호 | 분류 | 지역 | 단계, 그 아래는 관련 기사)"]
    for e in events:
        head = [e.key, e.category, e.region] + ([e.tier] if e.tier else [])
        lines += ["", " | ".join(head)]
        for i in e.article_ids[:MAX_ARTICLES_PER_EVENT]:
            a = by_id.get(i)
            if a is not None:
                lines.append(f"- {a.title} — {a.summary}" if a.summary else f"- {a.title}")
    return "\n".join(lines)


def rank_events(events: list[NewsEvent], articles: list[Article], ask: AskJson) -> list[RankedItem]:
    if not events:
        return []
    raw = ask(system=SYSTEM, user=_user_text(events, articles), schema=SCHEMA)
    try:
        parsed = _RankOut.model_validate(raw)
    except ValidationError as e:
        raise AiError(f"순위 응답 형식이 다릅니다 (오류 {e.error_count()}건)") from e
    known = {e.key for e in events}
    seen: set[str] = set()
    ranked: list[RankedItem] = []
    for item in parsed.items:
        if item.event_key in known and item.event_key not in seen:
            seen.add(item.event_key)
            ranked.append(RankedItem(item.event_key, item.rank, item.title_ko, item.why_ko))
    return ranked
