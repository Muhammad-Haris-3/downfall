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
python collector/checkpoint.py >/dev/null
STATUS=$?
if [ "$STATUS" -eq 2 ]; then
  # Event loss, not a transient. Committing now would write the loss into the
  # permanent record and call it coverage. Fail the job so it is seen.
  echo "checkpoint reports event loss - failing the job rather than committing"
  python collector/checkpoint.py || true
  exit 1
fi
if [ "$STATUS" -ne 0 ]; then
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

# Push FIRST, and rebase only if it is refused.
#
# A rebase rewrites the working tree, and the collector is still writing to it.
# That is what destroyed five hours of collection once already: git replaced the
# event file, the collector's open handle followed the unlinked inode, and every
# subsequent write vanished (FINDINGS M1-T8b). The log now re-opens by name so
# it cannot be orphaned - but a rewrite it does not need is still a rewrite it
# should not have, and this collector is almost always the only writer, so the
# push almost always succeeds on its own.
#
# When a rebase IS needed it is still a rebase, not a merge: the event log is
# append-only, so a concurrent commit is a different set of lines at the end of
# a file and replays cleanly. A merge commit would be noise in a history that
# doubles as the audit log.
for attempt in 1 2 3; do
  if git push origin "HEAD:$BRANCH"; then
    echo "pushed ($MODE)"
    exit 0
  fi
  echo "push attempt $attempt refused; rebasing onto $BRANCH"
  git pull --rebase --autostash origin "$BRANCH" || true
  sleep 5
done

# A failed push is not a failed collection. The data is on disk and the next
# checkpoint will carry it, so this must not take the whole job down with it.
echo "could not push; leaving the commit for the next checkpoint"
exit 0
