#!/bin/bash
# Monitor Buddhist text summary generation progress

LOG_FILE="summary_generation.log"
OUTPUT_FILE="source_data/source_summaries_ko.json"

echo "📊 Buddhist Text Summary Generation - Progress Monitor"
echo "========================================================="
echo ""

# Check if process is running
if pgrep -f "python3 generate_summaries.py" > /dev/null; then
    echo "✅ Status: RUNNING"
    PROCESS_ID=$(pgrep -f "python3 generate_summaries.py")
    echo "🔢 Process ID: $PROCESS_ID"
else
    echo "❌ Status: NOT RUNNING"
fi

echo ""
echo "📈 Progress:"
echo "------------"

# Get latest progress from log
LATEST_PROGRESS=$(tail -100 "$LOG_FILE" | grep -E "Processing|Checkpoint" | tail -1)
echo "$LATEST_PROGRESS"

# Count completed summaries from JSON
if [ -f "$OUTPUT_FILE" ]; then
    COMPLETED=$(python3 -c "
import json
try:
    with open('$OUTPUT_FILE', 'r') as f:
        data = json.load(f)
        count = data.get('summaries_generated', 0)
        total = data.get('total_sources', 2410)
        pct = (count / total * 100) if total > 0 else 0
        print(f'{count}/{total} summaries ({pct:.1f}%)')
except:
    print('Unable to read progress')
" 2>/dev/null)
    echo "💾 Saved: $COMPLETED"
fi

# Count errors
ERROR_COUNT=$(grep -c "ERROR" "$LOG_FILE" 2>/dev/null || echo "0")
echo "⚠️  Errors: $ERROR_COUNT"

# Estimate time remaining
CURRENT_COUNT=$(tail -100 "$LOG_FILE" | grep -oE "\[[0-9]+/2410\]" | tail -1 | grep -oE "[0-9]+" | head -1)
if [ ! -z "$CURRENT_COUNT" ]; then
    REMAINING=$((2410 - CURRENT_COUNT))
    # At 5 req/sec with rate limit
    SECONDS_LEFT=$((REMAINING / 5))
    MINUTES_LEFT=$((SECONDS_LEFT / 60))
    echo "⏱️  Estimated time remaining: ~$MINUTES_LEFT minutes"
fi

echo ""
echo "📝 Recent activity (last 10 lines):"
echo "------------------------------------"
tail -10 "$LOG_FILE" | grep -E "INFO.*Processing|ERROR"

echo ""
echo "💡 Commands:"
echo "   Watch live: tail -f $LOG_FILE"
echo "   Stop process: pkill -f 'python3 generate_summaries.py'"
echo "   View results: cat $OUTPUT_FILE | python3 -m json.tool | head -50"
