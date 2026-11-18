# Lane B claims (updated 2026-11-18 17:35)

Files lane B edits (branch `lane-B`, worktree $WORK/wt-B): src/simulation/m_weno.fpp, src/simulation/m_rhs.fpp only.

Candidates (B = lane B):
- B1: WENO3 kernel: private automatic arrays (dvd/poly/beta/alpha/omega, sized by runtime weno_num_stencils) -> scalars; variable index `i` moved outermost in collapse(4) for coalesced access. Bitwise-identical intent.
- B2: WENO sweep range: transverse loops run over the full buffered range (idwbuff) but the Riemann solver only reads 0:n / 0:p (inviscid, no surface tension) -> trim transverse range when no consumer needs ghosts.
- B3: mapped-WENO3 division count 16 -> 4 per (cell,var) by algebraic combination (ulp-level FP difference, same method).
- B4: s_compute_rhs q_cons_vf -> q_cons_qp full-field copy (noted by lane C) and flux-difference/advection-source loops in m_rhs.fpp.
NOT touching: Riemann solver files, m_time_steppers, m_variables_conversion, m_boundary_common (lane C).

## 17:59 NOTE FOR LANE C (HLLC is yours; this is a measured hint, not a claim)
B1 (commit 7fe05fcf on lane-B, m_weno.fpp only) took 5eq_rk3_weno3_hllc 503x252x252 from grind 0.6286 -> 0.4079 ns (bitwise identical)
by (a) replacing the WENO3 kernel's private arrays whose extent is a RUN-TIME variable (dimension(0:weno_num_stencils)) with scalars and
(b) moving the variable index outermost in collapse(4). NV_ACC_TIME profile after B1 (results/B/acctime_b1.txt): s_hllc_riemann_solver:894 = 46.6 %,
s_weno = 24.7 %, cons->prim 6.3 %, s_tvd_rk 4.1 %.
The HLLC kernel has the same pattern: m_riemann_solver_hllc.fpp L51-55 declares private arrays `dimension(num_fluids)` / `dimension(num_dims)`
(run-time extents in the non-case-optimized build) -> per-thread device-memory temporaries. Making them fixed-size (e.g. the `dimension(3)` branch
already used for USING_AMD at L46-49, or num_fluids_max) is likely the single biggest remaining win. I am NOT touching that file.

## 18:50 lane B -> lane C: experiment E1 in progress (NOT committed to lane-B; scratch tree wt-B-co)
Testing the 17:59 hint myself so you do not have to: on top of lane-B HEAD, HLLC L51-55 privates -> `dimension(num_fluids_max)` / `dimension(3)`
and cons->prim (m_variables_conversion L393) alpha_K/alpha_rho_K -> `dimension(num_fluids_max)`, both only when not case-optimized.
Result + ready-to-apply diff will be at $WORK/results/B/patches/e1_hllc_conv_fixed_extents.diff and in results/B/summary.md (ETA ~19:40).
If you already did this, ignore; the files stay yours and I will not commit them on lane-B.
