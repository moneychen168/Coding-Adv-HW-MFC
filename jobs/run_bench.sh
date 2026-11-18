#!/bin/bash
# Usage (on the compute node, inside the holder job):
#   run_bench.sh <tree> <case> <outdir> [case args...]
#     <tree>   MFC tree that is ALREADY BUILT with --gpu (e.g. $WORK/MFC)
#     <case>   benchmark slug (benchmarks/<slug>/case.py) or path to a case.py
#     <outdir> fresh output dir (case.py is copied here; outputs land here)
#     case args are passed to case.py after '--', e.g.  --gbpp 64 --steps 60
# Example via holder job (from login node):
#   srun --jobid=799601 --overlap --gpus=1 -n 1 -c 12 bash -lc \
#     '$HW/jobs/run_bench.sh $WORK/MFC 5eq_rk3_weno3_hllc $WORK/results/X/run1 --gbpp 64 --steps 60'
# Env knobs: SKIP_PRE=1 reuse ICs already in <outdir> (p_all/p0/0 from a previous run)
#            PRE_TREE=<tree> run pre_process from another (baseline) tree, so a lane only builds simulation
#            MFC_EXTRA="..." extra ./mfc.sh run flags (e.g. --case-optimization)
set -eo pipefail
TREE=$(readlink -f "$1"); CASE="$2"; OUT="$3"; shift 3 || { echo "usage: $0 <tree> <case> <outdir> [case args]"; exit 2; }
source $HW/jobs/env.sh
[ -f "$CASE" ] && SRC=$(readlink -f "$CASE") || SRC="$TREE/benchmarks/$CASE/case.py"
[ -f "$SRC" ] || { echo "case not found: $SRC"; exit 2; }
mkdir -p "$OUT"; OUT=$(readlink -f "$OUT")
cp "$SRC" "$OUT/case.py"
cd "$TREE"
COMMON=(--gpu acc --binary mpirun -n 1 --no-build $MFC_EXTRA)
if [ -z "$SKIP_PRE" ]; then
  # PRE_TREE: tree whose pre_process binary generates the ICs (default: <tree>); lets a lane build only simulation
  PRE_TREE=$(readlink -f "${PRE_TREE:-$TREE}")
  (cd "$PRE_TREE" && ./mfc.sh run "$OUT/case.py" -t pre_process --gpu acc --binary mpirun -n 1 --no-build -- "$@") > "$OUT/pre_process.log" 2>&1 \
    || { tail -30 "$OUT/pre_process.log"; echo "PRE_PROCESS FAILED"; exit 1; }
fi
rm -f "$OUT/time_data.dat" "$OUT/summary.yaml"
nvidia-smi --query-gpu=name,clocks.sm,clocks.mem,temperature.gpu --format=csv,noheader > "$OUT/gpu_before.txt" 2>/dev/null || true
T0=$(date +%s.%N)
./mfc.sh run "$OUT/case.py" -t simulation "${COMMON[@]}" --output-summary "$OUT/summary.yaml" -- "$@" > "$OUT/simulation.log" 2>&1 \
  || { tail -40 "$OUT/simulation.log"; echo "SIMULATION FAILED"; exit 1; }
T1=$(date +%s.%N)
GRIND=$(grep -m1 'grind:' "$OUT/summary.yaml" | awk '{print $2}')
EXEC=$(grep -A1 '^simulation:' "$OUT/summary.yaml" | awk '/exec:/{print $2}')
WALL=$(echo "$T1 - $T0" | bc -l)
# per-step wall times printed by simulation ("t/step X s"); loop_s = sum over all steps, step_med = median excl. first 2 (warmup)
read LOOP STEPMED NSTEP < <(grep -o 't/step *[0-9.E+-]*s' "$OUT/simulation.log" | sed 's/t\/step *//; s/s$//' | python3 -c '
import sys,statistics as st; v=[float(x) for x in sys.stdin.read().split()]
w=v[3:] if len(v)>3 else v; print(f"{sum(v):.3f} {st.median(w):.5f} {len(v)}")')
printf "RESULT case=%s grind_ns=%s step_med_s=%s loop_s=%s nsteps=%s sim_exec_s=%s mfc_run_wall_s=%.2f out=%s\n" "$(basename "$(dirname "$SRC")")" "$GRIND" "$STEPMED" "$LOOP" "$NSTEP" "$EXEC" "$WALL" "$OUT" | tee "$OUT/RESULT.txt"
