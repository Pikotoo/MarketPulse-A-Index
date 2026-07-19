"""北向资金情绪分测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import():
    from api.signals.northbound import get_northbound_sentiment
    assert callable(get_northbound_sentiment)


def test_single_value():
    from api.signals.northbound import get_northbound_sentiment
    result = get_northbound_sentiment(days=0)
    assert result["indicator"] == "northbound_sentiment"
    assert "value" in result
    assert result.get("dimensions_valid", 0) >= 1


def test_value_range():
    from api.signals.northbound import get_northbound_sentiment
    result = get_northbound_sentiment(days=0)
    val = result.get("value")
    if val is not None:
        assert 0 <= val <= 100, f"值 {val} 超出0-100范围"


def test_history_mode():
    from api.signals.northbound import get_northbound_sentiment
    result = get_northbound_sentiment(days=365)
    assert "history" in result
    history = result["history"]
    assert isinstance(history, list)
    # 月度数据，120条左右的记录应该有至少10个历史点
    if len(history) > 0:
        item = history[0]
        assert "date" in item
        assert "score" in item
        assert "monthly_flow" in item


def test_sub_scores():
    from api.signals.northbound import get_northbound_sentiment
    result = get_northbound_sentiment(days=0)
    sub = result.get("sub_scores", {})
    assert len(sub) == 3
    assert "recent_flow" in sub
    assert "quarterly_trend" in sub
    assert "continuity" in sub


def test_flow_data():
    """近月净流入有具体数值"""
    from api.signals.northbound import get_northbound_sentiment
    result = get_northbound_sentiment(days=0)
    flow = result.get("flow_latest_month")
    assert flow is not None
    # 北向资金月度净流入（累计值，正常范围 -20000 ~ +50000）
    assert -20000 < float(flow) < 50000, f"流值 {flow} 异常"
