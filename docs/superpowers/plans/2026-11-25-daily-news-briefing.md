# 매일 아침 뉴스 브리핑 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매일 한국 시간 7시 30분 전에, 18개 매체의 톱뉴스에서 고른 경제·IT 뉴스와 큰 일반 뉴스를 한국어 브리핑 1건으로 슬랙에 보낸다.

**Architecture:** 하루 한 번 실행되고 끝나는 파이썬 프로그램. 수집 → AI 묶기·분류 → 프로그램이 통과 규칙 계산 → AI 순위·요약 → 프로그램이 지역 보장·자르기 → 시장 요약 → 슬랙 전송 → 보관. GitHub Actions 예약 실행이 매일 돌린다. 통과 여부와 개수 제한은 전부 순수 함수(`briefing/select.py`)가 결정하고, AI는 판단(같은 사건인가, 단계, 순위, 문장)만 한다. AI 호출은 `AskJson`이라는 함수 하나 뒤에 숨겨서, 호출 방식(API 또는 구독 계정)을 바꿔도 나머지 코드는 그대로다.

**Tech Stack:** Python 3.13, `anthropic`(AI 호출), `feedparser`(피드 읽기), `pydantic`(설정·응답 검증), 테스트는 `pytest`. HTTP는 표준 라이브러리 `urllib.request`. 시장 데이터는 Yahoo Finance 차트 주소, 전송은 슬랙 수신 웹훅.

**Spec:** `docs/superpowers/specs/2026-11-25-daily-news-briefing-design.md`

## Global Constraints

- 저장소 루트는 `C:\workspace\news-briefing`. 아래 모든 경로는 이 폴더 기준이다.
- 언어는 파이썬이다 **[사용자 결정]**. 이 PC의 파이썬은 `C:\Users\USER\AppData\Local\Programs\Python\Python313\python.exe`(3.13.17). 가상 환경 `.venv`를 만들어 그 안에서 실행한다. GitHub Actions도 3.13을 쓴다.
- 통과 숫자는 코드에 직접 적지 않고 `config/settings.json`에서 읽는다. 값: 세계 일반 뉴스 매체 3곳 이상·지역 2곳 이상, 한국 국내 일반 뉴스 한국 매체 2곳 이상, 경제·IT 하루 최대 10건, 일반 하루 최대 3건, 지역 보장 1건(중국·일본·유럽), 기사 대상 기간 24시간, 보낸 기록 보관 7일.
- 출력은 전부 한국어. 외국 기사 제목은 번역하고 원문 링크를 1개 단다.
- AI에는 수집한 제목과 요약만 준다. 시장 숫자는 AI를 거치지 않는다.
- "사라/팔아라" 같은 투자 조언 문장은 쓰지 않는다(AI 지시문에 명시).
- 비밀 값은 환경 변수로만 읽는다. 파일에 적지 않고, 로그에 찍지 않는다.
- AI 모델 이름은 `config/settings.json`의 `model`에서 읽는다. 기본값 `claude-haiku-5-5`.
- 테스트는 네트워크와 AI를 실제로 호출하지 않는다. 가짜 함수나 `tests/fixtures/`의 파일을 쓴다.
- 모든 파일은 UTF-8로 읽고 쓴다(`encoding="utf-8"` 명시. 윈도우 기본값은 다르다).
- 커밋은 태스크마다 한다.

## Review Focus

설계서가 직접 말하지 않지만 실제로 쓰면 만나게 될 상황들. 각 줄의 테스트는 해당 태스크에 들어 있다.

1. **피드가 200으로 응답하지만 기사가 0건이거나 XML이 깨져 있음** → 프로그램이 죽지 않고 그 매체만 "수집 실패"로 처리한다. (Task 2)
2. **AI가 없는 기사 번호를 돌려주거나 한 기사를 두 사건에 넣음** → 없는 번호는 버리고, 겹친 기사는 먼저 나온 사건에만 둔다. 죽지 않는다. (Task 4)
3. **같은 날 두 번 실행됨(수동 재실행)** → 오늘 이미 보낸 것을 "이미 보낸 사건"으로 취급해 전부 빼 버리면 안 된다. 기록에서 오늘 날짜 항목은 비교 대상에서 제외하고, 저장할 때는 오늘 항목을 덮어쓴다. (Task 7)
4. **제목에 `<`, `>`, `&`가 들어 있음** → 슬랙 메시지가 깨지지 않도록 바꿔 쓴다. (Task 6)
5. **통과한 사건이 하나도 없는 날** → 메시지는 그대로 가고 각 구역에 "오늘은 큰 뉴스 없음"이 찍힌다. (Task 6, Task 8)

## File Structure

```
news-briefing/
  requirements.txt, requirements-dev.txt, pyproject.toml, .gitignore, README.md
  config/
    sources.json        매체 18곳: 이름, 소속 지역, 피드 주소, 최대 건수
    settings.json       통과 숫자, 모델 이름, 시장 종목
  briefing/
    __init__.py
    __main__.py         python -m briefing 진입점
    models.py           공용 자료형 (전 태스크가 여기서 가져다 씀)
    config.py           설정 파일 읽기와 검증
    collect.py          피드 → Article 목록
    ai.py               AI 호출 한 곳 (JSON 스키마 응답)
    cluster.py          AI 1: 묶기·분류
    select.py           통과 규칙, 지역 보장, 자르기 (순수 함수)
    rank.py             AI 2: 순위, 한국어 제목, "왜 중요한가"
    markets.py          지수·환율·금리
    render.py           브리핑 글 만들기 (순수 함수)
    slack.py            웹훅 전송
    state.py            보낸 기록(7일)과 날짜별 보관
    run.py              전체 순서 조립, 실패 처리, 연습 실행
  tests/                test_*.py, fixtures/
  state/sent.json       보낸 기록 (워크플로가 커밋)
  archive/YYYY-MM-DD.md 날짜별 브리핑 (워크플로가 커밋)
  .github/workflows/daily.yml
```

---

### Task 1: 프로젝트 뼈대, 설정 파일, 공용 자료형

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `.gitignore`, `config/sources.json`, `config/settings.json`, `briefing/__init__.py`, `briefing/models.py`, `briefing/config.py`
- Test: `tests/test_config.py`, `tests/fixtures/bad-sources.json`

**Interfaces:**
- Produces (`briefing/models.py`). 문자열 값은 `Literal`로 제한한다.

