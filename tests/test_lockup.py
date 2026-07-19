"""限售解禁压力分测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import():
    from api.signals.lockup import get_lockup_pressure
    assert callable(get_lockup_pressure)


def test_single_value():
    from api.signals.lockup import get_lockup_pressure
    result = get_lockup_pressure(days=0)
    assert result["indicator"] == "lockup_pressure"
    assert "value" in result
    assert result.get("dimensions_valid", 0) >= 1


def test_value_range():
    from api.signals.lockup import get_lockup_pressure
    result = get_lockup_pressure(days=0)
    val = result.get("value")
    if val is not None:
        assert 0 <= val <= 100, f"值 {val} 超出0-100范围"


def test_history_mode():
    from api.signals.lockup import get_lockup_pressure
    result = get_lockup_pressure(days=30)
    assert "history" in result
    history = result["history"]
    assert isinstance(history, list)


def test_sub_scores():
    from api.signals.lockup import get_lockup_pressure
    result = get_lockup_pressure(days=0)
    sub = result.get("sub_scores", {})
    assert len(sub) == 3
    assert "volume_deviation" in sub
    assert "trend" in sub
    assert "vs_historical_ratio" in sub


def test_no_data_handling():
    """无数据时不崩溃"""
    from api.signals.lockup import get_lockup_pressure
    result = get_lockup_pressure(days=0)
    # 无论有无数据，均应返回合法结构
    assert "indicator" in result
    assert "value" in result
