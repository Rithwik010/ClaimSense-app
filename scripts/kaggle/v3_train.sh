#!/usr/bin/env bash
# Model v3's training run on Kaggle under the team's pre-approval of 24 Oct (D-V3-25), unattended:
#
# - sessions full-1, then full-2 (and full-3 only when needed), each pushed as soon as the one
#   before it has ended and its output (with its checkpoint) is downloaded;
# - a session that reaches its safety stop (11 h, training/finetune/train.py) is continued by the
#   next; one crash is resumed once from the last checkpoint (the first session again, from the
#   start, if it crashed before its first checkpoint); a second crash stops the chain;
# - before each new session: the run's hours so far plus the hours left must stay within
#   RUN_LIMIT_HOURS, and the week's (WEEK_USED_HOURS at the start, plus this run) within
#   WEEK_LIMIT_HOURS, else the chain stops;
# - when the pace projects the run's training over PACE_NOTICE_HOURS, a notice (macOS notification
#   and kaggle-runs/notices.log), without stopping;
# - when training has finished, both GGUFs (the best and the final checkpoint) are exported on a
#   CPU-only session (scripts/kaggle/v3_export.py, D-V3-26: no GPU quota) and its report checked.
#
# Hours are wall-clock from push to the end of each session (a little over Kaggle's count). Run it
# detached and under caffeinate, from the repository root:
#
#   nohup caffeinate -ims scripts/kaggle/v3_train.sh 2.3 > /dev/null 2>&1 &   # 2.3: hours used
#
# kaggle-runs/chain.status: `training ...`, then `done ...` or `stopped: ...`.
set -u
WEEK_USED_HOURS=${1:?hours of GPU quota used this week before the run}
RUN_LIMIT_HOURS=22
WEEK_LIMIT_HOURS=30
PACE_NOTICE_HOURS=19
KERNELS=${KERNELS:-data/generated/kaggle}
RUNS=${RUNS:-data/generated/v3/kaggle-runs}
mkdir -p "$RUNS"
run_hours=0
crashes=0

notice() {
  echo "$(date '+%F %T') $1" >> "$RUNS/notices.log"
  osascript -e "display notification \"$1\" with title \"ClaimSense v3 training\"" > /dev/null 2>&1
}

stop() {
  echo "stopped: $1 ($(date '+%F %T'))" > "$RUNS/chain.status"
  notice "stopped: $1"
  exit 1
}

add() { python3 -c "print(round($1 + $2, 2))"; }
field() { echo "$result" | python3 -c "import json, sys; print(json.load(sys.stdin).get('$1'))"; }
over() { python3 -c "import sys; sys.exit(0 if $1 > $2 else 1)"; }

# session <stage>: push, wait, download; sets $hours and $result (the pace JSON)
session() {
  local stage=$1 folder="$KERNELS/kernel-v3-$1" log="$RUNS/$1/watch.log" slug started status
  slug=$(python3 -c "import json; print(json.load(open('$folder/kernel-metadata.json'))['id'])")
  rm -rf "$RUNS/$stage/output"
  mkdir -p "$RUNS/$stage"
  echo "training: $stage (pid $$, $(date '+%F %T'))" > "$RUNS/chain.status"
  echo "$(date '+%F %T') push $slug" >> "$log"
  started=$(date +%s)
  uvx kaggle kernels push -p "$folder" >> "$log" 2>&1 || stop "$stage: push failed"
  sleep 60
  while true; do
    status=$(uvx kaggle kernels status "$slug" 2>&1 | tail -1)
    echo "$(date '+%F %T') $status" >> "$log"
    case "$status" in
      *COMPLETE*|*ERROR*|*CANCEL*) break ;;
    esac
    sleep 300
  done
  hours=$(python3 -c "print(round(($(date +%s) - $started) / 3600, 2))")
  uvx kaggle kernels output "$slug" -p "$RUNS/$stage/output" >> "$log" 2>&1
  result=$(uv run --quiet python -m scripts.verify.v3_pace "$RUNS/$stage/output" 2>/dev/null)
  echo "$(date '+%F %T') $hours h; $status; $result" >> "$log"
  case "$status" in
    *ERROR*|*CANCEL*)  # after training finished, a later cell (a GGUF export) failed: no resume
      [ "$(field state)" = "finished" ] && stop "$stage: training finished but a later cell failed" ;;
  esac
}