```python
OutletRegion = Literal["KR", "US", "UK", "CN", "JP", "EU"]
TopicRegion = Literal["KR", "US", "CN", "JP", "EU", "OTHER"]
Category = Literal["econ_it", "general"]
Tier = Literal["major", "medium", "routine"]
Continuity = Literal["new", "ongoing_progress", "ongoing_no_progress"]

class Outlet(BaseModel):            # pydantic
    id: str; name: str; region: OutletRegion; feeds: list[str] = Field(min_length=1)
    max_items: int = Field(gt=0); google_news: bool = False

class MarketSpec(BaseModel):
    label: str; symbol: str; unit: Literal["index", "krw", "pct"]
class GeneralRule(BaseModel):
    min_outlets: int; min_regions: int; kr_min_outlets: int; max: int       # 3, 2, 2, 3
class EconRule(BaseModel):
    max: int; guaranteed_regions: list[TopicRegion]                           # 10, ["CN","JP","EU"]
class Settings(BaseModel):
    model: str; window_hours: int; general: GeneralRule; econ: EconRule
    history_days: int; markets: list[MarketSpec]

@dataclass(frozen=True)
class Article:
    id: str; outlet_id: str; title: str; summary: str; url: str
    published_at: datetime | None          # 시간대 정보가 있는 UTC

@dataclass
class NewsEvent:
    key: str                               # "e1", "e2", ... 실행 안에서만 유일
    label: str; article_ids: list[str]; category: Category
    region: TopicRegion                    # 사건이 일어난 곳
    domestic_kr: bool
    tier: Tier | None                      # econ_it만 값이 있음
    continuity: Continuity

@dataclass(frozen=True)
class RankedItem:
    event_key: str; rank: int; title_ko: str; why_ko: str
@dataclass(frozen=True)
class BriefingItem:
    title_ko: str; why_ko: str; region: TopicRegion; ongoing: bool
    outlet_names: list[str]; url: str
@dataclass(frozen=True)
class MarketQuote:
    label: str; unit: str; value: float; change_pct: float; date: str   # YYYY-MM-DD
@dataclass(frozen=True)
class SentRecord:
    date: str; title_ko: str; why_ko: str
```

- Produces (`briefing/config.py`): `load_sources(path: str = "config/sources.json") -> list[Outlet]`, `load_settings(path: str = "config/settings.json") -> Settings`. 형식이 틀리면 pydantic의 `ValidationError`가 그대로 올라온다(어느 항목이 틀렸는지 들어 있다). 매체 `id`가 겹치면 `ValueError`.

- [ ] **Step 1: 뼈대 파일 작성**
  - `requirements.txt`: `anthropic`, `feedparser`, `pydantic` (각각 설치 시점의 최신 주 버전으로 하한 고정, 예: `anthropic>=1,<2`. 설치 후 `pip freeze`로 확인한 값으로 적는다)
  - `requirements-dev.txt`: `-r requirements.txt`, `pytest`
  - `pyproject.toml`: `[tool.pytest.ini_options]`에 `testpaths = ["tests"]`, `pythonpath = ["."]`
  - `.gitignore`: `.venv/`, `__pycache__/`, `.pytest_cache/`, `.env`
  - 가상 환경: `"C:\Users\USER\AppData\Local\Programs\Python\Python313\python.exe" -m venv .venv` 후 `.venv\Scripts\python -m pip install -r requirements-dev.txt`

- [ ] **Step 2: `config/sources.json` 작성** — 아래 표 그대로(키는 `id`, `name`, `region`, `max_items`, `google_news`, `feeds`). 주소는 2026-11-25에 전부 열리는 것을 확인했다. `google_news: true`인 4곳은 공식 톱뉴스 목록이 없거나(로이터, 차이신, NHK 월드) 자동 접근을 막아서(AP) 구글 뉴스의 매체별 목록으로 대신한다.

| id | name | region | max_items | google_news | feeds |
|---|---|---|---|---|---|
| reuters | 로이터 | UK | 25 | true | `https://news.google.com/rss/search?q=site:reuters.com+when:1d&hl=en-US&gl=US&ceid=US:en` |
| ap | AP | US | 25 | true | `https://news.google.com/rss/search?q=site:apnews.com+when:1d&hl=en-US&gl=US&ceid=US:en` |
| bbc | BBC | UK | 25 | false | `https://feeds.bbci.co.uk/news/rss.xml`, `https://feeds.bbci.co.uk/news/business/rss.xml` |
| bloomberg | 블룸버그 | US | 25 | false | `https://feeds.bloomberg.com/markets/news.rss`, `https://feeds.bloomberg.com/economics/news.rss`, `https://feeds.bloomberg.com/technology/news.rss` |
| wsj | WSJ | US | 25 | false | `https://feeds.content.dowjones.io/public/rss/RSSMarketsMain`, `https://feeds.content.dowjones.io/public/rss/RSSWorldNews`, `https://feeds.content.dowjones.io/public/rss/WSJcomUSBusiness` |
| cnbc | CNBC | US | 25 | false | `https://www.cnbc.com/id/100003114/device/rss/rss.html` |
| yna | 연합뉴스 | KR | 40 | false | `https://www.yna.co.kr/rss/news.xml`, `https://www.yna.co.kr/rss/economy.xml` |
| hankyung | 한국경제 | KR | 40 | false | `https://www.hankyung.com/feed/all-news`, `https://www.hankyung.com/feed/economy`, `https://www.hankyung.com/feed/finance` |
| mk | 매일경제 | KR | 40 | false | `https://www.mk.co.kr/rss/30000001/`, `https://www.mk.co.kr/rss/30100041/`, `https://www.mk.co.kr/rss/50200011/` |
| techcrunch | TechCrunch | US | 20 | false | `https://techcrunch.com/feed/` |
| verge | The Verge | US | 20 | false | `https://www.theverge.com/rss/index.xml` |
| etnews | 전자신문 | KR | 30 | false | `https://rss.etnews.com/Section901.xml`, `https://rss.etnews.com/Section902.xml` |
| scmp | SCMP | CN | 25 | false | `https://www.scmp.com/rss/91/feed`, `https://www.scmp.com/rss/92/feed`, `https://www.scmp.com/rss/4/feed` |
| caixin | 차이신 | CN | 25 | true | `https://news.google.com/rss/search?q=site:caixinglobal.com+when:2d&hl=en-US&gl=US&ceid=US:en` |
| nikkei | 닛케이 아시아 | JP | 25 | false | `https://asia.nikkei.com/rss/feed/nar` |
| nhk | NHK 월드 | JP | 25 | true | `https://news.google.com/rss/search?q=site:www3.nhk.or.jp/nhkworld+when:1d&hl=en-US&gl=US&ceid=US:en` |
| ft | 파이낸셜타임스 | UK | 25 | false | `https://www.ft.com/rss/home`, `https://www.ft.com/world?format=rss`, `https://www.ft.com/markets?format=rss` |
| euronews | 유로뉴스 | EU | 25 | false | `https://www.euronews.com/rss?format=mrss&level=theme&name=news`, `https://www.euronews.com/rss?format=mrss&level=theme&name=business` |

한국 매체의 `max_items`가 큰 이유: 피드에 기사가 시간순으로 50~120건씩 쏟아져서, 25건만 보면 최근 한두 시간치밖에 안 되어 "한국 매체 2곳 이상" 겹침이 잘 안 생긴다.

