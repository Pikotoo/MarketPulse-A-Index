"""市场状态判定测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import():
    from api.signals.regime import get_regime
    assert callable(get_regime)


def test_basic():
    from api.signals.regime import get_regime
    r = get_regime(days=0)
    assert r["indicator"] == "regime"
    assert "label" in r


def test_regime_key():
    """regime 字段: bearish/neutral/bullish"""
    from api.signals.regime import get_regime
    r = get_regime(days=0)
    assert r.get("regime") in ("bearish", "neutral", "bullish")


def test_scores():
    from api.signals.regime import get_regime
    r = get_regime(days=0)
    for name in ["composite_score", "panic_score", "breadth_pct"]:
        assert name in r, f"缺失 {name}"
