"""ERP股权风险溢价测试"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import():
    from api.signals.erp import get_erp_signal
    assert callable(get_erp_signal)


def test_basic():
    from api.signals.erp import get_erp_signal
    r = get_erp_signal(days=0)
    assert "indicator" in r
    assert "value" in r
    v = r.get("value")
    assert v is None or -5 <= v <= 20


def test_history():
    from api.signals.erp import get_erp_signal
    r = get_erp_signal(days=90)
    assert "history" in r