- [ ] **Step 3: `config/settings.json` 작성**

```json
{
  "model": "claude-haiku-5-5",
  "window_hours": 24,
  "general": { "min_outlets": 3, "min_regions": 2, "kr_min_outlets": 2, "max": 3 },
  "econ": { "max": 10, "guaranteed_regions": ["CN", "JP", "EU"] },
  "history_days": 7,
  "markets": [
    { "label": "코스피", "symbol": "^KS11", "unit": "index" },
    { "label": "코스닥", "symbol": "^KQ11", "unit": "index" },
    { "label": "나스닥", "symbol": "^IXIC", "unit": "index" },
    { "label": "S&P500", "symbol": "^GSPC", "unit": "index" },
    { "label": "원/달러", "symbol": "KRW=X", "unit": "krw" },
    { "label": "미 10년물", "symbol": "^TNX", "unit": "pct" }
  ]
}
```

- [ ] **Step 4: 실패하는 테스트 작성** (`tests/test_config.py`)

```python
def test_sources_has_18_outlets_with_valid_regions():
    s = load_sources()
    assert len(s) == 18 and len({o.id for o in s}) == 18
    assert sorted(o.id for o in s if o.region == "KR") == ["etnews", "hankyung", "mk", "yna"]
    assert all(o.feeds and o.max_items > 0 for o in s)

def test_settings_carry_the_spec_numbers():
    st = load_settings()
    assert st.general.model_dump() == {"min_outlets": 3, "min_regions": 2, "kr_min_outlets": 2, "max": 3}
    assert st.econ.max == 10 and st.econ.guaranteed_regions == ["CN", "JP", "EU"]
    assert st.window_hours == 24 and st.history_days == 7 and len(st.markets) == 6

def test_unknown_region_is_rejected():          # fixtures/bad-sources.json: region이 "XX"
    with pytest.raises(ValidationError, match="region"):
        load_sources("tests/fixtures/bad-sources.json")

def test_duplicate_outlet_id_is_rejected(tmp_path): ...   # ValueError
```

- [ ] **Step 5: 실패 확인** — Run: `.venv\Scripts\python -m pytest -q` → Expected: FAIL (`briefing.config` 없음)
- [ ] **Step 6: `briefing/models.py`, `briefing/config.py` 구현** (Interfaces 블록 그대로)
- [ ] **Step 7: 통과 확인** — Run: `.venv\Scripts\python -m pytest -q` → Expected: 4 passed
- [ ] **Step 8: 커밋** — 저장소가 아직 없으면 `git init -b main` 먼저. `git add -A && git commit -m "chore: scaffold project, config and shared models"` (설계서와 이 계획 문서도 이 커밋에 포함된다)

---

### Task 2: 뉴스 수집

**Files:**
- Create: `briefing/collect.py`
- Test: `tests/test_collect.py`, `tests/fixtures/rss.xml`, `atom.xml`, `rdf-nodate.xml`, `googlenews.xml`, `empty.xml`, `broken.xml`

**Interfaces:**
- Consumes: `Outlet`, `Article`, `Settings` (Task 1)
- Produces:

```python
FetchText = Callable[[str], str]                       # 본문 문자열, 실패하면 예외
@dataclass
class CollectResult:
    articles: list[Article]; failed_outlet_ids: list[str]
def http_get_text(url: str) -> str                     # 기본 FetchText
def parse_feed(xml: str, outlet: Outlet) -> list[Article]      # id는 빈 문자열로 둔다
def collect(outlets: list[Outlet], settings: Settings, now: datetime,
            fetch_text: FetchText = http_get_text) -> CollectResult
```

규칙:
- `http_get_text`: `urllib.request`로 `User-Agent: Mozilla/5.0 (compatible; feed-reader)`를 붙이고 20초 제한. 200이 아니면 예외. 바이트를 그대로 `feedparser`에 넘기는 편이 인코딩 처리에 유리하지만, 인터페이스를 단순하게 두기 위해 응답의 charset(없으면 UTF-8)으로 풀어 문자열을 돌려준다.
- `parse_feed`: `feedparser.parse(xml)`로 RSS·Atom·RDF를 읽는다. `entries`가 비어 있고 `bozo`가 참이면 `ValueError`. `summary`는 항목의 `summary`에서 HTML 태그를 걷어내고 공백을 정리한 뒤 300자로 자른다. `published_at`은 `published_parsed`(없으면 `updated_parsed`)를 UTC `datetime`으로, 둘 다 없으면 `None`. 제목이나 링크가 없는 항목은 건너뛴다.
- `outlet.google_news`가 참이면 제목 끝의 `" - 매체이름"` 꼬리(마지막 `" - "` 뒤)를 떼고, `summary`는 빈 문자열로 둔다(구글 뉴스의 요약은 링크 HTML일 뿐 내용이 없다).
- 매체 하나의 처리: 그 매체의 모든 피드를 읽어 합친다 → `url`이 같은 것과 제목이 같은 것을 하나로 → `published_at`이 `now - window_hours`보다 오래된 것은 뺀다(날짜가 없는 기사는 남긴다: 닛케이 피드에는 날짜가 없다) → 최신순 정렬(날짜 없는 것은 피드에 나온 순서대로 뒤에) → `max_items`개로 자른다.
- 매체의 피드가 전부 실패했거나, 다 읽었는데 기사가 0건이면 `failed_outlet_ids`에 넣는다. 피드 일부만 실패하면 실패로 치지 않는다.
- 매체들은 `ThreadPoolExecutor(max_workers=8)`로 동시에 읽되 결과 순서는 `outlets` 순서를 지킨다. 어떤 예외도 `collect` 밖으로 나가지 않는다.
- `Article.id`는 전체 결과에 `a1`, `a2`, …를 순서대로 붙인다(AI 응답 길이를 줄이기 위한 짧은 번호).

- [ ] **Step 1: 픽스처 작성** — 각 3~5건짜리 작은 파일. `rss.xml`에는 30시간 전 기사 1건과 HTML이 든 요약 1건, 같은 URL 2건을 넣는다(기준 시각 `2026-11-25T22:00:00Z`). `googlenews.xml`의 제목은 `Fed cuts rates by quarter point - Reuters` 형태. `empty.xml`은 `<item>`이 없는 정상 RSS, `broken.xml`은 XML이 아닌 글(`not a feed`).

- [ ] **Step 2: 실패하는 테스트 작성** — `NOW = datetime(2026, 11, 25, 22, tzinfo=UTC)`, 도우미 `outlet(**kw)`와 `serve(mapping)`(없는 주소면 예외를 던지는 `FetchText`).

