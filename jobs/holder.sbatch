#!/bin/bash
#SBATCH -A <account>
#SBATCH -p 8gpus
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=12
#SBATCH --time=06:00:00
#SBATCH --exclude=<gpu-node>,<gpu-node>,<gpu-node>,<gpu-node>
#SBATCH -o $WORK/logs/holder_%x_%j.log
# Holder allocation: agents attach with `srun --jobid=$SLURM_JOB_ID --overlap ...`
echo "$SLURM_JOB_ID $(hostname)" > $WORK/logs/holder_${SLURM_JOB_NAME}.info
nvidia-smi -L
sleep infinity
