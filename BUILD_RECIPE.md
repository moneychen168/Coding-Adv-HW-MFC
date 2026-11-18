# MFC GPU build recipe (lane A) — NCHC Nano, H200

Status: WORKING (17:29 CST 2026-11-18). pre_process + simulation built with OpenACC/NVHPC 26.3 and a
GPU smoke run of `benchmarks/5eq_rk3_weno3_hllc` passed (grind 0.748 ns at 198x99x99, log:
`$WORK/results/A/smoke1/simulation.log`). post_process NOT built (its fftw/hdf5/silo dep build was
stopped: not needed for grind/compare). Profiling: `$HW/jobs/profile_A.sh` (nsys + ACC_TIME), `$HW/jobs/ncu_A.sh`.
Running the binary directly: always `mpirun -np 1 [nsys|ncu ...] <TREE>/build/install/*/bin/simulation` from the case dir
(a singleton MPI_Init fails inside an srun step). `git commit` in an MFC tree runs the precheck hook, so commit on the compute node (lane C).

## Source
- Tree: `$WORK/MFC` (symlink `$HW/MFC`)
- Pinned: MFC release **v5.7.1** = commit `ce4b191d4da0da50672bef8974638a43d8cbd279` (2026-10-26).
  Tag `hw-baseline` on it; branch `hw-opt` created from it. (master was 135 commits ahead; we use the release.)

## Environment (compute node only; `module` exists only in login shells -> `bash -lc`)
`$HW/jobs/env.sh`:
```
module purge; module load x86-nvhpc/26.3     # nvfortran 26.3 + HPC-X OpenMPI (mpif90/mpirun)
export PATH=$HOME/.local/bin:$PATH           # uv -> MFC venv bootstrap is fast
export UV_CACHE_DIR=$WORK/.uv-cache  UV_LINK_MODE=copy
export MFC_CUDA_CC=90                         # H200 sm_90 only
```
System python3 3.9.21 and system cmake 3.26.5 are accepted by MFC (needs py 3.9-3.14, cmake >= 3.20).
Compute nodes HAVE internet (github/fftw reachable), so the first `./mfc.sh` call installs its venv there.

## Build (inside your holder job)
```
srun --jobid=<HOLDER> --overlap --gpus=1 -n 1 -c 12 bash -lc \
  'source $HW/jobs/env.sh && cd <TREE> && ./mfc.sh build --gpu acc -j 12 -t pre_process simulation'
```
Measured on the fresh tree (job 799601): venv ~1 min, configure ~3 min PER TARGET (slow CMake checks),
pre_process build 147 s, simulation build 238 s. Total to working simulation ~10.5 min.
Run long builds in background: `nohup srun ... > log 2>&1 &` and poll the log (>=30 s sleeps).

## Run a case on GPU
Use the shared script (every lane measures the same way):
```
srun --jobid=<HOLDER> --overlap --gpus=1 -n 1 -c 12 bash -lc \
  '$HW/jobs/run_bench.sh <TREE> 5eq_rk3_weno3_hllc <OUTDIR> --gbpp <G> --steps <S>'
```
It copies case.py into OUTDIR, runs pre_process then simulation via
`./mfc.sh run <OUTDIR>/case.py -t simulation --gpu acc --binary mpirun -n 1 --no-build --output-summary ...`
and prints `RESULT grind_ns=... step_med_s=... loop_s=... sim_exec_s=...`.
- `--binary mpirun`: the default template picks `srun` first; we are already inside an srun step, so force mpirun.
- `--no-build`: never rebuild implicitly during a measurement.
- `PRE_TREE=$WORK/MFC` env: generate ICs with the baseline pre_process (a lane then only
  needs to build `simulation`). pre_process runs on 1 rank (serial I/O => rank count must match simulation).
- Benchmark sizing knobs from the official case files: `--gbpp G` => ~G*0.5M cells (Nx=2s, Ny=Nz=s),
  `--steps S` overrides t_step_stop/save. Standard sizes: table below.