```python
def test_rss_summary_has_no_html_and_is_capped_at_300(): ...
def test_atom_entries_are_parsed(): ...
def test_undated_rdf_items_are_kept(): ...                    # published_at is None, 건수 유지
def test_google_news_strips_outlet_suffix_and_blanks_summary(): ...   # title == "Fed cuts rates by quarter point", summary == ""
def test_old_articles_and_duplicate_urls_are_dropped(): ...
def test_cap_keeps_the_newest(): ...                          # max_items=2
def test_empty_feed_marks_outlet_failed():
    r = collect([outlet()], SETTINGS, NOW, serve({"u1": EMPTY}))
    assert r.articles == [] and r.failed_outlet_ids == ["x"]
def test_broken_feed_marks_outlet_failed(): ...               # 위와 같은 결과, 예외 없음
def test_one_failing_feed_of_two_is_not_a_failure(): ...      # feeds=["u1","u2"], u2 없음 → failed == []
def test_ids_run_a1_to_aN_across_outlets(): ...
```

- [ ] **Step 3: 실패 확인** → **Step 4: 구현** → **Step 5: 통과 확인** (`.venv\Scripts\python -m pytest -q`)
- [ ] **Step 6: 커밋** — `git commit -m "feat: collect top news from configured feeds"`

---

### Task 3: 통과 규칙, 지역 보장, 자르기 (순수 함수)

설계서 3.2의 핵심. 이 파일은 AI도 네트워크도 모른다.

**Files:**
- Create: `briefing/select.py`
- Test: `tests/test_select.py`

**Interfaces:**
- Consumes: `NewsEvent`, `Article`, `Outlet`, `Settings`, `RankedItem`
- Produces:

```python
@dataclass
class Passed:
    econ: list[NewsEvent]; general: list[NewsEvent]
def pass_filter(events: list[NewsEvent], articles: list[Article], outlets: list[Outlet], s: Settings) -> Passed
    """통과 규칙만 적용. 개수 제한은 아직 적용하지 않는다."""
def apply_caps(passed: Passed, ranked: list[RankedItem], s: Settings) -> Passed
    """순위가 매겨진 뒤 지역 보장과 개수 제한을 적용. 각 목록은 rank 오름차순."""
```

`pass_filter` 규칙(순서대로):
1. `continuity == "ongoing_no_progress"`는 뺀다.
2. 사건의 매체 수 = `article_ids`에 해당하는 기사들의 **서로 다른 `outlet_id`** 수. 지역 수 = 그 매체들의 서로 다른 `Outlet.region` 수. 한국 매체 수 = `region == "KR"`인 매체 수. 기사 목록에 없는 번호는 무시한다.
3. `category == "econ_it"`: `tier`가 `"major"` 또는 `"medium"`이면 통과(매체 1곳이어도). `"routine"`이나 `None`은 뺀다.
4. `category == "general"`:
   - `domestic_kr`이 참이면 한국 매체 수 ≥ `s.general.kr_min_outlets`일 때 통과.
   - 아니면 매체 수 ≥ `s.general.min_outlets` **그리고** 지역 수 ≥ `s.general.min_regions`일 때 통과.

`apply_caps` 규칙:
1. `ranked`에 없는 사건은 순위 맨 뒤로 보낸다(원래 순서 유지).
2. 경제·IT: `s.econ.guaranteed_regions`의 각 지역에 대해, 그 지역 사건이 있으면 순위가 가장 높은 1건을 먼저 확보한다. 그다음 남은 자리를 순위대로 채워 총 `s.econ.max`건까지. 결과는 순위순으로 다시 정렬한다.
3. 일반: 순위대로 `s.general.max`건.

- [ ] **Step 1: 실패하는 테스트 작성** — 테스트 파일 안에 매체 10곳짜리 작은 목록(KR 3: yna·hankyung·mk, US 3, UK 2, CN 1, JP 1)과, 매체 id 목록을 받아 기사와 사건을 만들어 주는 도우미 `ev(outlet_ids, **overrides)`를 둔다.

```python
# pass_filter
def test_econ_medium_passes_with_a_single_outlet(): ...
def test_econ_routine_and_none_tier_are_dropped(): ...
def test_ongoing_no_progress_is_dropped_even_when_major(): ...
def test_ongoing_progress_passes_like_a_new_event(): ...
def test_general_world_3_outlets_in_2_regions_passes(): ...           # US, US, UK
def test_general_world_3_outlets_in_1_region_fails(): ...             # US, US, US
def test_general_world_2_outlets_in_2_regions_fails(): ...
def test_general_domestic_kr_2_korean_outlets_passes(): ...           # yna, mk
def test_general_domestic_kr_1_korean_plus_2_foreign_fails(): ...     # domestic_kr=True, yna·US·UK
def test_two_articles_from_one_outlet_count_once(): ...               # yna 기사 2건 → 한국 매체 수 1 → 탈락
def test_unknown_article_ids_are_ignored(): ...
# apply_caps
def test_econ_caps_at_10_in_rank_order(): ...                         # US 14건 → 순위 1~10
def test_econ_guaranteed_regions_get_a_slot_even_when_ranked_last():
    # US 12건(순위 1~12) + CN 1건(13위) + JP 2건(14, 15위), EU 없음
    # 기대: 10건 = US 순위 1~8 + CN 13위 + JP 14위, rank 오름차순
def test_econ_no_padding_when_a_guaranteed_region_is_absent(): ...
def test_econ_guaranteed_region_already_in_top_is_not_doubled(): ...  # CN이 2위와 13위 → 13위는 안 들어감
def test_econ_fewer_than_max_returns_all(): ...
def test_general_caps_at_3(): ...
def test_events_missing_from_ranked_go_last(): ...
```

- [ ] **Step 2: 실패 확인** → **Step 3: 구현** → **Step 4: 통과 확인** (`.venv\Scripts\python -m pytest -q`)
- [ ] **Step 5: 커밋** — `git commit -m "feat: pass rules, regional guarantee and caps"`

---

### Task 4: AI 단계 — 묶기·분류, 순위·요약

**Files:**
- Create: `briefing/ai.py`, `briefing/cluster.py`, `briefing/rank.py`
- Test: `tests/test_cluster.py`, `tests/test_rank.py`

**Interfaces:**
- Consumes: `Article`, `Outlet`, `NewsEvent`, `RankedItem`, `SentRecord`
- Produces:

```python
# briefing/ai.py
class AskJson(Protocol):
    def __call__(self, *, system: str, user: str, schema: dict, max_tokens: int) -> dict: ...
class AiError(Exception): ...
def make_ask_json(model: str) -> AskJson               # 실제 Anthropic API 호출
# briefing/cluster.py
def cluster_events(articles: list[Article], outlets: list[Outlet], history: list[SentRecord], ask: AskJson) -> list[NewsEvent]
# briefing/rank.py
def rank_events(events: list[NewsEvent], articles: list[Article], ask: AskJson) -> list[RankedItem]
```

`make_ask_json` 구현 지침(`anthropic` SDK):
- `client = anthropic.Anthropic()` (환경 변수 `ANTHROPIC_API_KEY`를 자동으로 읽는다).
- 호출:

```python
with client.messages.stream(
    model=model, max_tokens=max_tokens, system=system,
    messages=[{"role": "user", "content": user}],
    output_config={"format": {"type": "json_schema", "schema": schema}},
) as stream:
    msg = stream.get_final_message()
```
  스트리밍을 쓰는 이유: 묶기 응답이 길어 시간 제한에 걸리지 않게 하기 위해서다.
- `temperature`, `thinking`, `tool_choice`는 보내지 않는다(이 모델에서 거부되거나 기본값이 맞다).
- 응답 처리: `msg.stop_reason`이 `"refusal"` 또는 `"max_tokens"`이면 그 이유를 담아 `AiError`. 아니면 `type == "text"`인 첫 블록의 글을 `json.loads`해 돌려준다. JSON이 아니면 `AiError`.
- 호출이 끝나면 `msg.usage.input_tokens`, `msg.usage.output_tokens`를 `print`로 한 줄 남긴다(비용 확인용).
- SDK 예외(`anthropic.APIError` 계열)는 `AiError`로 감싸 올린다. 재시도는 SDK 기본(2회)에 맡긴다.

스키마는 각 파일에 손으로 쓴 딕셔너리로 둔다. 모든 객체에 `"additionalProperties": False`와 전체 필드 `required`를 넣는다.

`cluster_events`:
- AI에 주는 글: 기사마다 한 줄 `a12 | 매체이름 | 제목 | 요약`. 그 뒤에 "최근 7일간 이미 보낸 소식" 목록(`날짜 | 제목 | 한 줄`, 없으면 "없음").
- 응답 스키마: `{"events": [{"label": str, "article_ids": [str], "category": "econ_it"|"general", "region": "KR"|"US"|"CN"|"JP"|"EU"|"OTHER", "domestic_kr": bool, "tier": "major"|"medium"|"routine"|null, "continuity": "new"|"ongoing_progress"|"ongoing_no_progress"}]}`
- `max_tokens=32000`.
- 시스템 지시문에 반드시 들어갈 내용(문장은 구현자가 쓴다):
  - 같은 사건을 다룬 기사를 하나의 사건으로 묶는다. 한 기사는 한 사건에만 넣는다. 혼자인 기사도 사건 하나다.
  - **기본 제외**: 연예, 스포츠 결과, 단순 사건·사고, 정치인 말싸움, 광고성 기사, 의견·칼럼은 응답에 넣지 않는다.
  - `econ_it`의 범위: 금리, 환율, 물가, 고용, 무역·관세, 기업 실적, 인수합병, 원자재, 부동산 정책, 반도체, AI, 빅테크, 기술 규제.
  - `tier` 3단계의 정의와 예시를 설계서 3.2의 표 그대로: 큼(시장 전체를 움직임: 기준금리 결정, 환율 급변, 대형 정책·관세), 중간(한 산업이나 주요 기업에 영향: 주요 기업 실적, 인수합병, 산업 규제, 대형 투자·감원), 일상(소소한 신제품, 증권사 전망·목표가, 단순 시황 기사, 인사). `general`이면 `null`.
  - `region`은 매체의 나라가 아니라 사건이 일어난 곳. 영국은 `EU`에 넣는다.
  - `domestic_kr`은 한국 안에서만 의미가 큰 뉴스일 때 참.
  - `continuity`: 이미 보낸 소식 목록과 비교한다. 새 결정·발표·숫자·행동이 나왔으면 `ongoing_progress`, 같은 내용의 후속 해설·반응이면 `ongoing_no_progress`, 목록에 없으면 `new`.
- 응답 후처리(프로그램): 응답 모양은 pydantic 모델로 한 번 검증한다(틀리면 `AiError`). 없는 기사 번호는 버린다. 이미 앞 사건에 들어간 기사 번호는 뒤 사건에서 뺀다. 기사가 0건이 된 사건은 버린다. `category == "general"`이면 `tier`를 `None`으로 맞춘다. `key`는 남은 사건에 `e1`, `e2`, …를 붙인다.
- `articles`가 비어 있으면 AI를 호출하지 않고 `[]`.

`rank_events`:
- `events`가 비어 있으면 AI를 호출하지 않고 `[]`.
- AI에 주는 글: 사건마다 `e3 | 분류 | 지역 | 단계`와 그 아래 기사들의 `제목 — 요약`(사건당 최대 5건).
- 응답 스키마: `{"items": [{"event_key": str, "rank": int, "title_ko": str, "why_ko": str}]}`, `max_tokens=16000`.
- 시스템 지시문에 반드시 들어갈 내용:
  - 순위 기준: 시장·금리·환율·기업 실적에 주는 영향, 영향받는 사람의 수, 일주일 뒤에도 의미가 있는가. `econ_it`과 `general`은 각각 따로 1위부터 매긴다.
  - `title_ko`: 한국어 한 줄 제목(40자 안팎). 외국 기사는 번역한다.
  - `why_ko`: "그래서 왜 중요한가" 한두 문장(80자 안팎). 시장이나 경제에 어떻게 이어지는지 쓴다.
  - **주어진 제목과 요약에 없는 숫자나 사실은 쓰지 않는다.**
  - **"사라", "팔아라", "매수·매도 추천" 같은 투자 조언은 쓰지 않는다.**
- 응답 후처리: pydantic 검증. `event_key`가 `events`에 없는 항목은 버린다. 같은 `event_key`가 두 번 나오면 첫 번째만 둔다.

- [ ] **Step 1: 실패하는 테스트 작성** — 가짜 `ask`는 받은 인자를 기록하고 정해 둔 딕셔너리를 돌려준다.

```python
# cluster
def test_maps_response_to_events_with_keys_e1_to_eN(): ...
def test_unknown_article_ids_are_dropped(): ...                       # "a999"
def test_article_claimed_twice_stays_in_the_first_event(): ...
def test_event_left_with_no_articles_is_dropped(): ...
def test_general_event_gets_tier_none_even_if_model_set_one(): ...
def test_prompt_lists_every_article_id_and_the_history(): ...         # user 글에 "a1", "a2", 기록의 제목
def test_no_articles_means_no_ai_call(): ...
def test_malformed_response_raises_ai_error(): ...                    # {"events": [{"label": "x"}]}
def test_error_from_ask_propagates(): ...
# rank
def test_no_events_means_no_ai_call(): ...
def test_unknown_event_key_dropped_and_first_duplicate_kept(): ...
def test_system_prompt_forbids_advice_and_invented_numbers(): ...     # system에 "조언"과 "숫자"가 들어 있다
```

- [ ] **Step 2: 실패 확인** → **Step 3: 구현** → **Step 4: 통과 확인** (`.venv\Scripts\python -m pytest -q`. `make_ask_json`의 실제 호출은 Task 9에서 확인한다)
- [ ] **Step 5: 커밋** — `git commit -m "feat: AI clustering and ranking steps"`

