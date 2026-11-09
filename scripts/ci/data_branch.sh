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
#       origin/data: 3 push attempts, rebasing onto a concurrent writer between
#       them. No change = no commit. Needs a prior `pull` (it refuses
#       otherwise: a push built from a stale baseline would erase newer data).
#       Refused before committing, so no patch is saved: a path matching
#       --forbid (catch-up's picks.csv guard), a credential-looking filename,
#       or added text that looks like an API key, an auth header, or the value
#       of ODDS_API_KEY / LUMIFY_API_KEY / CFBD_API_KEY in the environment (the
#       branch is public and its history is permanent). If the push step fails
#       AFTER the commit, the commit is saved as ${RUNNER_TEMP:-/tmp}/data-delta.patch
#       and the workflows upload it (replay with `git am`).
#
#   data_branch.sh changed <path>
#       Exit 0 if <path> (e.g. data/ncaaf) differs between the workspace and the
#       pulled baseline, 1 if identical or absent on both sides. Fails open: a
#       diff error counts as changed.
#
# CLAUDE.md files in data/ and reports/ are docs owned by `main`; symlinks are
# never copied. Prerequisites: git, rsync, bash (all present on ubuntu-latest).
# Env: DATA_BRANCH (default data, never main), DATA_WORKTREE (default .databranch).
set -euo pipefail

BRANCH="${DATA_BRANCH:-data}"
WT="${DATA_WORKTREE:-.databranch}"
DIRS=(data reports)
# --checksum: never trust size+mtime to skip a same-size edit made in the same second.
RSYNC=(rsync -a --no-links --checksum --delete --exclude=CLAUDE.md)
PATCH_OUT="${RUNNER_TEMP:-/tmp}/data-delta.patch"
# Added text that must never reach the public branch: key=value / key: value in
# plain, JSON, repr or URL-encoded form, and bearer/basic auth headers.
SECRET_RE='(api[_-]?key|apikey)["'"'"']?([ ]*[=:]|%3[dD])[ ]*["'"'"']?[A-Za-z0-9_-]{16,}'
SECRET_RE+='|authorization["'"'"']?[ ]*[:=][ ]*["'"'"']?(bearer|basic) '
# Filenames that mean a credential was swept into data/ or reports/.
CRED_NAME_RE='(^|/)(\.env[^/]*|\.netrc|\.npmrc|id_[a-z0-9]+|credentials[^/]*\.json'
CRED_NAME_RE+='|service-account[^/]*\.json|[^/]*\.(pem|key|p12|pfx|p8|jks))$'

if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  echo "::error::DATA_BRANCH must not be a code branch"
  exit 2
fi

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
  # rsync would follow a top-level symlink on the data branch out of the repo.
  if [ -L "$WT/data" ] || [ -L "$WT/reports" ]; then
    echo "::error::origin/$BRANCH has a symlink where data/ or reports/ should be; not using it"
    exit 1
  fi
}

# safe_names: echo file names without anything the runner could read as a workflow command
# (a name may hold a newline followed by ::error::); every unusual byte becomes '?'.
safe_names() { sed 's/[^[:alnum:]\/._-]/?/g; s/^/  /'; }

# files_with <regex|fixed> <pattern>: the staged files whose ADDED text matches, names only
# (never the matching text), so a refusal says where to look without leaking the value.
files_with() {
  local kind="$1" pat="$2" f
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    git -C "$WT" diff --cached -U0 --text --no-ext-diff --no-textconv -- "$f" 2>/dev/null \
      | grep -aE '^\+' > "$scratch/one" || true
    if [ "$kind" = regex ]; then
      grep -aEiq -e "$pat" "$scratch/one" && echo "$f" || true
    else
      grep -aFq -e "$pat" "$scratch/one" && echo "$f" || true
    fi
  done < "$scratch/names" | safe_names
  echo "  (if the list is empty the name could not be resolved; inspect the staged diff in the data worktree)"
}

