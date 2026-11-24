"""공용 자료형. 모든 단계가 여기서 가져다 쓴다."""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

OutletRegion = Literal["KR", "US", "UK", "CN", "JP", "EU"]
TopicRegion = Literal["KR", "US", "CN", "JP", "EU", "OTHER"]
Category = Literal["econ_it", "general"]
Tier = Literal["major", "medium", "routine"]
Continuity = Literal["new", "ongoing_progress", "ongoing_no_progress"]


class Outlet(BaseModel):
    id: str
    name: str
    region: OutletRegion
    feeds: list[str] = Field(min_length=1)
    max_items: int = Field(gt=0)
    google_news: bool = False


class MarketSpec(BaseModel):
    label: str
    symbol: str
    unit: Literal["index", "krw", "pct"]


class GeneralRule(BaseModel):
    min_outlets: int
    min_regions: int
    kr_min_outlets: int
    max: int


class EconRule(BaseModel):
    max: int
    guaranteed_regions: list[TopicRegion]


class Settings(BaseModel):
    model: str
    window_hours: int
    general: GeneralRule
    econ: EconRule
    history_days: int
    markets: list[MarketSpec]


@dataclass(frozen=True)
class Article:
    id: str
    outlet_id: str
    title: str
    summary: str
    url: str
    published_at: datetime | None  # 시간대 정보가 있는 UTC


@dataclass
class NewsEvent:
    key: str  # "e1", "e2", ... 한 번의 실행 안에서만 유일
    label: str
    article_ids: list[str]
    category: Category
    region: TopicRegion  # 사건이 일어난 곳
    domestic_kr: bool
    tier: Tier | None  # econ_it만 값이 있다
    continuity: Continuity


@dataclass(frozen=True)
class RankedItem:
    event_key: str
    rank: int
    title_ko: str
    why_ko: str


@dataclass(frozen=True)
class BriefingItem:
    title_ko: str
    why_ko: str
    region: TopicRegion
    ongoing: bool
    outlet_names: list[str]
    url: str


@dataclass(frozen=True)
class MarketQuote:
    label: str
    unit: str
    value: float
    change_pct: float
    date: str  # YYYY-MM-DD


@dataclass(frozen=True)
class SentRecord:
    date: str
    title_ko: str
    why_ko: str
