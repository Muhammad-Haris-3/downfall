#!/usr/bin/env bash
#
# Commit whatever the collector has written so far, and push it.
#
# Called two ways:
#   checkpoint   mid-run, every 30 minutes, while the collector is still writing
#   final        after the collector exits, when data/runs.ndjson has its row
#
# Kept as a script rather than inline YAML because it is the part most likely to
# need fixing at an awkward moment, and a shell script in a file can be run and
# read on its own.
set -uo pipefail

MODE="${1:-final}"
BRANCH="${GITHUB_REF_NAME:-main}"

# A torn last line in an append-only log is unrecoverable - the next write lands
# on the same row and both records are lost. checkpoint.py waits for every file
# to end on a line boundary and refuses if one does not. Skipping a checkpoint
# costs nothing: the data is still on disk and goes in the next one.
if ! python collector/checkpoint.py >/dev/null; then
  echo "checkpoint refused - not committing a torn file"
  exit 0
fi

git add data/
if git diff --cached --quiet; then
  echo "nothing new to commit"
  exit 0
fi

if [ "$MODE" = "final" ] && [ -s data/runs.ndjson ]; then
  python collector/summarise_run.py > /tmp/msg.txt
else
  python collector/checkpoint.py --message > /tmp/msg.txt
fi
git commit -F /tmp/msg.txt

# Rebase rather than merge: the event log is append-only, so a concurrent commit
# is always a different set of lines at the end of a file and replays cleanly.
# A merge commit here would be noise in a history that doubles as the audit log.
for attempt in 1 2 3; do
  if git pull --rebase --autostash origin "$BRANCH"; then
    break
  fi
  echo "rebase attempt $attempt failed, retrying"
  sleep 5
done

for attempt in 1 2 3; do
  if git push origin "HEAD:$BRANCH"; then
    echo "pushed ($MODE)"
    exit 0
  fi
  echo "push attempt $attempt failed, retrying"
  sleep 5
  git pull --rebase --autostash origin "$BRANCH" || true
done

# A failed push is not a failed collection. The data is on disk and the next
# checkpoint will carry it, so this must not take the whole job down with it.
echo "could not push; leaving the commit for the next checkpoint"
exit 0
