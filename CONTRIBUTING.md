# 贡献指南

欢迎贡献！以下是添加新信号模块的步骤。

## 添加新信号

### 1. 创建信号模块 `api/signals/new_signal.py`

```python
"""新信号说明"""

def get_new_signal(days: int = 0) -> dict:
    """返回 {indicator, value, range, interpretation, ...}"""
    if days > 0:
        return _history(days)
    return _latest()

def _latest() -> dict:
    # 计算最新值
    score = ...
    return {
        "indicator": "new_signal",
        "value": score,
        "range": "0-100",
        "interpretation": _interpret(score),
        "as_of_date": date.today().isoformat(),
    }

def _interpret(score: float) -> str:
    if score < 20: return "[算法输出] ..."
    # ...

def _history(days: int) -> dict:
    # 历史回算
    return {"indicator": "new_signal", "history": [...]}
```

### 2. 注册端点 `api/app.py`

```python
@app.route("/api/v1/signal/new-signal")
@audit_trail
@require_api_key
@signal_endpoint
def signal_new():
    from api.signals.new_signal import get_new_signal
    return _cached_signal("new_signal", lambda days=0: get_new_signal(days=days), _get_days())
```

### 3. 加入预计算 `scripts/update_signals.py`

在 SIGNALS 列表中加入 `"new_signal"`。

### 4. 写测试 `tests/test_new_signal.py`

```python
def test_single_value():
    from api.signals.new_signal import get_new_signal
    result = get_new_signal(days=0)
    assert "value" in result
    assert 0 <= result["value"] <= 100
```

## 代码风格

- 遵循现有装饰器模式
- 所有 API 响应通过 `api_response()` 包装
- 解读文案以 `[算法输出]` 开头
- 优先使用 `day_reader` 统一读取 `.day` 文件
