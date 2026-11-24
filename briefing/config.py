"""설정 파일 읽기와 검증."""
import json

from pydantic import TypeAdapter

from briefing.models import Outlet, Settings


def load_sources(path: str = "config/sources.json") -> list[Outlet]:
    with open(path, encoding="utf-8") as f:
        outlets = TypeAdapter(list[Outlet]).validate_python(json.load(f))
    seen: set[str] = set()
    for o in outlets:
        if o.id in seen:
            raise ValueError(f"매체 id가 겹칩니다: {o.id}")
        seen.add(o.id)
    return outlets


def load_settings(path: str = "config/settings.json") -> Settings:
    with open(path, encoding="utf-8") as f:
        return Settings.model_validate(json.load(f))
