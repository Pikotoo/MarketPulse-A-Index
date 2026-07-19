"""融资融券情绪分测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import():
    """模块可导入"""
    from api.signals.margin import get_margin_sentiment
    assert callable(get_margin_sentiment)


def test_single_value():
    """单值模式返回正确结构"""
    from api.signals.margin import get_margin_sentiment
    result = get_margin_sentiment(days=0)
    assert result["indicator"] == "margin_sentiment"
    assert "value" in result
    assert "range" in result
    assert "sub_scores" in result
    # 应有3个子指标
    sub = result["sub_scores"]
    assert len(sub) == 3
    # 至少1维有效
    assert result.get("dimensions_valid", 0) >= 1


def test_value_range():
    """分数在0-100范围内"""
    from api.signals.margin import get_margin_sentiment
    result = get_margin_sentiment(days=0)
    val = result.get("value")
    if val is not None:
        assert 0 <= val <= 100, f"值 {val} 超出0-100范围"


def test_history_mode():
    """历史模式返回history数组"""
    from api.signals.margin import get_margin_sentiment
    result = get_margin_sentiment(days=30)
    assert result["indicator"] == "margin_sentiment"
    assert "history" in result
    history = result["history"]
    assert isinstance(history, list)
    if len(history) > 0:
        item = history[0]
        assert "date" in item
        assert "score" in item


def test_interpretation():
    """解读文本非空"""
    from api.signals.margin import get_margin_sentiment
    result = get_margin_sentiment(days=0)
    interp = result.get("interpretation")
    if result.get("value") is not None:
        assert interp is not None and len(interp) > 0
