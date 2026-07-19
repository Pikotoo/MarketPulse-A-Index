"""行业宽度测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import():
    from api.signals.sector import get_sector_breadth
    assert callable(get_sector_breadth)


def test_basic():
    from api.signals.sector import get_sector_breadth
    r = get_sector_breadth(days=0)
    assert r["indicator"] == "sector_breadth"
    v = r.get("value")
    assert v is None or 0 <= v <= 100


def test_above_ma60():
    from api.signals.sector import get_sector_breadth
    r = get_sector_breadth(days=0)
    standing = r.get("standing", {})
    n = standing.get("above_ma60", 0)
    total = standing.get("total", 32)
    assert 0 <= n <= total
    assert total == 32


def test_history():
    from api.signals.sector import get_sector_breadth
    r = get_sector_breadth(days=90)
    assert "history" in r
