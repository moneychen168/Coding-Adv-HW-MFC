#!/bin/bash
# Lane A baseline: 3 repeats of each standard benchmark config on the pinned tree.
# Standard configs (use these exact args in every lane):
#   PRIMARY  : $HW/cases/5eq_rk3_weno3_hllc/case.py          --gbpp 160 --steps 60
#   SECONDARY: $HW/cases/viscous_weno5_sgb_acoustic/case.py  --gbpp 96  --steps 40
TREE=${TREE:-$WORK/MFC}
R=${R:-$WORK/results/A/baseline}
mkdir -p $R
for i in 1 2 3; do
  $HW/jobs/run_bench.sh $TREE $HW/cases/5eq_rk3_weno3_hllc/case.py $R/hllc_run$i --gbpp 160 --steps 60
done
for i in 1 2 3; do
  $HW/jobs/run_bench.sh $TREE $HW/cases/viscous_weno5_sgb_acoustic/case.py $R/visc_run$i --gbpp 96 --steps 40
done
touch $R/DONE
