# Lane C claims (updated 2026-11-18 18:26)

Files lane C edits (on branch `lane-C`, worktree $WORK/wt-C):
- src/simulation/m_riemann_solver_hllc.fpp, m_riemann_state.fpp, m_riemann_solvers.fpp (Riemann solve + flux finalize copy)
- src/simulation/m_time_steppers.fpp (RK update)
- src/common/m_variables_conversion.fpp (cons->prim)
- src/common/m_boundary_common.fpp (ghost-cell fill)
- src/common/m_eos.fpp (mixture coefficients / sound speed helpers called from the Riemann + conversion kernels)
- build flags / --case-optimization experiments: cmake/MFCTargets.cmake (-Minline limits), CMakeLists.txt

Candidates being evaluated (C = lane C):
- C1: HLLC kernel writes flux directly into flux_vf / flux_src_vf -> skip s_finalize_riemann_solver copy (~18 field sweeps per direction)
- C2: HLLC 5-eq kernel writes vel_src_rsx_vf (num_dims fields) only when viscous/surface_tension consume it
- C3: build flags / --case-optimization measurements

NOT touching (lane B): m_weno.fpp, m_rhs.fpp.
Note for lane B: s_compute_rhs copies q_cons_vf -> q_cons_qp over the full buffered domain every stage
(m_rhs.fpp ~L604-614); it is only needed when (mpp_lim .and. bubbles_euler) modifies it, but q_prim_qp's adv
fields alias q_cons_qp, so removing it needs care. Left to lane B.
