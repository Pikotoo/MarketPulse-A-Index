"""量能分测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import():
    from api.signals.volume import get_volume_score
    assert callable(get_volume_score)


def test_single_value():
    from api.signals.volume import get_volume_score
    result = get_volume_score(days=0)
    assert result["indicator"] == "volume_score"
    assert "value" in result
    assert result.get("dimensions_valid", 0) >= 1


def test_value_range():
    from api.signals.volume import get_volume_score
    result = get_volume_score(days=0)
    val = result.get("value")
    if val is not None:
        assert 0 <= val <= 100, f"值 {val} 超出0-100范围"


def test_history_mode():
    from api.signals.volume import get_volume_score
    result = get_volume_score(days=30)
    assert "history" in result
    history = result["history"]
    assert isinstance(history, list)


def test_sub_scores():
    from api.signals.volume import get_volume_score
    result = get_volume_score(days=0)
    sub = result.get("sub_scores", {})
    assert len(sub) == 3
    assert "amount_deviation" in sub
    assert "amount_trend" in sub
    assert "vol_price_health" in sub
