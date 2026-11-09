#!/usr/bin/env bash
# Bot data lives on the `data` branch, not on protected `main`.
#
#   data_branch.sh pull
#       Overlay data/ and reports/ from origin/data onto the working tree, so
#       the run reads and extends the latest bot data while code and config
#       come from the branch the workflow was started on.
#
#   data_branch.sh push "<commit message>" [--forbid <extended-regex>]
#       Copy data/ and reports/ back to origin/data and push (3 tries, rebasing
#       onto a concurrent writer). No change = no commit. --forbid fails the
#       push when a changed path matches the regex (catch-up's picks.csv guard).
#
# CLAUDE.md files in data/ and reports/ are docs owned by `main`; they are never
# copied in either direction. Env: DATA_BRANCH (default data), DATA_WORKTREE
# (default .databranch). Works locally too: run `pull` from a repo checkout.
set -euo pipefail

BRANCH="${DATA_BRANCH:-data}"
WT="${DATA_WORKTREE:-.databranch}"
DIRS=(data reports)
# --checksum: never trust size+mtime to skip a same-size edit made in the same second.
RSYNC=(rsync -a --checksum --delete --exclude=CLAUDE.md)

mode="${1:-}"
shift || true

open_worktree() {
  git fetch --quiet --depth=50 origin "$BRANCH"
  if [ -d "$WT/.git" ] || [ -f "$WT/.git" ]; then
    git -C "$WT" checkout --quiet --detach FETCH_HEAD
  else
    git worktree add --quiet --detach "$WT" FETCH_HEAD
  fi
}

case "$mode" in
  pull)
    open_worktree
    for d in "${DIRS[@]}"; do
      mkdir -p "$d"
      "${RSYNC[@]}" "$WT/$d/" "$d/"
    done
    echo "data_branch: overlaid ${DIRS[*]} from origin/$BRANCH@$(git -C "$WT" rev-parse --short HEAD)"
    ;;
  push)
    msg="${1:?commit message required}"
    shift
    forbid=""
    if [ "${1:-}" = "--forbid" ]; then forbid="${2:?--forbid needs a regex}"; fi
    # Commit on top of the tree `pull` left in $WT (the baseline), so the commit
    # holds only this run's delta; a concurrent writer's files survive the rebase.
    if [ ! -e "$WT/.git" ]; then open_worktree; fi
    for d in "${DIRS[@]}"; do
      mkdir -p "$WT/$d"
      "${RSYNC[@]}" "$d/" "$WT/$d/"
    done
    git -C "$WT" add -A
    if git -C "$WT" diff --cached --quiet; then
      echo "No changes to commit."
      exit 0
    fi
    if [ -n "$forbid" ] && git -C "$WT" diff --cached --name-only | grep -Eq "$forbid"; then
      echo "::error::refusing to commit a path matching $forbid"
      git -C "$WT" diff --cached --name-only | grep -E "$forbid"
      exit 1
    fi
    git -C "$WT" config user.name "panthera-bot"
    git -C "$WT" config user.email "actions@users.noreply.github.com"
    git -C "$WT" commit --quiet -m "$msg"
    for attempt in 1 2 3; do
      if git -C "$WT" push origin "HEAD:refs/heads/$BRANCH"; then
        echo "data_branch: pushed to origin/$BRANCH@$(git -C "$WT" rev-parse --short HEAD)"
        # Lets a step that wants to know if anything landed read steps.<id>.outputs.pushed.
        if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "pushed=true" >> "$GITHUB_OUTPUT"; fi
        exit 0
      fi
      echo "push rejected (attempt $attempt); rebasing onto origin/$BRANCH"
      git -C "$WT" fetch --quiet --depth=50 origin "$BRANCH"
      git -C "$WT" rebase "FETCH_HEAD"
    done
    echo "::error::could not push to origin/$BRANCH after 3 attempts"
    exit 1
    ;;
  *)
    echo "usage: $0 pull | push \"<message>\" [--forbid <regex>]" >&2
    exit 2
    ;;
esac
