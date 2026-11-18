# Source inside a login shell on the compute node (srun ... bash -lc 'source $HW/jobs/env.sh && ...')
module purge >/dev/null 2>&1
module load x86-nvhpc/26.3
export PATH=$HOME/.local/bin:$PATH            # uv (MFC bootstrap uses it if present)
export UV_CACHE_DIR=$WORK/.uv-cache
export UV_LINK_MODE=copy
export MFC_CUDA_CC=90                          # H200 = sm_90; avoids multi-arch codegen
export OMPI_MCA_hwloc_base_binding_policy=none
