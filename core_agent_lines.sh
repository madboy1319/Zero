#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")" || exit 1

count_top_level_py_lines() {
  local dir="$1"
  if [ ! -d "$dir" ]; then
    echo 0
    return
  fi
  find "$dir" -maxdepth 1 -type f -name "*.py" -print0 | xargs -0 cat 2>/dev/null | wc -l | tr -d ' '
}

count_recursive_py_lines() {
  local dir="$1"
  if [ ! -d "$dir" ]; then
    echo 0
    return
  fi
  find "$dir" -type f -name "*.py" -print0 | xargs -0 cat 2>/dev/null | wc -l | tr -d ' '
}

count_skill_lines() {
  local dir="$1"
  if [ ! -d "$dir" ]; then
    echo 0
    return
  fi
  find "$dir" -type f \( -name "*.md" -o -name "*.py" -o -name "*.sh" \) -print0 | xargs -0 cat 2>/dev/null | wc -l | tr -d ' '
}

print_row() {
  local label="$1"
  local count="$2"
  printf "  %-16s %6s lines\n" "$label" "$count"
}

echo "zero line count"
echo "=================="
echo ""

echo "Core runtime"
echo "------------"
core_agent=$(count_top_level_py_lines "zero/agent")
core_bus=$(count_top_level_py_lines "zero/bus")
core_config=$(count_top_level_py_lines "zero/config")
core_cron=$(count_top_level_py_lines "zero/cron")
core_heartbeat=$(count_top_level_py_lines "zero/heartbeat")
core_session=$(count_top_level_py_lines "zero/session")

print_row "agent/" "$core_agent"
print_row "bus/" "$core_bus"
print_row "config/" "$core_config"
print_row "cron/" "$core_cron"
print_row "heartbeat/" "$core_heartbeat"
print_row "session/" "$core_session"

core_total=$((core_agent + core_bus + core_config + core_cron + core_heartbeat + core_session))

echo ""
echo "Separate buckets"
echo "----------------"
extra_tools=$(count_recursive_py_lines "zero/agent/tools")
extra_skills=$(count_skill_lines "zero/skills")
extra_api=$(count_recursive_py_lines "zero/api")
extra_cli=$(count_recursive_py_lines "zero/cli")
extra_channels=$(count_recursive_py_lines "zero/channels")
extra_utils=$(count_recursive_py_lines "zero/utils")

print_row "tools/" "$extra_tools"
print_row "skills/" "$extra_skills"
print_row "api/" "$extra_api"
print_row "cli/" "$extra_cli"
print_row "channels/" "$extra_channels"
print_row "utils/" "$extra_utils"

extra_total=$((extra_tools + extra_skills + extra_api + extra_cli + extra_channels + extra_utils))

echo ""
echo "Totals"
echo "------"
print_row "core total" "$core_total"
print_row "extra total" "$extra_total"

echo ""
echo "Notes"
echo "-----"
echo "  - agent/ only counts top-level Python files under zero/agent"
echo "  - tools/ is counted separately from zero/agent/tools"
echo "  - skills/ counts .md, .py, and .sh files"
echo "  - not included here: command/, providers/, security/, templates/, zero.py, root files"
