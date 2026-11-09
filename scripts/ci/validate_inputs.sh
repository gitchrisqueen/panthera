#!/usr/bin/env bash
# Validate workflow_dispatch inputs that were passed through `env:` (never interpolated
# into a run script). Usage: validate_inputs.sh NAME:kind [NAME:kind ...]
# Each NAME is an environment variable; empty is allowed. Kinds:
#   date    YYYY-MM-DD            week    1-2 digits         year    YYYY
#   range   YYYY-YYYY            seasons YYYY or YYYY-YYYY
# Exit 1 on the first value that does not match, naming the variable but not echoing
# the value into a workflow command.
set -euo pipefail

fail=0
for spec in "$@"; do
  name="${spec%%:*}"
  kind="${spec#*:}"
  value="${!name:-}"
  [ -z "$value" ] && continue
  case "$kind" in
    date) re='^[0-9]{4}-[0-9]{2}-[0-9]{2}$' ;;
    week) re='^[0-9]{1,2}$' ;;
    year) re='^[0-9]{4}$' ;;
    range) re='^[0-9]{4}-[0-9]{4}$' ;;
    seasons) re='^[0-9]{4}(-[0-9]{4})?$' ;;
    *) echo "::error::unknown input kind '$kind' for $name"; exit 2 ;;
  esac
  if ! [[ "$value" =~ $re ]]; then
    echo "::error::input $name does not match the expected '$kind' format"
    fail=1
  fi
done
exit "$fail"