---

### Task 5: 시장 요약

**Files:**
- Create: `briefing/markets.py`
- Test: `tests/test_markets.py`, `tests/fixtures/yahoo-chart.json`

**Interfaces:**
- Consumes: `MarketSpec`, `MarketQuote`, `FetchText`·`http_get_text` (Task 2)
- Produces:

```python
def parse_chart(text: str, spec: MarketSpec) -> MarketQuote          # 형식이 다르면 ValueError
def fetch_markets(specs: list[MarketSpec], fetch_text: FetchText = http_get_text) -> list[MarketQuote] | None
```

규칙:
- 주소: `https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol, safe="")}?range=5d&interval=1d` (2026-11-25에 6개 종목 모두 응답 확인).
- `parse_chart`: `chart.result[0]`의 `timestamp`와 `indicators.quote[0].close`에서 `None`이 아닌 마지막 두 종가를 쓴다. `value` = 마지막 종가, `change_pct` = (마지막 − 그 전) / 그 전 × 100, `date` = 마지막 종가의 시각을 UTC 기준 `YYYY-MM-DD`로. 종가가 2개 미만이면 `ValueError`.
- `fetch_markets`: **하나라도 실패하면 `None`**을 반환한다(시장 줄 전체를 뺀다. 일부만 보이면 헷갈린다). 절대 예외를 내보내지 않는다.

- [ ] **Step 1: 픽스처와 실패하는 테스트 작성**

```python
def test_uses_the_last_two_non_null_closes():
    # 픽스처 close: [100, 110, null, 121], 마지막 timestamp = 2026-11-24T21:00:00Z
    q = parse_chart(FIX, MarketSpec(label="나스닥", symbol="^IXIC", unit="index"))
    assert (q.label, q.unit, q.value, q.date) == ("나스닥", "index", 121, "2026-11-24")
    assert q.change_pct == pytest.approx(10.0)
def test_fewer_than_two_closes_raises(): ...
def test_any_failure_returns_none_without_raising(): ...
def test_quotes_come_back_in_settings_order(): ...
```

- [ ] **Step 2: 실패 확인** → **Step 3: 구현** → **Step 4: 통과 확인**
- [ ] **Step 5: 커밋** — `git commit -m "feat: market summary line data"`

---

### Task 6: 브리핑 글 만들기와 슬랙 전송

**Files:**
- Create: `briefing/render.py`, `briefing/slack.py`
- Test: `tests/test_render.py`, `tests/test_slack.py`

**Interfaces:**
- Consumes: `BriefingItem`, `MarketQuote`
- Produces:

```python
@dataclass
class Briefing:
    date: str                              # YYYY-MM-DD, 한국 날짜
    markets: list[MarketQuote] | None
    econ: list[BriefingItem]; general: list[BriefingItem]
    failed_outlet_names: list[str]
def render_slack(b: Briefing) -> str       # 슬랙 mrkdwn
def render_markdown(b: Briefing) -> str    # 보관 파일용
def render_failure(date: str, reason: str) -> str
# briefing/slack.py
Post = Callable[[str, bytes], int]         # (url, body) -> HTTP 상태 코드
def send_slack(text: str, webhook_url: str, post: Post = http_post_json) -> None
```

`render_slack` 출력 형식(설계서 4장). 예:

```
📊 *11/25(수) 아침 브리핑*
코스피 2,654.12 (+0.4%) | 코스닥 865.30 (-0.1%) | 나스닥 23,742.68 (-1.2%) | S&P500 7,205.03 (-0.6%)
원/달러 1,343.5원 (+0.2%) | 미 10년물 4.90%

💰 *경제·IT (2건)*
• *엔비디아 실적 예상 상회, 시간외 주가는 하락*  [미국]
  → 기대치가 이미 높았다는 뜻. 국내 반도체주 개장 영향 주목.
  블룸버그 · CNBC · 한국경제  <https://example.com/a|원문>
• *미·중 관세 협상 2차 회담 일정 확정* (이어지는 소식)  [중국]
  → 회담이 실제로 열린다는 신호. 관세 인하 기대가 수출주에 반영될 수 있음.
  로이터  <https://example.com/b|원문>

🌍 *그 외 큰 뉴스 (0건)*
오늘은 큰 뉴스 없음

수집 실패: 차이신, NHK 월드
```

세부 규칙:
- 날짜 줄: `M/D(요일)`, 요일은 한국어 한 글자.
- 지수(`unit == "index"`)는 소수 2자리와 천 단위 쉼표, 환율(`"krw"`)은 소수 1자리 + `원`, 금리(`"pct"`)는 소수 2자리 + `%`이고 등락률을 붙이지 않는다. 등락률은 소수 1자리, 0 이상이면 `+`.
- 시장 줄은 앞 4개와 나머지로 두 줄. `markets`가 `None`이면 두 줄 모두 생략.
- 시장 종목 중 `date`가 브리핑 날짜의 전날보다 이른 것이 있으면(주말·공휴일) 둘째 시장 줄 끝에 ` (M/D 종가)`를 한 번, 가장 이른 날짜로 붙인다.
- 지역 표시: KR 한국, US 미국, CN 중국, JP 일본, EU 유럽, OTHER 세계.
- `ongoing`이면 제목 뒤에 ` (이어지는 소식)`.
- 매체 이름은 ` · `로 잇고 최대 4개, 넘으면 ` 외 N곳`.
- 구역에 항목이 없으면 제목은 `(0건)`으로 두고 `오늘은 큰 뉴스 없음` 한 줄.
- `failed_outlet_names`가 비어 있으면 "수집 실패" 줄과 그 앞 빈 줄을 생략.
- 제목·한 줄·매체 이름의 `&`, `<`, `>`는 `&amp;`, `&lt;`, `&gt;`로 바꾼다. 링크 URL의 `|`와 `>`는 `%7C`, `%3E`로 바꾼다.
- `render_markdown`은 같은 내용을 일반 마크다운으로: 첫 줄 `# 2026-11-25 아침 브리핑`, 항목은 `- **제목** [지역]`, 링크는 `[원문](url)`. 슬랙용 바꿔 쓰기는 하지 않는다.
- `render_failure`: `⚠️ *11/25(수) 브리핑 생성 실패*\n이유: {reason}`.

`send_slack`: 본문은 `json.dumps({"text": text, "unfurl_links": False, "unfurl_media": False}).encode("utf-8")`, `Content-Type: application/json`, 20초 제한. 상태 코드가 200이 아니면 코드를 담아 `RuntimeError`. 오류 메시지에 `webhook_url`을 넣지 않는다(`urllib`의 예외도 잡아서 주소 없는 메시지로 바꾼다).

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# render
def test_full_briefing_matches_expected_text_exactly(): ...           # 위 예시 전체를 문자열로 비교
def test_empty_sections_show_0_and_no_big_news(): ...
def test_markets_none_omits_market_lines(): ...
def test_stale_market_date_adds_close_date(): ...                     # 브리핑 2026-11-29(일), 시장 date 2026-11-27 → "(11/27 종가)"
def test_escapes_special_characters():
    # title_ko="AT&T <속보> 합병", url="https://x.com/a|b>c"
    # 결과에 "AT&amp;T &lt;속보&gt; 합병" 과 "<https://x.com/a%7Cb%3Ec|원문>" 포함
