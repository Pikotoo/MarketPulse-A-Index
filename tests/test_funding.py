"""流动性评分 + 资金情绪 + 跨资产测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ──── liquidity ────
def test_liquidity_import():
    from api.signals.liquidity import get_liquidity_score
    assert callable(get_liquidity_score)


def test_liquidity_basic():
    from api.signals.liquidity import get_liquidity_score
    r = get_liquidity_score(days=0)
    assert r["indicator"] == "liquidity_score"
    v = r.get("value")
    assert v is None or 0 <= v <= 100


# ──── fund_sentiment ────
def test_fund_import():
    from api.signals.fund_sentiment import get_fund_sentiment
    assert callable(get_fund_sentiment)


def test_fund_basic():
    from api.signals.fund_sentiment import get_fund_sentiment
    r = get_fund_sentiment(days=0)
    assert r["indicator"] == "fund_sentiment"
    v = r.get("value")
    assert v is None or 0 <= v <= 100


# ──── cross_asset ────
def test_cross_import():
    from api.signals.cross_asset import get_cross_asset
    assert callable(get_cross_asset)


def test_cross_basic():
    from api.signals.cross_asset import get_cross_asset
    r = get_cross_asset(days=0)
    assert r["indicator"] == "cross_asset"
    v = r.get("value")
    assert v is None or 0 <= v <= 100
