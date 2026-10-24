#!/usr/bin/env bash
# Model v3 on Kaggle (D-V3-22): push the given kernels one after another, each as soon as the one
# before it has ended well and left a checkpoint; download every output. Run it under caffeinate so
# the Mac stays awake for the whole run, from the repository root:
#
#   caffeinate -ims scripts/kaggle/v3_chain.sh timing resume
#   caffeinate -ims scripts/kaggle/v3_chain.sh full-1 full-2
#
# The kernel folders come from `python -m training.finetune.prepare_kaggle_v3`. Each stage logs to
# data/generated/v3/kaggle-runs/<stage>/watch.log; the chain stops at the first kernel that errors
# or leaves no checkpoint.
set -u
KERNELS=data/generated/kaggle
RUNS=data/generated/v3/kaggle-runs

for stage in "$@"; do
  folder="$KERNELS/kernel-v3-$stage"
  slug=$(python3 -c "import json; print(json.load(open('$folder/kernel-metadata.json'))['id'])")
  mkdir -p "$RUNS/$stage"
  log="$RUNS/$stage/watch.log"
  echo "$(date '+%F %T') push $slug" >> "$log"
  if ! uvx kaggle kernels push -p "$folder" >> "$log" 2>&1; then
    echo "$(date '+%F %T') push failed" >> "$log"
    exit 1
  fi
  sleep 60
  while true; do
    status=$(uvx kaggle kernels status "$slug" 2>&1 | tail -1)
    echo "$(date '+%F %T') $status" >> "$log"
    case "$status" in
      *COMPLETE*) break ;;
      *ERROR*|*CANCEL*)
        uvx kaggle kernels output "$slug" -p "$RUNS/$stage/output" >> "$log" 2>&1
        echo "$(date '+%F %T') stopped: $status" >> "$log"
        exit 1 ;;
    esac
    sleep 120
  done
  uvx kaggle kernels output "$slug" -p "$RUNS/$stage/output" >> "$log" 2>&1
  if ! find "$RUNS/$stage/output" -name trainer_state.json | grep -q .; then
    echo "$(date '+%F %T') no checkpoint in the output: the chain stops" >> "$log"
    exit 1
  fi
  echo "$(date '+%F %T') done: checkpoint saved" >> "$log"
done
