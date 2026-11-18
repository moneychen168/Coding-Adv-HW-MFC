#!/bin/bash
# ncu (full set) on the top kernels of one stage. usage: ncu_A.sh <tree> <case.py> <outdir> [case args]
set -e
TREE=$(readlink -f $1); C=$2; O=$3; shift 3
source $HW/jobs/env.sh
export TMPDIR=/tmp
NCU=/usr/local/cuda-13.0/bin/ncu
[ -f $O/simulation.inp ] || $HW/jobs/run_bench.sh $TREE $C $O "$@"
BIN=$(ls $TREE/build/install/*/bin/simulation | head -1)
cd $O
mpirun -np 1 $NCU --set full -k "regex:${NCU_KREGEX:-weno_983|hllc_riemann_solver_894|conservative_to_primitive_variables_420|tvd_rk_505|advection_source_term_1367|finalize_riemann_solver_1348}" \
   -c ${NCU_COUNT:-10} -f -o $O/ncu_top $BIN > $O/ncu_run.log 2>&1
$NCU --import $O/ncu_top.ncu-rep --page details --csv > $O/ncu_details.csv 2>/dev/null || true
echo NCU_DONE