### STANDARD lane-A benchmark configs (use exactly these for speedup numbers)
| id | case file | args | grid (m,n,p) | GPU mem | baseline (median of 3) |
|---|---|---|---|---|---|
| PRIMARY | `$HW/cases/5eq_rk3_weno3_hllc/case.py` | `--gbpp 160 --steps 60` | 682x341x341 (79,886,412 cells, 8 eqs) | 86.6 GB measured | grind 0.61395 ns, loop 69.09 s, exec 97.2 s; ~1 min pre_process |
| SECONDARY | `$HW/cases/viscous_weno5_sgb_acoustic/case.py` | `--gbpp 96 --steps 40` | 576x288x288 (48,191,617 cells, 8 eqs) | ~100 GB (extrapolated) | grind 1.31140 ns, loop 58.91 s, exec 80.1 s |
Raw: `$WORK/results/A/baseline/*/RESULT.txt`. Profiles: `results/A/profile_{hllc,visc}/`, ncu: `results/A/ncu_hllc_g32/`.
`$HW/cases/*/case.py` are byte-identical copies of `benchmarks/*/case.py` except `"parallel_io": "T"`.
Reason: with `parallel_io=F`, simulation writes an ASCII dump `D/cons.*.dat` of every 3D field at every save
step (m_data_output.fpp:738-750; 7.2 GB for a 2M-cell run, would be ~80 GB per save at 80M cells).
`parallel_io=T` writes one binary `restart_data/lustre_<step>.dat` (sys_size vars x (m+1)(n+1)(p+1) float64).
Grind time is unaffected (I/O is outside the timed RK stages), only exec wall time.
Driver for the 3x baseline: `$HW/jobs/baseline_A.sh` (TREE=... R=... env overrides).

### Correctness check
```
srun --jobid=<HOLDER> --overlap -n 1 -c 12 bash -lc \
  '$WORK/MFC/build/venv/bin/python3 $HW/tools/compare_output.py <refdir> <newdir>'
```
(system python3 has no numpy; use the MFC venv python.) Reference outputs:
`$WORK/results/A/baseline/{hllc,visc}_run1` (final step = 60 / 40).

## Independent tree for another lane
```
cd $WORK/MFC && git worktree add $WORK/wt-B hw-baseline -b lane-B   # (login node OK: git only)
srun --jobid=<HOLDER_B> --overlap --gpus=1 -n 1 -c 12 bash -lc \
  'source $HW/jobs/env.sh && cd $WORK/wt-B && ./mfc.sh build --gpu acc -j 12 -t simulation'
```
- Each tree has its own `build/` (venv, staging, install). CMake caches absolute source paths, so the
  baseline `build/` cannot be copied/reused; the uv cache IS shared (venv re-creation ~20-60 s).
- Build only `-t simulation` in a lane tree (~1 min venv + ~3 min configure + ~4 min build) and run with
  `PRE_TREE=$WORK/MFC` so pre_process comes from the baseline tree.
- After editing sources, re-run the same build command: CMake/make rebuilds only changed files (+ Fortran
  module dependents). Installed binary: `<TREE>/build/install/gpu-acc-<hash>/bin/simulation`.
- Compile flags already on (cmake/MFCTargets.cmake): `-gpu=cc90,keep,ptxinfo,lineinfo`, `-Minfo=inline`.
  `--fastmath` / `--case-optimization` are MFC options (case-opt bakes case params into the binary, docs claim up to 10x).

## Pitfalls hit
- First `./mfc.sh` call builds a "hipfort" dependency (harmless, seconds) and installs a git pre-commit hook.
- Configure step is slow (~3 min/target) even though the build itself is quick.
- `build/lock.yaml` only stores the build config (gpu/mpi/...); passing different flags (e.g. no `--gpu`) to
  `./mfc.sh run/build` silently switches the config of that tree -> always pass `--gpu acc`.
- syscheck runs before every `./mfc.sh run` (~4 s, outside the simulation timing).
- Killing the login-side `srun` of a background step cancels that step only (holder job survives).
- Don't overlap a build/other GPU job with timing runs in the same holder (12-core make perturbs host launch).