# export <stage>: the CPU-only export of the finished session's adapters
export() {
  local slug="claimsense-finetune-v3-$1" log="$RUNS/export/watch.log" status
  mkdir -p "$RUNS/export"
  rm -rf "$RUNS/export/output"
  echo "exporting: $1 (pid $$, $(date '+%F %T'))" > "$RUNS/chain.status"
  uv run --quiet python -m scripts.kaggle.v3_export --source "$slug" >> "$log" 2>&1 \
    || stop "the export notebook could not be written"
  uvx kaggle kernels push -p "$KERNELS/kernel-v3-export" >> "$log" 2>&1 || stop "export: push failed"
  sleep 60
  while true; do
    status=$(uvx kaggle kernels status "$USER_SLUG/claimsense-v3-export" 2>&1 | tail -1)
    echo "$(date '+%F %T') $status" >> "$log"
    case "$status" in *COMPLETE*|*ERROR*|*CANCEL*) break ;; esac
    sleep 120
  done
  uvx kaggle kernels output "$USER_SLUG/claimsense-v3-export" -p "$RUNS/export/output" >> "$log" 2>&1
  report=$(find "$RUNS/export/output" -name report.json | head -1)
  if [ -z "$report" ] || ! python3 -c "import json, sys; r = json.load(open('$report')); \
      sys.exit(0 if r and all(v['ok'] for v in r.values()) else 1)"; then
    stop "training finished in $1, but the CPU export failed or differs from v2 (see $report)"
  fi
}

USER_SLUG=$(python3 -c "import json; print(json.load(open('$KERNELS/kernel-v3-full-1/kernel-metadata.json'))['id'].split('/')[0])")
stage=full-1
while true; do
  session "$stage"
  run_hours=$(add "$run_hours" "$hours")
  state=$(field state)
  projected=$(field projected_training_hours)
  if [ "$projected" != "None" ] && over "$projected" "$PACE_NOTICE_HOURS"; then
    notice "pace: the run's training projects to $projected h (over $PACE_NOTICE_HOURS h); continuing"
  fi
  case "$state" in
    finished)
      notice "training finished in $stage ($run_hours h); exporting on CPU"
      export "$stage"
      echo "done: finished in $stage; $run_hours h; exported ($(date '+%F %T'))" > "$RUNS/chain.status"
      notice "training finished in $stage and both GGUFs are exported"
      exit 0 ;;
    paused) next_reason="safety stop" ;;
    *)
      crashes=$((crashes + 1))
      [ "$crashes" -gt 1 ] && stop "$stage crashed again (second crash)"
      notice "$stage crashed; resuming once from the last checkpoint"
      next_reason="crash" ;;
  esac
  remaining=$(field remaining_hours)
  [ "$remaining" = "None" ] && remaining=$RUN_LIMIT_HOURS  # no pace yet: the whole limit
  if over "$(add "$run_hours" "$remaining")" "$RUN_LIMIT_HOURS"; then
    stop "the run would exceed $RUN_LIMIT_HOURS h ($run_hours h so far, $remaining h left)"
  fi
  if over "$(add "$(add "$WEEK_USED_HOURS" "$run_hours")" "$remaining")" "$WEEK_LIMIT_HOURS"; then
    stop "the week would exceed $WEEK_LIMIT_HOURS h"
  fi
  case "$stage" in
    full-1)
      if [ "$(field checkpoint)" = "True" ]; then stage=full-2; else stage=full-1; fi ;;
    full-2) stage=full-3 ;;
    full-3) stop "full-3 ended without finishing ($next_reason); no fourth session is defined" ;;
  esac
  echo "$(date '+%F %T') next: $stage ($next_reason)" >> "$RUNS/notices.log"
done
