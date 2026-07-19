"""综合情绪分测试（v2.1 7维度）"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import():
    from api.signals.composite import get_composite_score
    assert callable(get_composite_score)


def test_single_value():
    from api.signals.composite import get_composite_score
    result = get_composite_score(days=0)
    assert result["indicator"] == "composite"
    assert "value" in result
    assert result.get("dimensions_valid", 0) >= 1


def test_seven_dimensions():
    """v2.1: 应包含7个维度"""
    from api.signals.composite import get_composite_score
    result = get_composite_score(days=0)
    assert result.get("dimensions_total") == 7, \
        f"预期7维，得到{result.get('dimensions_total')}维"

    comps = result.get("components", {})
    required = ["pe_score", "erp_score", "macro_score", "breadth_score",
                "margin_score", "northbound_score", "volume_score"]
    for r in required:
        assert r in comps, f"缺失 {r} 维度"


def test_value_range():
    from api.signals.composite import get_composite_score
    result = get_composite_score(days=0)
    val = result.get("value")
    if val is not None:
        assert 0 <= val <= 100, f"值 {val} 超出0-100范围"


def test_history_mode():
    from api.signals.composite import get_composite_score
    result = get_composite_score(days=90)
    assert "history" in result
    history = result["history"]
    assert isinstance(history, list)
    if len(history) > 0:
        item = history[0]
        assert "date" in item
        assert "score" in item


def test_all_components_have_values():
    """所有7个组件都有值或显式为null"""
    from api.signals.composite import get_composite_score
    result = get_composite_score(days=0)
    comps = result.get("components", {})
    assert len(comps) == 7
    # v2.1: 新增的3个维度应该有有效值（数据文件已存在）
    for name in ["margin_score", "northbound_score", "volume_score"]:
        assert comps[name] is not None, \
            f"{name} 为None，数据文件可能缺失"
