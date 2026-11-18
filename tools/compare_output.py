#!/usr/bin/env python3
"""Compare the conserved variables written by two MFC simulation runs.

Usage:
  compare_output.py <caseA> <caseB> [--step N] [--rtol 1e-12] [--atol 0]

<caseX> is a case/output directory. Two layouts are supported:
  * parallel_io=T (the lane cases in $HW/cases):  restart_data/lustre_<step>.dat
      raw float64, sys_size variables back to back, each (m+1)(n+1)(p+1) cells (m,n,p read
      from <caseX>/simulation.inp)
  * parallel_io=F (official benchmark files):  p_all/p0/<step>/q_cons_vf<i>.dat
      Fortran unformatted sequential records of float64
If --step is omitted, the largest step present in both runs is used.
Prints per-variable max|A|, max abs diff, max abs diff / max|A| (field-normalised relative
error), pointwise max rel diff (|a-b|/|a| where |a|>1e-300, and where |a|>1e-6*max|A|), bitwise identity and NaN count.
Exit 0 if every variable satisfies max_abs <= atol + rtol*max|A| and has no NaN, else 1.
Run it on a compute node (it reads multi-GB files).
"""
import argparse
import glob
import os
import re
import sys

import numpy as np


def read_fortran_unformatted(path, dtype=np.float64):
    raw = np.fromfile(path, dtype=np.uint8)
    out, i, n = [], 0, raw.size
    while i < n:
        L = abs(int(np.frombuffer(raw[i:i + 4].tobytes(), dtype=np.int32)[0]))
        out.append(raw[i + 4:i + 4 + L])
        i += 4 + L + 4
    return np.frombuffer(np.concatenate(out).tobytes(), dtype=dtype)


def read_inp(case):
    vals = {}
    with open(os.path.join(case, "simulation.inp")) as f:
        for line in f:
            mm = re.match(r"\s*(m|n|p)\s*=\s*(-?\d+)", line)
            if mm:
                vals[mm.group(1)] = int(mm.group(2))
    return (vals["m"] + 1) * (vals.get("n", 0) + 1) * (vals.get("p", 0) + 1)


def load_vars(case, step):
    """Return (dict step->loader, kind)."""
    rd = os.path.join(case, "restart_data")
    files = glob.glob(os.path.join(rd, "lustre_*.dat"))
    steps = {int(m.group(1)): f for f in files if (m := re.search(r"lustre_(\d+)\.dat$", f))}
    if steps:
        def loader(s):
            ncell = read_inp(case)
            arr = np.fromfile(steps[s], dtype=np.float64)
            nvar = arr.size // ncell
            assert nvar * ncell == arr.size, f"{steps[s]}: size {arr.size} not a multiple of ncell {ncell}"
            return [(f"var{i + 1}", arr[i * ncell:(i + 1) * ncell]) for i in range(nvar)]
        return set(steps), loader, "restart_data"
    pdir = os.path.join(case, "p_all", "p0")
    if os.path.isdir(pdir):
        st = {int(d) for d in os.listdir(pdir) if d.isdigit()}

        def loader(s):
            fs = glob.glob(os.path.join(pdir, str(s), "q_cons_vf*.dat"))
            fs.sort(key=lambda f: int(re.findall(r"(\d+)\.dat$", f)[0]))
            return [(os.path.basename(f), read_fortran_unformatted(f)) for f in fs]
        return st, loader, "p_all"
    sys.exit(f"no restart_data/lustre_*.dat or p_all/p0 in {case}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--step", type=int, default=None)
    ap.add_argument("--rtol", type=float, default=1e-12)
    ap.add_argument("--atol", type=float, default=0.0)
    args = ap.parse_args()

    sa, la, ka = load_vars(args.a, args.step)
    sb, lb, kb = load_vars(args.b, args.step)
    common = sorted(sa & sb)
    step = args.step if args.step is not None else (common[-1] if common else None)
    if step is None or step not in sa or step not in sb:
        sys.exit(f"step {step} not in both runs: A={sorted(sa)} B={sorted(sb)}")
    VA, VB = la(step), lb(step)
    print(f"A = {args.a} ({ka})\nB = {args.b} ({kb})\nstep = {step}")
    if len(VA) != len(VB):
        print(f"variable count differs: {len(VA)} vs {len(VB)}")
        sys.exit(1)
    ok, bitwise_all = True, True
    print(f"{'var':>14} {'ncell':>11} {'max|A|':>11} {'max_abs':>11} {'abs/max|A|':>11} {'max_ptw_rel':>11} {'rel|A|>1e-6max':>14} {'bitwise':>7} {'nan':>4}")
    for (na, A), (_, B) in zip(VA, VB):
        if A.shape != B.shape:
            print(f"{na}: shape mismatch {A.shape} vs {B.shape}")
            ok = False
            continue
        bitwise = A.tobytes() == B.tobytes()
        bitwise_all &= bitwise
        nan = int(np.isnan(A).sum() + np.isnan(B).sum())
        d = np.abs(A - B)
        scale = max(float(np.nanmax(np.abs(A))), np.finfo(np.float64).tiny)
        max_abs = float(np.nanmax(d)) if d.size else 0.0
        nz = np.abs(A) > 1e-300
        ptw = float(np.nanmax(d[nz] / np.abs(A[nz]))) if nz.any() else 0.0
        sig = np.abs(A) > 1e-6 * scale  # pointwise rel. only where |A| is not negligible vs the field
        ptw_sig = float(np.nanmax(d[sig] / np.abs(A[sig]))) if sig.any() else 0.0
        bad = nan > 0 or max_abs > args.atol + args.rtol * scale
        ok &= not bad
        print(f"{na:>14} {A.size:>11} {scale:11.4e} {max_abs:11.4e} {max_abs / scale:11.4e} {ptw:11.4e} {ptw_sig:14.4e} {str(bitwise):>7} {nan:>4}")
    print(f"BITWISE_IDENTICAL={bitwise_all}  WITHIN_TOL(rtol={args.rtol},atol={args.atol})={ok}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
