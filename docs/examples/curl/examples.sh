#!/bin/bash
# MarketPulse API — curl 快速测试
# 使用方法: bash examples.sh

API_BASE="${API_BASE:-http://localhost:8898}"
API_KEY="${API_KEY:-mp-xxxxxxxx}"

echo "=========================================="
echo "  MarketPulse API 快速测试"
echo "  $API_BASE"
echo "=========================================="

# 1. 健康检查（不需要 Key）
echo ""
echo "--- 1. 健康检查 ---"
curl -s "$API_BASE/api/v1/health" | python3 -m json.tool 2>/dev/null || curl -s "$API_BASE/api/v1/health"

# 2. PE 分位
echo ""
echo "--- 2. PE 分位 ---"
curl -s -H "X-API-Key: $API_KEY" \
  "$API_BASE/api/v1/signal/pe-percentile" | python3 -m json.tool 2>/dev/null

# 3. ERP
echo ""
echo "--- 3. ERP 股债性价比 ---"
curl -s -H "X-API-Key: $API_KEY" \
  "$API_BASE/api/v1/signal/erp" | python3 -m json.tool 2>/dev/null

# 4. 宏观评分
echo ""
echo "--- 4. 宏观综合评分 ---"
curl -s -H "X-API-Key: $API_KEY" \
  "$API_BASE/api/v1/signal/macro-score" | python3 -m json.tool 2>/dev/null

# 5. 行业宽度
echo ""
echo "--- 5. 行业宽度 ---"
curl -s -H "X-API-Key: $API_KEY" \
  "$API_BASE/api/v1/signal/sector-breadth" | python3 -m json.tool 2>/dev/null

echo ""
echo "=========================================="
echo "  测试完成"
echo "=========================================="
