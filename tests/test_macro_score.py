"""宏观评分测试（v2.1 9维度）"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import():
    from api.signals.macro_score import get_macro_score
    assert callable(get_macro_score)


def test_single_value():
    from api.signals.macro_score import get_macro_score
    result = get_macro_score(days=0)
    assert result["indicator"] == "macro_score"
    assert "value" in result
    assert result.get("dimensions_valid", 0) >= 1


def test_nine_dimensions():
    """v2.1: 应包含9个维度"""
    from api.signals.macro_score import get_macro_score
    result = get_macro_score(days=0)
    assert result.get("dimensions_total") == 9, \
        f"预期9维，得到{result.get('dimensions_total')}维"

    sub = result.get("sub_scores", {})
    # 6原始 + 3 v2.1新增 = 9
    assert "m2" in sub
    assert "pmi" in sub
    assert "cpi" in sub
    assert "shibor" in sub
    assert "spread" in sub
    assert "rmb" in sub
    assert "ppi" in sub, "v2.1 PPI维度缺失"
    assert "m1m2" in sub, "v2.1 M1-M2剪刀差维度缺失"
    assert "fdi" in sub, "v2.1 FDI维度缺失"


def test_value_range():
    from api.signals.macro_score import get_macro_score
    result = get_macro_score(days=0)
    val = result.get("value")
    if val is not None:
        assert 0 <= val <= 100, f"值 {val} 超出0-100范围"


def test_history_mode():
    from api.signals.macro_score import get_macro_score
    result = get_macro_score(days=180)
    assert "history" in result
    history = result["history"]
    assert isinstance(history, list)
    if len(history) > 0:
        item = history[0]
        assert "date" in item
        assert "score" in item


def test_new_dimensions_return_data():
    """v2.1新增维度应有数据或明确标注不可用"""
    from api.signals.macro_score import get_macro_score
    result = get_macro_score(days=0)
    sub = result.get("sub_scores", {})

    for dim in ["ppi", "m1m2", "fdi"]:
        s = sub.get(dim, {})
        # 至少要有结构（value/score/note之一）
        assert "value" in s or "note" in s, f"{dim} 子分数结构不完整"
