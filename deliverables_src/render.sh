#!/bin/bash
# Render all deliverables from content.yaml (+ cached TTS from tts.py). Compute only; no network needed.
# Runs INSIDE the pre-allocated holder SLURM job via make_all.sh:
#   srun --jobid=$HOLDER_JOB --overlap -c 12 bash render.sh
# (never on the login node, never via sbatch). STAGES env (default "charts pptx png video report") reruns a subset.
set -euo pipefail
SRC=$HW/deliverables_src
W=$WORK
B=$W/deliver_build
PY=/work/$USER/hw3_comd/venv-deliver/bin/python           # HW3 venv, used read-only
SOFFICE=/work/$USER/hw3_comd/deliver_tools/libreoffice/opt/libreoffice26.8/program/soffice
STAGES=${STAGES:-"charts pptx png video report"}
MARK=$B/DONE
rm -f $MARK
trap 'echo "FAIL $(date +%F_%T) host=$(hostname) line=$LINENO" > $MARK' ERR

export FONTCONFIG_FILE=$SRC/fonts.conf PYTHONDONTWRITEBYTECODE=1
export MPLCONFIGDIR=$B/mplconfig XDG_CACHE_HOME=$B/xdg-cache
export SAL_USE_VCLPLUGIN=svp
mkdir -p $B/fc-cache $B/mplconfig $B/xdg-cache $B/render $W/deliverables
cd $SRC
echo "== host $(hostname) stages: $STAGES  $(date +%T)"
[[ "$(hostname)" == *lgn* || "$(hostname)" == *login* ]] && { echo "refusing to run on a login node"; exit 1; }
fc-list | grep -c "Noto Sans CJK" || true
fc-match "Microsoft JhengHei"

has() { [[ " $STAGES " == *" $1 "* ]]; }

if has charts; then
  echo "== charts $(date +%T)"; $PY make_charts.py
  mkdir -p $HW/docs/figs                    # small PNGs referenced by report.md / README
  cp -f $B/charts/*.png $HW/docs/figs/ 2>/dev/null || true
fi
if has pptx; then echo "== pptx $(date +%T)"; $PY build_pptx.py; fi
if has png; then
  echo "== soffice pptx->pdf $(date +%T)"
  rm -f $B/render/slides.pdf
  timeout 600 $SOFFICE -env:UserInstallation=file://$B/lo_profile --headless --norestore --nologo \
    --convert-to pdf --outdir $B/render $W/deliverables/slides.pptx
  cp $B/render/slides.pdf $W/deliverables/slides_preview.pdf
  $PY render_png.py
fi
if has video; then echo "== video $(date +%T)"; $PY make_video.py; fi
if has web; then
  # web copy (<= 14 MB, 1280x720) from the verified video.mp4 + the slide PNGs used in the video
  echo "== web $(date +%T)"
  FF=$($PY -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')
  DUR=$($PY -c 'import imageio_ffmpeg; print(imageio_ffmpeg.count_frames_and_secs("'$W'/deliverables/video.mp4")[1])')
  AK=96; VK=$($PY -c "print(int((14e6*8*0.92/$DUR - $AK*1000)/1000))")   # 8% container margin
  echo "duration $DUR s -> video ${VK} kbps, audio ${AK} kbps"
  $FF -v error -y -i $W/deliverables/video.mp4 -vf scale=1280:720:flags=lanczos,format=yuv420p \
      -c:v libx264 -preset slow -tune stillimage -b:v ${VK}k -maxrate $((VK*2))k -bufsize $((VK*4))k \
      -c:a aac -b:a ${AK}k -ac 1 -movflags +faststart $W/deliverables/video_web.mp4
  rm -rf $W/deliverables/slides_png && mkdir -p $W/deliverables/slides_png
  cp $B/slides/slide_*.png $W/deliverables/slides_png/
  ls -la $W/deliverables/video_web.mp4; ls $W/deliverables/slides_png | wc -l
fi
if has report; then
  if [[ -f $HW/report.md ]]; then echo "== report pdf $(date +%T)"; $PY make_report_pdf.py
  else echo "== report: $HW/report.md missing, skipped"; fi
fi

echo "== QA $(date +%T)"
$PY - <<'EOF'
import os, glob, json, subprocess, imageio_ffmpeg
W = '$WORK'
QA = f'{W}/deliver_build/qa'
os.makedirs(QA, exist_ok=True)
rp = f'{W}/deliverables/report.pdf'
if os.path.exists(rp):
    import fitz
    d = fitz.open(rp)
    fonts = sorted({f[3] for p in d for f in p.get_fonts()})
    print('report.pdf pages', d.page_count, 'fonts', fonts)
    for f in glob.glob(f'{QA}/report_p*.png'):
        os.remove(f)
    for i, page in enumerate(d):          # every page, so any one can be inspected
        page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4)).save(f'{QA}/report_p{i + 1:02d}.png')
    print('images per page:', {i + 1: len(p.get_images()) for i, p in enumerate(d) if p.get_images()})
    print('pages with TODO:', [i + 1 for i, p in enumerate(d) if 'TODO' in p.get_text()])
vp = f'{W}/deliverables/video.mp4'
if os.path.exists(vp):
    # ffprobe is not bundled with imageio-ffmpeg -> parse `ffmpeg -i` header (duration / streams / resolution)
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-i', vp], capture_output=True, text=True)
    print('\n'.join(l.strip() for l in r.stderr.splitlines() if 'Stream' in l or 'Duration' in l))
    nf, dur = imageio_ffmpeg.count_frames_and_secs(vp)
    print(f'video.mp4: {dur:.2f} s ({dur / 60:.2f} min), {nf} frames, {os.path.getsize(vp) / 1e6:.1f} MB')
EOF
$PY - <<'EOF'
from pptx import Presentation
p = Presentation('$WORK/deliverables/slides.pptx')
for i, s in enumerate(p.slides, 1):
    n = s.notes_slide.notes_text_frame.text if s.has_notes_slide else ''
    pics = sum(1 for sh in s.shapes if sh.shape_type == 13)
    txt = sum(1 for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip())
    todo = sum(1 for sh in s.shapes if sh.has_text_frame and 'TODO' in sh.text_frame.text)
    print(f'slide {i:2d}: text shapes {txt:3d}, pictures {pics}, notes {len(n)} chars, TODO shapes {todo}')
EOF
# copy small text deliverables into the repo (big ones stay on /work)
for f in slides.pptx speech.md video.srt report.pdf; do
  [[ -f $W/deliverables/$f ]] && cp -f $W/deliverables/$f $HW/docs/
done
ls -la $W/deliverables/
echo "OK $(date +%F_%T) host=$(hostname)" > $MARK
echo "== done $(date +%T)"
