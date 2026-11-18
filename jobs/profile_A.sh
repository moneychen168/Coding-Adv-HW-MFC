#!/bin/bash
# Profile one benchmark config on GPU: nsys timeline (cuda+nvtx+openacc) + NVHPC ACC_TIME table.
# usage: profile_A.sh <tree> <case.py> <outdir> [case args]   (run inside holder job, srun -n 1)
# If <outdir>/simulation.inp + restart_data exist, the setup run is skipped.
set -e
TREE=$(readlink -f $1); C=$2; O=$3; shift 3
source $HW/jobs/env.sh
export TMPDIR=/tmp
NSYS=/usr/local/cuda-13.0/bin/nsys
[ -f $O/simulation.inp ] || $HW/jobs/run_bench.sh $TREE $C $O "$@"   # creates ICs + simulation.inp
BIN=$(ls $TREE/build/install/*/bin/simulation | head -1)
cd $O
# singleton MPI_Init fails inside an srun step -> always go through mpirun
mpirun -np 1 $NSYS profile -t cuda,nvtx,openacc --force-overwrite true -o $O/nsys_prof $BIN > $O/nsys_run.log 2>&1
$NSYS stats -r cuda_gpu_kern_sum,cuda_gpu_mem_time_sum,cuda_gpu_mem_size_sum,nvtx_sum,cuda_api_sum,openacc_sum -f csv -o $O/stats $O/nsys_prof.nsys-rep > $O/nsys_stats.log 2>&1 || true
mpirun -np 1 -x NVCOMPILER_ACC_TIME=1 $BIN > $O/acctime.log 2>&1
echo PROFILE_DONE
