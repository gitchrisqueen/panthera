#!/usr/bin/env bash
# Validate workflow_dispatch inputs that were passed through `env:` (never interpolated
# into a run script). Usage: validate_inputs.sh NAME:kind [NAME:kind ...]
# Each NAME is an environment variable; empty is allowed. Kinds:
#   date    YYYY-MM-DD            week    1-99, no leading 0   year    19YY or 20YY
#   range   YYYY-YYYY            seasons YYYY or YYYY-YYYY (years 1900-2099)
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
    week) re='^[1-9][0-9]?$' ;;  # printf %02d reads a leading 0 as octal
    year) re='^(19|20)[0-9]{2}$' ;;
    range) re='^(19|20)[0-9]{2}-(19|20)[0-9]{2}$' ;;
    seasons) re='^(19|20)[0-9]{2}(-(19|20)[0-9]{2})?$' ;;
    *) echo "::error::unknown input kind '$kind' for $name"; exit 2 ;;
  esac
  if ! [[ "$value" =~ $re ]]; then
    echo "::error::input $name does not match the expected '$kind' format"
    fail=1
  fi
done
exit "$fail"
