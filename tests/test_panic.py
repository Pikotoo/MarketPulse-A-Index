"""恐慌指数测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import():
    from api.signals.panic import get_panic_index
    assert callable(get_panic_index)


def test_basic():
    from api.signals.panic import get_panic_index
    r = get_panic_index(days=0)
    assert r["indicator"] == "panic_index"
    assert "value" in r
    v = r.get("value")
    assert v is None or 0 <= v <= 100


def test_components():
    from api.signals.panic import get_panic_index
    r = get_panic_index(days=0)
    comps = r.get("components", {})
    required = ["volatility_score", "dispersion_score", "breadth_score"]
    for name in required:
        assert name in comps, f"缺失 {name}"


def test_level():
    from api.signals.panic import get_panic_index
    r = get_panic_index(days=0)
    assert "level" in r
    assert "算法输出" not in r.get("level", ""), "残留[算法输出]前缀"


def test_history():
    from api.signals.panic import get_panic_index
    r = get_panic_index(days=90)
    assert "history" in r