def test_more_than_4_outlets_shows_n_more(): ...                      # 6곳 → "… 외 2곳"
def test_no_failed_outlets_omits_the_line(): ...
def test_render_failure_has_date_and_reason(): ...
def test_markdown_has_title_and_plain_links(): ...
# slack
def test_posts_json_with_text_and_unfurl_off(): ...
def test_non_200_raises_without_leaking_the_url(): ...
```

- [ ] **Step 2: 실패 확인** → **Step 3: 구현** → **Step 4: 통과 확인**
- [ ] **Step 5: 커밋** — `git commit -m "feat: render briefing and send to Slack"`

---

### Task 7: 보낸 기록과 날짜별 보관

**Files:**
- Create: `briefing/state.py`, `state/sent.json` (내용 `[]`), `archive/.gitkeep`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `SentRecord`, `BriefingItem`
- Produces:

```python
def load_history(path: str, today: str, history_days: int) -> list[SentRecord]
def save_history(path: str, today: str, items: list[BriefingItem], history_days: int) -> None
def save_archive(directory: str, today: str, markdown: str) -> None
```

규칙:
- `load_history`: 파일이 없거나 JSON이 깨져 있으면 `[]`(죽지 않는다). `today`에서 `history_days`일보다 더 오래된 항목은 뺀다(정확히 7일 전은 남긴다). **`date == today`인 항목도 뺀다**(같은 날 재실행 대비).
- `save_history`: 파일을 다시 읽어 `date == today`인 항목을 지우고, 오늘 보낸 항목(경제·IT와 일반 전부)을 추가하고, 오래된 것을 지운 뒤 `ensure_ascii=False`, 들여쓰기 2칸 JSON으로 쓴다. 폴더가 없으면 만든다.
- `save_archive`: `{directory}/{today}.md`에 쓴다. 이미 있으면 덮어쓴다. 폴더가 없으면 만든다.

- [ ] **Step 1: 실패하는 테스트 작성** — pytest의 `tmp_path`에서.

```python
def test_missing_or_corrupt_file_gives_empty_history(tmp_path): ...
def test_history_drops_old_entries_and_todays(tmp_path):
    # today 2026-11-25. 항목 날짜: 11-17(8일 전), 11-18(7일 전), 11-24, 11-25 → 11-18, 11-24만
def test_second_run_same_day_replaces_todays_entries(tmp_path): ...
def test_save_prunes_old_entries(tmp_path): ...
def test_archive_is_written_and_overwritten(tmp_path): ...
def test_korean_text_round_trips(tmp_path): ...                       # 파일 안에 "\\u" 없음
```

- [ ] **Step 2: 실패 확인** → **Step 3: 구현** → **Step 4: 통과 확인**
- [ ] **Step 5: 커밋** — `git commit -m "feat: sent history and daily archive"`

---

### Task 8: 전체 조립, 실패 처리, 연습 실행

**Files:**
- Create: `briefing/run.py`, `briefing/__main__.py`
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: Task 1~7의 모든 Produces
- Produces:

```python
@dataclass
class Deps:
    now: datetime
    outlets: list[Outlet]; settings: Settings
    collect: Callable[[list[Outlet], Settings, datetime], CollectResult]
    ask: AskJson
    fetch_markets: Callable[[list[MarketSpec]], list[MarketQuote] | None]
    send: Callable[[str], None]
    state_path: str; archive_dir: str
    dry_run: bool
    log: Callable[[str], None]
def run(deps: Deps) -> Literal["sent", "failed"]
def main(argv: list[str]) -> int           # __main__.py가 sys.exit(main(sys.argv[1:]))
```

`run`의 순서:
1. `today` = `now`를 한국 시간(UTC+9)으로 바꾼 `YYYY-MM-DD`.
2. `collect`. 실패한 매체 수 × 2 ≥ 전체 매체 수이면 실패 처리(이유: `매체 N곳 중 M곳 수집 실패`).
3. `load_history` → `cluster_events` → `pass_filter` → `rank_events`(통과한 경제·IT와 일반을 합쳐 한 번 호출) → `apply_caps`.
4. `BriefingItem` 만들기: `title_ko`/`why_ko`는 `RankedItem`에서. `RankedItem`이 없는 사건(AI가 빠뜨림)은 브리핑에서 뺀다. `outlet_names`는 사건의 매체 이름들(중복 없이, `sources.json` 순서대로). `url`은 사건의 기사 중 `google_news`가 아닌 매체의 것을 우선해 첫 번째. `ongoing`은 `continuity == "ongoing_progress"`.
5. `fetch_markets`.
6. `render_slack` → `send`. `render_markdown` → `save_archive`. `save_history`.
7. `"sent"` 반환.

실패 처리: 2~4단계에서 예외가 나거나 2의 조건에 걸리면 `send(render_failure(today, 이유))`를 보내고 `"failed"`를 반환한다. 기록과 보관은 쓰지 않는다. 이유에는 예외의 종류와 메시지만 넣는다. 6단계의 `send`가 실패하면 예외를 그대로 올린다(깃허브가 실행 실패로 표시하고 메일을 보낸다).

`dry_run`이면: `send`를 부르지 않고 브리핑 글(실패 시에는 실패 알림 글)을 `log`로 출력하며, 기록과 보관도 쓰지 않는다.

`main`:
- `--dry-run` 인자를 읽는다(`argparse`).
- 표준 출력을 UTF-8로 바꾼다(`sys.stdout.reconfigure(encoding="utf-8")`. 윈도우 콘솔에서 한글과 이모지가 깨지지 않게).
- `ANTHROPIC_API_KEY`가 없으면 "ANTHROPIC_API_KEY 환경 변수가 필요합니다"를 출력하고 1을 반환. `--dry-run`이 아닌데 `SLACK_WEBHOOK_URL`이 없으면 같은 방식으로 1.
- 실제 의존성으로 `run`을 부른다. 결과가 `"failed"`이면 1, 아니면 0.

- [ ] **Step 1: 실패하는 테스트 작성** — 모든 의존성을 가짜로. 가짜 `ask`는 `schema`에 `"events"`가 있는지로 묶기 호출과 순위 호출을 구분한다.

```python
def test_happy_path_sends_once_and_saves(tmp_path): ...       # send 1회, archive/2026-11-25.md 존재, sent.json에 오늘 항목
def test_uses_the_korean_date(tmp_path): ...                  # now = 2026-11-24T22:00:00Z → "2026-11-25"
def test_half_of_outlets_failed_sends_failure_notice(tmp_path): ...   # 4곳 중 2곳 → 글에 "생성 실패", "failed", 파일 없음
def test_clustering_error_sends_failure_notice_with_reason(tmp_path): ...
def test_nothing_passes_still_sends_with_no_big_news(tmp_path): ...
def test_markets_none_sends_without_market_lines(tmp_path): ...
def test_dry_run_sends_nothing_and_writes_nothing(tmp_path): ...      # log에 브리핑 글
def test_event_without_ranked_item_is_left_out(tmp_path): ...
def test_prefers_a_non_google_news_url(tmp_path): ...
def test_send_failure_on_the_briefing_propagates(tmp_path): ...
def test_main_without_api_key_returns_1(monkeypatch, capsys): ...
```

- [ ] **Step 2: 실패 확인** → **Step 3: 구현** → **Step 4: 통과 확인**
- [ ] **Step 5: 커밋** — `git commit -m "feat: orchestrate daily run with failure notice and dry run"`

---

### Task 9: 자동 실행, 사용 안내, 실제 데이터 확인

**Files:**
- Create: `.github/workflows/daily.yml`, `README.md`

**Interfaces:**
- Consumes: `python -m briefing`, `python -m briefing --dry-run` (Task 8)

- [ ] **Step 1: `.github/workflows/daily.yml` 작성**

```yaml
name: daily-briefing
on:
  schedule:
    - cron: "0 22 * * *"   # 매일 22:00 UTC = 한국 시간 07:00
  workflow_dispatch: {}
