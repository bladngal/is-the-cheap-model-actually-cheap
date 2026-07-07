#!/bin/bash
# Usage: run_one.sh <mode> <model> <rep>
set -u
EXP="$(cd "$(dirname "$0")" && pwd)"
MODE="$1"; MODEL="$2"; REP="$3"
WORK="$EXP/runs/$MODE/${MODEL}-rep${REP}"
RESULT="$EXP/results/${MODE}__${MODEL}__rep${REP}.json"
mkdir -p "$WORK" "$EXP/results"

# fresh fixture copy
case "$MODE" in
  coding)      cp -R "$EXP/fixtures/coding/." "$WORK/" ;;
  coding-hard) cp -R "$EXP/fixtures/coding-hard/." "$WORK/" ;;
  data)        cp "$EXP/fixtures/data/sales_data.csv" "$WORK/" ;;
esac

case "$MODE" in
  qa)          CAP=2 ;;
  writing)     CAP=3 ;;
  data)        CAP=6 ;;
  coding)      CAP=15 ;;
  coding-hard) CAP=15 ;;
esac

PROMPT="$(cat "$EXP/prompts/$MODE.txt")"

cd "$WORK" || exit 1
START=$(date +%s)
claude -p "$PROMPT" \
  --model "$MODEL" \
  --effort high \
  --safe-mode \
  --output-format json \
  --permission-mode acceptEdits \
  --allowedTools "Bash TodoWrite Task" \
  --max-budget-usd "$CAP" \
  > "$RESULT" 2> "$EXP/results/${MODE}__${MODEL}__rep${REP}.stderr"
EXIT=$?
END=$(date +%s)

# verification
VERIFY="n/a"
case "$MODE" in
  coding|coding-hard)
    if python3 -m unittest discover -s tests > /dev/null 2>&1; then VERIFY="pass"; else VERIFY="FAIL"; fi ;;
  data)
    if [ -s cleaned_sales.csv ] && [ -s summary.md ]; then VERIFY="pass"; else VERIFY="FAIL"; fi ;;
  writing)
    if [ -s article.md ]; then VERIFY="pass"; else VERIFY="FAIL"; fi ;;
esac

echo "{\"mode\":\"$MODE\",\"model\":\"$MODEL\",\"rep\":$REP,\"exit\":$EXIT,\"wall_s\":$((END-START)),\"verify\":\"$VERIFY\"}" >> "$EXP/results/manifest.jsonl"
echo "DONE $MODE $MODEL rep$REP exit=$EXIT wall=$((END-START))s verify=$VERIFY"
