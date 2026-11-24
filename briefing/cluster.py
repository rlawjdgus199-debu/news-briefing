"""AI 1단계: 같은 사건을 다룬 기사를 묶고 분류한다.

통과 여부는 여기서 정하지 않는다. AI는 판단(같은 사건인가, 어떤 분야·단계인가)만 하고,
통과 규칙은 select.py가 계산한다.
"""
from pydantic import BaseModel, ValidationError

from briefing.ai import AiError, AskJson
from briefing.models import Article, Category, Continuity, NewsEvent, Outlet, SentRecord, Tier, TopicRegion

SYSTEM = """당신은 한국 개인 투자자를 위한 아침 뉴스 브리핑의 편집 보조입니다.
여러 매체에서 모은 기사 목록(제목과 요약)을 받아, 같은 사건을 다룬 기사끼리 묶고 각 사건을 분류합니다.
어떤 사건을 브리핑에 실을지는 뒤 단계의 프로그램이 정하므로, 여기서는 묶기와 분류만 정확히 하면 됩니다.

묶기
- 같은 사건을 다룬 기사는 언어와 매체가 달라도 하나의 사건으로 묶습니다.
- 한 기사는 한 사건에만 넣습니다. 혼자인 기사도 사건 하나입니다.
- article_ids에는 입력에 있는 기사 번호(a1, a2, ...)만 씁니다.

응답에서 빼는 것
- 연예, 스포츠 결과, 단순 사건·사고, 정치인 말싸움, 광고성 기사, 의견·칼럼은 응답에 넣지 않습니다.

category
- econ_it: 금리, 환율, 물가, 고용, 무역·관세, 기업 실적, 인수합병, 원자재, 부동산 정책, 반도체, AI, 빅테크, 기술 규제.
- general: 그 밖의 모든 뉴스(정치, 외교, 안보, 사회, 재난 등).

tier (econ_it일 때만. general이면 null)
- major: 시장 전체를 움직이는 뉴스. 예: 기준금리 결정, 환율 급변, 대형 정책·관세.
- medium: 한 산업이나 주요 기업에 영향을 주는 뉴스. 예: 주요 기업 실적, 인수합병, 산업 규제, 대형 투자·감원.
- routine: 영향이 작거나 정보가 적은 뉴스. 예: 소소한 신제품, 증권사 전망·목표가, 단순 시황 기사, 인사.

region
- 매체의 나라가 아니라 사건이 일어난 곳입니다. KR 한국, US 미국, CN 중국(홍콩 포함), JP 일본, EU 유럽(영국 포함), 그 밖은 OTHER.

domestic_kr
- 한국 안에서만 의미가 큰 뉴스면 true, 아니면 false.

continuity ("최근 7일간 이미 보낸 소식" 목록과 비교합니다)
- new: 목록에 없는 사건.
- ongoing_progress: 목록에 있는 사건인데 새로운 결정·발표·숫자·행동이 나왔다.
- ongoing_no_progress: 목록에 있는 사건이고, 같은 내용의 후속 해설이나 반응일 뿐이다.

label
- 사건을 알아볼 수 있는 짧은 이름."""

SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "article_ids": {"type": "array", "items": {"type": "string"}},
                    "category": {"type": "string", "enum": ["econ_it", "general"]},
                    "region": {"type": "string", "enum": ["KR", "US", "CN", "JP", "EU", "OTHER"]},
                    "domestic_kr": {"type": "boolean"},
                    "tier": {"type": ["string", "null"], "enum": ["major", "medium", "routine", None]},
                    "continuity": {"type": "string", "enum": ["new", "ongoing_progress", "ongoing_no_progress"]},
                },
                "required": ["label", "article_ids", "category", "region", "domestic_kr", "tier", "continuity"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["events"],
    "additionalProperties": False,
}


class _EventOut(BaseModel):
    label: str
    article_ids: list[str]
    category: Category
    region: TopicRegion
    domestic_kr: bool
    tier: Tier | None
    continuity: Continuity


class _ClusterOut(BaseModel):
    events: list[_EventOut]


def _user_text(articles: list[Article], outlets: list[Outlet], history: list[SentRecord]) -> str:
    name = {o.id: o.name for o in outlets}
    lines = ["기사 목록 (번호 | 매체 | 제목 | 요약)"]
    lines += [f"{a.id} | {name.get(a.outlet_id, a.outlet_id)} | {a.title} | {a.summary}".rstrip(" |") for a in articles]
    lines += ["", "최근 7일간 이미 보낸 소식 (날짜 | 제목 | 한 줄)"]
    lines += [f"{r.date} | {r.title_ko} | {r.why_ko}" for r in history] or ["없음"]
    return "\n".join(lines)


def cluster_events(articles: list[Article], outlets: list[Outlet], history: list[SentRecord],
                   ask: AskJson) -> list[NewsEvent]:
    if not articles:
        return []
    raw = ask(system=SYSTEM, user=_user_text(articles, outlets, history), schema=SCHEMA)
    try:
        parsed = _ClusterOut.model_validate(raw)
    except ValidationError as e:
        raise AiError(f"묶기 응답 형식이 다릅니다 (오류 {e.error_count()}건)") from e
    known = {a.id for a in articles}
    used: set[str] = set()
    events: list[NewsEvent] = []
    for out in parsed.events:
        # AI가 없는 번호를 주거나 한 기사를 두 사건에 넣어도 죽지 않는다: 버리고 계속한다.
        ids = []
        for i in out.article_ids:
            if i in known and i not in used:
                used.add(i)
                ids.append(i)
        if not ids:
            continue
        events.append(NewsEvent(
            key=f"e{len(events) + 1}", label=out.label, article_ids=ids, category=out.category,
            region=out.region, domestic_kr=out.domestic_kr,
            tier=out.tier if out.category == "econ_it" else None, continuity=out.continuity,
        ))
    return events
