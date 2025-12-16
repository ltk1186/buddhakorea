#!/bin/bash
# Buddha Korea RAG - Usage Stats Checker

echo "🔍 Buddha Korea RAG - 사용량 통계"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if usage.jsonl exists
if [ ! -f "logs/usage.jsonl" ]; then
    echo -e "${RED}❌ logs/usage.jsonl 파일이 없습니다.${NC}"
    echo "아직 쿼리가 실행되지 않았거나 로그 파일이 생성되지 않았습니다."
    exit 1
fi

# Count total queries
TOTAL_QUERIES=$(wc -l < logs/usage.jsonl | tr -d ' ')
echo -e "${BLUE}총 쿼리 수:${NC} $TOTAL_QUERIES"
echo ""

# Show recent 5 queries with costs
echo -e "${GREEN}최근 5개 쿼리:${NC}"
echo "────────────────────────────────────────────────────────────────"

tail -5 logs/usage.jsonl | while read -r line; do
    QUERY=$(echo "$line" | python3 -c "import sys, json; print(json.load(sys.stdin)['query'][:50])" 2>/dev/null || echo "N/A")
    MODE=$(echo "$line" | python3 -c "import sys, json; print(json.load(sys.stdin)['mode'])" 2>/dev/null || echo "N/A")
    MODEL=$(echo "$line" | python3 -c "import sys, json; print(json.load(sys.stdin)['model'])" 2>/dev/null || echo "N/A")
    INPUT_TOKENS=$(echo "$line" | python3 -c "import sys, json; print(json.load(sys.stdin)['tokens']['input'])" 2>/dev/null || echo "0")
    OUTPUT_TOKENS=$(echo "$line" | python3 -c "import sys, json; print(json.load(sys.stdin)['tokens']['output'])" 2>/dev/null || echo "0")
    COST=$(echo "$line" | python3 -c "import sys, json; print(json.load(sys.stdin)['cost_usd'])" 2>/dev/null || echo "0")

    echo -e "${YELLOW}Query:${NC} $QUERY..."
    echo -e "${YELLOW}Mode:${NC} $MODE | ${YELLOW}Model:${NC} $MODEL"
    echo -e "${YELLOW}Tokens:${NC} ${INPUT_TOKENS}in + ${OUTPUT_TOKENS}out | ${YELLOW}Cost:${NC} \$$COST"
    echo ""
done

# Calculate total cost
echo "────────────────────────────────────────────────────────────────"
TOTAL_COST=$(cat logs/usage.jsonl | python3 -c "
import sys, json
total = sum(json.loads(line)['cost_usd'] for line in sys.stdin)
print(f'{total:.6f}')
" 2>/dev/null || echo "0.000000")

echo -e "${GREEN}총 비용:${NC} \$$TOTAL_COST USD"
echo ""

# Show mode breakdown
echo -e "${GREEN}모드별 통계:${NC}"
cat logs/usage.jsonl | python3 -c "
import sys, json
from collections import defaultdict

stats = defaultdict(lambda: {'queries': 0, 'cost': 0.0, 'tokens': 0})

for line in sys.stdin:
    try:
        data = json.loads(line)
        mode = data['mode']
        stats[mode]['queries'] += 1
        stats[mode]['cost'] += data['cost_usd']
        stats[mode]['tokens'] += data['tokens']['total']
    except:
        continue

for mode, data in sorted(stats.items()):
    avg_cost = data['cost'] / data['queries'] if data['queries'] > 0 else 0
    print(f'  {mode}: {data[\"queries\"]}회 | \${data[\"cost\"]:.6f} | 평균: \${avg_cost:.6f}/query')
" 2>/dev/null

echo ""
echo "=================================="
echo -e "${BLUE}💡 API 엔드포인트로 자세한 통계 확인:${NC}"
echo "   curl http://localhost:8000/api/usage-stats?days=7"
echo "   curl http://localhost:8000/api/recent-queries?limit=10"
echo ""