# match_file <regex> <file> [grep flags]: 0 = match, 1 = no match; any other
# grep status (bad regex, I/O) aborts the push. Reads a file, never a pipe, so
# an early grep exit cannot raise SIGPIPE and turn a match into "no match".
match_file() {
  local rc=0
  grep -aE "${3:--q}" -e "$1" "$2" >/dev/null 2>&1 || rc=$?
  if [ "$rc" -gt 1 ]; then
    echo "::error::grep failed (status $rc) on a safety check; not pushing"
    exit 1
  fi
  return "$rc"
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
    diff -rq -x CLAUDE.md -- "$WT/$path" "$path" >/dev/null 2>&1 || rc=$?
    if [ "$rc" -eq 0 ]; then exit 1; fi
    exit 0
    ;;

  push)
    msg="${1:?commit message required}"
    shift
    forbid=""
    if [ "$#" -gt 0 ]; then
      if [ "$1" != "--forbid" ] || [ "$#" -ne 2 ]; then
        echo "::error::unknown arguments to push: $*"
        exit 2
      fi
      forbid="$2"
      rc=0
      printf '' | grep -E -e "$forbid" >/dev/null 2>&1 || rc=$?
      if [ "$rc" -gt 1 ]; then
        echo "::error::--forbid is not a valid extended regex: $forbid"
        exit 2
      fi
    fi
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

    scratch="$(mktemp -d)"
    trap 'rm -rf "$scratch"' EXIT
    git -C "$WT" diff --cached --no-renames --name-only -z | tr '\0' '\n' > "$scratch/names"
    # To a file first: a failing git diff must abort (set -e), not leave an empty scan input.
    git -C "$WT" diff --cached -U0 --text --no-ext-diff --no-textconv > "$scratch/diff"
    rc=0
    grep -aE '^\+' "$scratch/diff" > "$scratch/added" || rc=$?
    if [ "$rc" -gt 1 ]; then echo "::error::could not scan the staged diff"; exit 1; fi

    if [ -n "$forbid" ] && match_file "$forbid" "$scratch/names"; then
      echo "::error::refusing to commit a path matching $forbid"
      grep -E -e "$forbid" "$scratch/names" | safe_names || true
      exit 1
    fi
    if match_file "$CRED_NAME_RE" "$scratch/names" -qi; then
      echo "::error::refusing to commit a credential-looking filename"
      grep -Ei -e "$CRED_NAME_RE" "$scratch/names" | safe_names || true
      exit 1
    fi
    if match_file "$SECRET_RE" "$scratch/added" -qi; then
      echo "::error::staged data looks like it contains an API key or auth header; not pushing"
      echo "files to read (names only):"
      files_with regex "$SECRET_RE"
      exit 1
    fi
    for var in ODDS_API_KEY LUMIFY_API_KEY CFBD_API_KEY; do
      val="${!var:-}"
      val="${val%%$'\n'*}"
      if [ "${#val}" -ge 8 ] && grep -aFq -e "$val" "$scratch/added"; then
        echo "::error::staged data contains the value of $var; not pushing"
        echo "files to read (names only):"
        files_with fixed "$val"
        exit 1
      fi
    done

    # Env identity, not `git config`: a linked worktree would rewrite the shared repo config, and
    # the rebase below also needs a committer (runners have none).
    export GIT_AUTHOR_NAME=panthera-bot GIT_COMMITTER_NAME=panthera-bot
    export GIT_AUTHOR_EMAIL=actions@users.noreply.github.com GIT_COMMITTER_EMAIL=actions@users.noreply.github.com
    git -C "$WT" commit --quiet -m "$msg"
    git -C "$WT" format-patch -1 --binary --stdout > "$PATCH_OUT"
    nfiles="$(wc -l < "$scratch/names" | tr -d ' ')"

    for attempt in 1 2 3; do
      if git -C "$WT" push --quiet origin "HEAD:refs/heads/$BRANCH"; then
        sha="$(git -C "$WT" rev-parse --short HEAD)"
        echo "data_branch: pushed to origin/$BRANCH@$sha ($nfiles files)"
        if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
          echo "data branch: pushed \`$sha\` ($nfiles files)" >> "$GITHUB_STEP_SUMMARY"
        fi
        # Lets a later step read steps.<id>.outputs.pushed.
        if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "pushed=true" >> "$GITHUB_OUTPUT"; fi
        # The data is on origin now: a later failing step must not upload a patch to replay.
        rm -f "$PATCH_OUT"
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
