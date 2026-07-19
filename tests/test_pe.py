"""PE分位测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import():
    from api.signals.pe import get_pe_signal
    assert callable(get_pe_signal)


def test_basic():
    from api.signals.pe import get_pe_signal
    r = get_pe_signal(days=0)
    assert "indicator" in r
    assert "value" in r
    v = r.get("value")
    assert v is None or 0 <= v <= 100


def test_history():
    from api.signals.pe import get_pe_signal
    r = get_pe_signal(days=90)
    assert "history" in r


def test_interpretation():
    from api.signals.pe import get_pe_signal
    r = get_pe_signal(days=0)
    assert "interpretation" in r
    assert "算法输出" not in r.get("interpretation", ""), "残留[算法输出]前缀"
