#!/usr/bin/env bash
# Bot data lives on the `data` branch, not on protected `main`.
#
#   data_branch.sh pull
#       Overlay data/ and reports/ from origin/data onto the working tree, so
#       the run reads and extends the latest bot data while code and config
#       come from the branch the workflow was started on.
#
#   data_branch.sh push "<commit message>" [--forbid <extended-regex>]
#       Commit this run's delta (workspace vs. what `pull` left) and push it to
#       origin/data: 3 tries, rebasing onto a concurrent writer. No change = no
#       commit. Needs a prior `pull` (it refuses otherwise: a push built from a
#       stale baseline would erase newer data). --forbid fails the push when a
#       changed path matches the regex (catch-up's picks.csv guard). A staged
#       change that looks like an API key or auth header also fails it: the
#       branch is public and its history is permanent. On any failure the
#       commit is saved as ${RUNNER_TEMP:-/tmp}/data-delta.patch so the
#       workflow can upload it (replay with `git am`).
#
#   data_branch.sh changed <path>
#       Exit 0 if <path> (e.g. data/ncaaf) differs between the workspace and the
#       pulled baseline, 1 if identical or absent on both sides. Fails open: a
#       diff error counts as changed.
#
# CLAUDE.md files in data/ and reports/ are docs owned by `main`; symlinks are
# never copied. Prerequisites: git, rsync, bash (all present on ubuntu-latest).
# Env: DATA_BRANCH (default data), DATA_WORKTREE (default .databranch).
set -euo pipefail

BRANCH="${DATA_BRANCH:-data}"
WT="${DATA_WORKTREE:-.databranch}"
DIRS=(data reports)
# --checksum: never trust size+mtime to skip a same-size edit made in the same second.
RSYNC=(rsync -a --no-links --checksum --delete --exclude=CLAUDE.md)
PATCH_OUT="${RUNNER_TEMP:-/tmp}/data-delta.patch"
# Added lines that must never reach the public branch.
SECRET_RE='(api[_-]?key|apikey)=[A-Za-z0-9]{16,}|authorization: *(bearer|basic) '

mode="${1:-}"
shift || true

open_worktree() {
  git fetch --quiet --depth=50 origin "$BRANCH"
  local sha
  sha="$(git rev-parse FETCH_HEAD)"
  git worktree prune
  if [ -e "$WT/.git" ]; then
    git -C "$WT" checkout --quiet --detach "$sha"
  else
    git worktree add --quiet --detach "$WT" "$sha"
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

  changed)
    path="${1:?path required}"
    if [ ! -e "$path" ] && [ ! -e "$WT/$path" ]; then exit 1; fi
    rc=0
    diff -rq -x CLAUDE.md "$WT/$path" "$path" >/dev/null 2>&1 || rc=$?
    if [ "$rc" -eq 0 ]; then exit 1; fi
    exit 0
    ;;

  push)
    msg="${1:?commit message required}"
    shift
    forbid=""
    if [ "${1:-}" = "--forbid" ]; then forbid="${2:?--forbid needs a regex}"; fi
    if [ ! -e "$WT/.git" ]; then
      echo "::error::data_branch.sh push needs a prior pull (no $WT worktree)"
      exit 1
    fi
    # The worktree still holds the pull baseline, so the commit is only this
    # run's delta; a concurrent writer's files survive the rebase.
    for d in "${DIRS[@]}"; do
      mkdir -p "$WT/$d"
      "${RSYNC[@]}" "$d/" "$WT/$d/"
    done
    git -C "$WT" add -A
    if git -C "$WT" diff --cached --quiet; then
      echo "No changes to commit."
      exit 0
    fi
    names="$(git -C "$WT" diff --cached --no-renames --name-only -z | tr '\0' '\n')"
    if [ -n "$forbid" ] && printf '%s\n' "$names" | grep -Eq -e "$forbid"; then
      echo "::error::refusing to commit a path matching $forbid"
      printf '%s\n' "$names" | grep -E -e "$forbid" || true
      exit 1
    fi
    added="$(git -C "$WT" diff --cached -U0 | grep -E '^\+[^+]' || true)"
    if printf '%s\n' "$added" | grep -Eiq -e "$SECRET_RE"; then
      echo "::error::staged data looks like it contains an API key or auth header; not pushing"
      exit 1
    fi
    git -C "$WT" config user.name "panthera-bot"
    git -C "$WT" config user.email "actions@users.noreply.github.com"
    git -C "$WT" commit --quiet -m "$msg"
    git -C "$WT" format-patch -1 --binary --stdout > "$PATCH_OUT"

    for attempt in 1 2 3; do
      if git -C "$WT" push --quiet origin "HEAD:refs/heads/$BRANCH"; then
        sha="$(git -C "$WT" rev-parse --short HEAD)"
        nfiles="$(printf '%s\n' "$names" | wc -l | tr -d ' ')"
        echo "data_branch: pushed to origin/$BRANCH@$sha ($nfiles files)"
        if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
          echo "data branch: pushed \`$sha\` ($nfiles files)" >> "$GITHUB_STEP_SUMMARY"
        fi
        # Lets a later step read steps.<id>.outputs.pushed.
        if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "pushed=true" >> "$GITHUB_OUTPUT"; fi
        exit 0
      fi
      if [ "$attempt" -eq 3 ]; then break; fi
      echo "push rejected (attempt $attempt); rebasing onto origin/$BRANCH"
      sleep $((attempt * 3))
      git -C "$WT" fetch --quiet --depth=50 origin "$BRANCH"
      if ! git -C "$WT" rebase --quiet FETCH_HEAD; then
        git -C "$WT" rebase --abort || true
        echo "::error::rebase onto origin/$BRANCH conflicted; delta saved to $PATCH_OUT"
        exit 1
      fi
    done
    echo "::error::could not push to origin/$BRANCH after 3 attempts; delta saved to $PATCH_OUT"
    exit 1
    ;;

  *)
    echo "usage: $0 pull | changed <path> | push \"<message>\" [--forbid <regex>]" >&2
    exit 2
    ;;
esac
