#!/bin/bash
# One command to regenerate every deliverable from content.yaml (+ $HW/report.md).
#   bash $HW/deliverables_src/make_all.sh            # TTS (login node, network only) + render in the holder job
#   STAGES="pptx png" bash make_all.sh                     # rerun only some render stages (charts pptx png video report)
#   SKIP_TTS=1 bash make_all.sh                            # skip the TTS step (e.g. only slides/report changed)
#   HOLDER_JOB=799605 (default)                            # pre-allocated SLURM job; compute runs there via srun --overlap
# Outputs: $WORK/deliverables/{slides.pptx,speech.md,video.mp4,video.srt,report.pdf,slides_preview.pdf}
#          copies of slides.pptx / speech.md / video.srt -> $HW/docs/
# Log: $WORK/deliver_build/render.log ; marker: $WORK/deliver_build/DONE (OK|FAIL ...)
set -euo pipefail
SRC=$(cd "$(dirname "$0")" && pwd)
W=$WORK
B=$W/deliver_build
PY=/work/$USER/hw3_comd/venv-deliver/bin/python           # HW3 venv, used read-only
HOLDER_JOB=${HOLDER_JOB:-799605}
export PYTHONDONTWRITEBYTECODE=1
mkdir -p $B

# 1) narration TTS: network I/O only (edge-tts), cached per sentence -> only changed sentences are re-requested.
#    Male voice only (zh-CN-YunyangNeural; zh-TW-YunJheNeural was down server-side 11/18); NO female fallback.
if [[ -z "${SKIP_TTS:-}" ]]; then
  ok=0
  for attempt in 1 2 3; do
    if $PY "$SRC/tts.py"; then ok=1; break; fi
    echo "tts.py attempt $attempt failed; retrying in $((attempt * 20)) s"; sleep $((attempt * 20))
  done
  [[ $ok == 1 ]] || { echo "TTS FAILED with the male voice after 3 attempts (no female fallback by design)"; exit 2; }
fi

# 2) everything compute-heavy runs inside the holder SLURM job (charts, pptx, LibreOffice render, ffmpeg, PDF)
rm -f $B/DONE
echo "render in job $HOLDER_JOB  (log: $B/render.log, marker: $B/DONE)"
srun --jobid=$HOLDER_JOB --overlap -c 12 --export=ALL,STAGES="${STAGES:-charts pptx png video report}" \
  bash "$SRC/render.sh" > $B/render.log 2>&1 || true
[[ -f $B/DONE ]] || echo "FAIL $(date +%F_%T) srun returned without marker" > $B/DONE
cat $B/DONE
tail -30 $B/render.log
grep -q '^OK' $B/DONE