permissions:
  contents: write
concurrency: daily-briefing
jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13", cache: pip }
      - run: pip install -r requirements.txt
      - run: python -m briefing
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
      - name: Save archive and history
        if: always()
        run: |
          git config user.name "news-briefing-bot"
          git config user.email "actions@users.noreply.github.com"
          git add archive state
          git diff --cached --quiet || git commit -m "briefing: $(TZ=Asia/Seoul date +%F)"
          git push
```

- [ ] **Step 2: `README.md` 작성 (한국어, 개발자가 아닌 사람 기준)** — 다음을 순서대로, 화면에서 누를 메뉴 이름까지:
  1. 이 프로그램이 하는 일 세 줄.
  2. 준비물 발급 방법: (가) 슬랙 개인 워크스페이스 만들기 → 채널 만들기 → 수신 웹훅 주소 발급, (나) AI 호출용 키 발급(방식은 "사용자 확인 사항" 1번 결정에 따름), (다) 깃허브 저장소의 Settings → Secrets and variables → Actions에 비밀 값 등록.
  3. 지금 바로 한 번 보내 보기: Actions 탭 → daily-briefing → Run workflow.
  4. 기준 바꾸기: `config/settings.json`의 각 숫자가 무엇인지 표로. 매체 넣고 빼기: `config/sources.json`.
  5. 브리핑이 안 왔을 때 확인할 곳: 슬랙의 "생성 실패" 메시지, Actions 탭의 실행 기록.
  6. 알아 둘 점: 예약 실행은 5~30분 늦을 수 있음. 로이터·AP·차이신·NHK 월드는 구글 뉴스 목록으로 대신함. 지난 브리핑은 `archive/` 폴더에 쌓임.

- [ ] **Step 3: 전체 테스트** — Run: `.venv\Scripts\python -m pytest -q` → Expected: 전부 통과

- [ ] **Step 4: AI 없이 실제 수집 확인** — 키가 없어도 되는 부분을 먼저 실제 데이터로 확인한다: 임시 스크립트로 `collect(load_sources(), load_settings(), now)`와 `fetch_markets(...)`를 돌려 매체별 건수, 실패 매체, 시장 6종목을 출력한다. 기대: 실패 매체 3곳 이하, 전체 기사 300~600건, 시장 6종목 값이 나옴.

- [ ] **Step 5: 실제 데이터로 연습 실행 (사용자의 키 필요)** — 사용자가 자기 터미널에서 환경 변수를 설정한 뒤 `.venv\Scripts\python -m briefing --dry-run`을 돌린다. 키를 대화나 파일에 붙여 넣게 하지 않는다.
  확인할 것:
  - 브리핑 형식이 설계서 4장과 같은가.
  - 경제·IT 건수가 10 이하이고, 중국·일본·유럽 뉴스가 통과했다면 각 1건 이상 들어 있는가.
  - "왜 중요한가" 문장에 원문에 없는 숫자가 없는가(항목 3개를 원문 링크와 대조).
  - 로그의 토큰 사용량으로 하루 비용을 계산해 사용자에게 보고한다.

- [ ] **Step 6: 커밋** — `git commit -m "ci: daily schedule and setup guide"`

- [ ] **Step 7: 깃허브에 올리기 (사용자 확인 후)** — 비공개 저장소를 만들고 푸시하는 것은 바깥에 영향을 주는 일이므로, 저장소 이름을 사용자에게 확인받은 뒤 진행한다: `gh repo create <이름> --private --source . --push`. 비밀 값은 사용자가 깃허브 화면에서 직접 등록한다.

- [ ] **Step 8: 실제 전송 확인** — 사용자가 Actions 탭에서 Run workflow를 눌러 슬랙에 브리핑이 도착하는지, 저장소에 `archive/오늘날짜.md`와 `state/sent.json` 커밋이 생겼는지 확인한다. 한 번 더 눌러, 두 번째 실행에서도 브리핑이 비지 않는지(같은 날 재실행) 확인한다.

---

## 사용자 확인 사항

1. **AI를 어떤 방식으로 호출할지 (비용).** 구독과 API는 따로 결제된다.
   - API 방식(이 계획의 기본): 쓴 만큼 낸다. 하루 사용량을 입력 약 5만 토큰, 출력 약 2만 5천 토큰으로 어림잡으면 Haiku 5.5 약 월 1,000원, Sonnet 5.5 약 월 1만 5천 원, Opus 5.5 약 월 3만 원. Sonnet 5.5나 Opus 5.5로 바꿀 때는 `briefing/ai.py`에 안전 거부 시 대체 모델 설정(`fallbacks`)을 추가하는 작은 수정이 함께 필요하다.
   - 구독 계정 방식: 추가 요금 없이 구독 사용량에서 차감. 가능 여부와 조건을 확인 중이며, 채택하면 `briefing/ai.py`의 `make_ask_json`만 바뀐다.

2. **매체 4곳의 대체.** 로이터, AP, 차이신, NHK 월드는 톱뉴스 목록을 직접 구할 수 없어 구글 뉴스의 매체별 최신 목록으로 대신한다. "편집자가 고른 톱뉴스"가 아니라 "그 매체의 최근 기사"라는 차이가 있다.

3. **깃허브 저장소 이름**(Task 9 Step 7).
