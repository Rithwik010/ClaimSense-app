#!/usr/bin/env bash
# Model v3 on Kaggle (D-V3-22): push the given kernels one after another, each as soon as the one
# before it has ended well and left a checkpoint; download every output. Run it detached and under
# caffeinate, so it outlives the terminal or agent session that started it and the Mac stays awake
# for the whole run, from the repository root:
#
#   nohup caffeinate -ims scripts/kaggle/v3_chain.sh timing resume > /dev/null 2>&1 &
#   nohup caffeinate -ims scripts/kaggle/v3_chain.sh full-1 full-2 > /dev/null 2>&1 &
#
# `--attach` first: the first kernel is already running (pushed by an earlier chain whose watcher
# stopped), so it is watched, not pushed again (a push would restart it).
#
# The kernel folders come from `python -m training.finetune.prepare_kaggle_v3`. Each stage logs to
# data/generated/v3/kaggle-runs/<stage>/watch.log; the chain stops at the first kernel that errors
# or leaves no checkpoint. data/generated/v3/kaggle-runs/chain.status holds `running`, then `done`
# or `failed: <stage>`.
set -u
KERNELS=data/generated/kaggle
RUNS=data/generated/v3/kaggle-runs
mkdir -p "$RUNS"
attach=0
if [ "${1:-}" = "--attach" ]; then
  attach=1
  shift
fi
echo "running $* (pid $$, $(date '+%F %T'))" > "$RUNS/chain.status"

fail() {
  echo "$(date '+%F %T') $2" >> "$RUNS/$1/watch.log"
  echo "failed: $1 ($2)" > "$RUNS/chain.status"
  exit 1
}

for stage in "$@"; do
  folder="$KERNELS/kernel-v3-$stage"
  slug=$(python3 -c "import json; print(json.load(open('$folder/kernel-metadata.json'))['id'])")
  mkdir -p "$RUNS/$stage"
  log="$RUNS/$stage/watch.log"
  if [ "$attach" = 1 ]; then
    echo "$(date '+%F %T') attach to the running $slug" >> "$log"
    attach=0
  else
    echo "$(date '+%F %T') push $slug" >> "$log"
    uvx kaggle kernels push -p "$folder" >> "$log" 2>&1 || fail "$stage" "push failed"
    sleep 60
  fi
  while true; do
    status=$(uvx kaggle kernels status "$slug" 2>&1 | tail -1)
    echo "$(date '+%F %T') $status" >> "$log"
    case "$status" in
      *COMPLETE*) break ;;
      *ERROR*|*CANCEL*)
        uvx kaggle kernels output "$slug" -p "$RUNS/$stage/output" >> "$log" 2>&1
        fail "$stage" "stopped: $status" ;;
    esac
    sleep 120
  done
  uvx kaggle kernels output "$slug" -p "$RUNS/$stage/output" >> "$log" 2>&1
  if ! find "$RUNS/$stage/output" -name trainer_state.json | grep -q .; then
    fail "$stage" "no checkpoint in the output: the chain stops"
  fi
  echo "$(date '+%F %T') done: checkpoint saved" >> "$log"
done
echo "done: $* ($(date '+%F %T'))" > "$RUNS/chain.status"
