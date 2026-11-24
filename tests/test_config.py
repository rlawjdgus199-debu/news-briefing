import json

import pytest
from pydantic import ValidationError

from briefing.config import load_settings, load_sources


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


def test_unknown_region_is_rejected():
    with pytest.raises(ValidationError, match="region"):
        load_sources("tests/fixtures/bad-sources.json")


def test_duplicate_outlet_id_is_rejected(tmp_path):
    one = {"id": "x", "name": "X", "region": "US", "max_items": 5, "google_news": False, "feeds": ["u"]}
    p = tmp_path / "s.json"
    p.write_text(json.dumps([one, one]), encoding="utf-8")
    with pytest.raises(ValueError, match="x"):
        load_sources(str(p))
