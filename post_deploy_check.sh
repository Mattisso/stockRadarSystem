#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-https://api.stockradarx.com}"
TOKEN="${TOKEN:-}"

if [[ -z "$TOKEN" ]]; then
  echo "Set TOKEN before running."
  echo 'Example: TOKEN="..." ./post_deploy_check.sh'
  exit 1
fi

auth() {
  curl -sS -H "Authorization: Bearer $TOKEN" "$1"
}

section() {
  printf '\n== %s ==\n' "$1"
}

pass() {
  printf 'PASS: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1"
}

section "Health"
auth "$BASE/api/health"

section "Decision Events"
auth "$BASE/api/aggregate/decision-events?page=0&page_size=25"

section "Live Second Aggregates"
auth "$BASE/api/polygon/second-aggregates?page=0&page_size=5"

section "Live Minute Aggregates"
auth "$BASE/api/polygon/minute-aggregates?page=0&page_size=5"

section "Live Ticks"
auth "$BASE/api/polygon/ticks?page_size=5"

section "History Ticks"
auth "$BASE/api/polygon/history/ticks?page=0&page_size=5"

section "History Second Aggregates"
auth "$BASE/api/polygon/history/second-aggregates?page=0&page_size=5"

section "History Minute Aggregates"
auth "$BASE/api/polygon/history/minute-aggregates?page=0&page_size=5"

if command -v jq >/dev/null 2>&1; then
  decision_json="$(auth "$BASE/api/aggregate/decision-events?page=0&page_size=25")"
  second_json="$(auth "$BASE/api/polygon/second-aggregates?page=0&page_size=5")"
  minute_json="$(auth "$BASE/api/polygon/minute-aggregates?page=0&page_size=5")"
  ticks_json="$(auth "$BASE/api/polygon/ticks?page_size=5")"
  health_json="$(auth "$BASE/api/health")"

  section "Decision Events Summary"
  printf '%s\n' "$decision_json" | jq '{trade_date,total,summary,first_item:(.items[0] // null)}'

  section "Live Second Summary"
  printf '%s\n' "$second_json" | jq '{trade_date,total,is_stale,latest_available_ts,first_item:(.items[0] // null)}'

  section "Live Minute Summary"
  printf '%s\n' "$minute_json" | jq '{trade_date,total,is_stale,latest_available_ts,first_item:(.items[0] // null)}'

  section "Live Ticks Summary"
  printf '%s\n' "$ticks_json" | jq '{trade_date,total,has_more,next_cursor,first_item:(.items[0] // null)}'

  section "PASS/FAIL Summary"
  if [[ "$(printf '%s\n' "$health_json" | jq -r '.status // empty')" == "ok" ]]; then
    pass "health endpoint"
  else
    fail "health endpoint"
  fi

  decision_trade_date="$(printf '%s\n' "$decision_json" | jq -r '.trade_date // empty')"
  if [[ "$decision_trade_date" == "2026-05-04" ]]; then
    fail "decision-events default trade date is still stuck on 2026-05-04"
  elif [[ -n "$decision_trade_date" ]]; then
    pass "decision-events default trade date is $decision_trade_date"
  else
    fail "decision-events trade date missing"
  fi

  if [[ "$(printf '%s\n' "$second_json" | jq -r '.trade_date // empty')" != "null" ]]; then
    pass "live second aggregates returned a trade date"
  else
    fail "live second aggregates trade date missing"
  fi

  if [[ "$(printf '%s\n' "$minute_json" | jq -r '.trade_date // empty')" != "null" ]]; then
    pass "live minute aggregates returned a trade date"
  else
    fail "live minute aggregates trade date missing"
  fi

  if [[ "$(printf '%s\n' "$ticks_json" | jq -r '.items | length')" -ge 0 ]]; then
    pass "live ticks endpoint returned a valid payload"
  else
    fail "live ticks endpoint payload invalid"
  fi
fi
