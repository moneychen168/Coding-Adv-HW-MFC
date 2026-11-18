"""Assemble video.mp4 (1920x1080, H.264 + AAC, burned-in subtitles) + video.srt. Run inside SLURM.

Inputs: BUILD/slides/slide_NN.png (rendered from slides.pptx), BUILD/tts/manifest.json (tts.py).
"""
import os
import re
import sys
import json
import wave
import shutil
import subprocess
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import build_pptx

DATA = C.load()
META = DATA['meta']
FF = imageio_ffmpeg.get_ffmpeg_exe()
SLIDES = os.path.join(C.BUILD, 'slides')
VB = os.path.join(C.BUILD, 'video')
shutil.rmtree(VB, ignore_errors=True)
os.makedirs(os.path.join(VB, 'frames'))
os.makedirs(os.path.join(VB, 'wav'))
RATE = 24000
W, H = 1920, 1080
FONT = ImageFont.truetype(os.path.join(C.FONT_DIR, 'NotoSansCJKtc-Medium.otf'), 40)
MAXW = 1640


def mp3_to_wav(mp3):
    out = os.path.join(VB, 'wav', os.path.basename(mp3)[:-4] + '.wav')
    if not os.path.exists(out):
        subprocess.run([FF, '-v', 'error', '-y', '-i', mp3, '-ac', '1', '-ar', str(RATE), '-sample_fmt', 's16',
                        out], check=True)
    with wave.open(out) as w:
        return out, w.readframes(w.getnframes())


def wlen(s):
    return sum(1 if ord(ch) > 0x2e80 else 0.55 for ch in s)


def split_cues(text, maxc):
    """Split one sentence into subtitle cues (each <= 2 lines of ~maxc)."""
    if wlen(text) <= maxc * 1.9:
        return [text]
    chunks = re.findall(r'[^，；：、]+[，；：、]?', text)
    cues, cur = [], ''
    for ch in chunks:
        if cur and wlen(cur + ch) > maxc * 1.6:
            cues.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        cues.append(cur)
    # a chunk that is itself too long: hard-split
    out = []
    for c in cues:
        while wlen(c) > maxc * 1.9:
            k, acc = 0, 0
            while acc < maxc * 1.5:
                acc += wlen(c[k])
                k += 1
            out.append(c[:k])
            c = c[k:]
        out.append(c)
    return out


def wrap(text):
    lines, cur = [], ''
    draw = ImageDraw.Draw(Image.new('RGB', (10, 10)))
    for ch in text:
        if draw.textlength(cur + ch, font=FONT) > MAXW and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    # balance two lines
    if len(lines) == 2:
        full = ''.join(lines)
        best = None
        for k in range(1, len(full)):
            if full[k - 1].isascii() and full[k].isascii() and (full[k - 1].isalnum() or full[k - 1] in '-_./') \
                    and (full[k].isalnum() or full[k] in '-_./'):
                continue                       # never break inside a Latin word / identifier
            a, b = full[:k], full[k:]
            la, lb = draw.textlength(a, font=FONT), draw.textlength(b, font=FONT)
            if la <= MAXW and lb <= MAXW:
                score = abs(la - lb) - (60 if a[-1] in '，；：、 ' else 0)
                if best is None or score < best[0]:
                    best = (score, [a.rstrip(), b.lstrip()])
        if best:
            lines = best[1]
    return lines


def frame_with_sub(slide_png, text, out):
    im = Image.open(slide_png).convert('RGB').resize((W, H))
    if text:
        lines = wrap(text)
        lh = 54
        bh = lh * len(lines) + 30
        draw = ImageDraw.Draw(im, 'RGBA')
        widths = [draw.textlength(l, font=FONT) for l in lines]
        bw = max(widths) + 64
        x0 = (W - bw) / 2
        y0 = H - 28 - bh
        draw.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=14, fill=(10, 20, 32, 205))
        for i, (l, lw) in enumerate(zip(lines, widths)):
            draw.text(((W - lw) / 2, y0 + 13 + i * lh), l, font=FONT, fill=(255, 255, 255))
    im.save(out)


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def main():
    man = json.load(open(os.path.join(C.BUILD, 'tts', 'manifest.json'), encoding='utf-8'))
    assert len(man['slides']) == len(DATA['slides']), 'manifest out of date: rerun tts.py'
    lead, gap, tail = META['lead_s'], META['gap_s'], META['tail_s']
    maxc = META.get('subtitle_max_chars', 30)
    pcm = bytearray()
    sil = lambda sec: b'\x00\x00' * int(round(sec * RATE))
    concat, srt, timings = [], [], []
    t = 0.0
    fidx = 0
    speech_s, nchars = 0.0, 0
    for sm in man['slides']:
        i = sm['slide']
        png = os.path.join(SLIDES, f'slide_{i:02d}.png')
        plain_f = os.path.join(VB, 'frames', f's{i:02d}_plain.png')
        frame_with_sub(png, None, plain_f)
        t_slide0 = t
        pcm += sil(lead)
        concat.append((plain_f, lead))
        t += lead
        for k, se in enumerate(sm['sentences']):
            _, data = mp3_to_wav(se['mp3'])
            d = len(data) / 2 / RATE
            pcm += data
            speech_s += d
            nchars += C.count_chars(se['display'])[0]
            cues = split_cues(se['display'], maxc)
            tot = sum(wlen(c) for c in cues)
            for c in cues:
                cd = d * wlen(c) / tot
                fidx += 1
                f = os.path.join(VB, 'frames', f'c{fidx:04d}.png')
                frame_with_sub(png, c, f)
                concat.append((f, cd))
                srt.append((t, t + cd, c))
                t += cd
            g = gap if k < len(sm['sentences']) - 1 else tail
            pcm += sil(g)
            concat.append((plain_f, g))
            t += g
        timings.append(t - t_slide0)
        print(f'slide {i:2d}: {t - t_slide0:6.1f} s')
    wav_all = os.path.join(VB, 'narration.wav')
    with wave.open(wav_all, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(pcm))
    lst = os.path.join(VB, 'concat.txt')
    with open(lst, 'w') as f:
        for p, d in concat:
            f.write(f"file '{p}'\nduration {d:.4f}\n")
        f.write(f"file '{concat[-1][0]}'\n")
    out_mp4 = os.path.join(C.OUT, 'video.mp4')
    cmd = [FF, '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-i', wav_all,
           '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
           '-tune', 'stillimage', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2',
           '-shortest', '-movflags', '+faststart', out_mp4]
    subprocess.run(cmd, check=True)
    with open(os.path.join(C.OUT, 'video.srt'), 'w', encoding='utf-8') as f:
        for n, (a, b, c) in enumerate(srt, 1):
            f.write(f'{n}\n{srt_time(a)} --> {srt_time(b)}\n{c}\n\n')
    cpm_speech = nchars / (speech_s / 60)
    cpm_total = nchars / (t / 60)
    json.dump({'slide_seconds': timings, 'total_seconds': t, 'chars': nchars, 'speech_seconds': speech_s,
               'cpm_speech_only': cpm_speech, 'cpm_with_pauses': cpm_total, 'voice': man['voice'],
               'rate': man['rate']}, open(os.path.join(C.BUILD, 'timing.json'), 'w'), indent=1)
    print(f'chars {nchars}; speech {speech_s:.1f} s -> {cpm_speech:.0f} chars/min (speech only), '
          f'{cpm_total:.0f} chars/min incl. pauses; voice {man["voice"]} rate {man["rate"]}')
    build_pptx.write_speech(os.path.join(C.OUT, 'speech.md'), timings)
    print(f'video {out_mp4}: {t:.1f} s ({t / 60:.2f} min), {len(srt)} cues')
    # verify container
    r = subprocess.run([FF, '-hide_banner', '-i', out_mp4], capture_output=True, text=True)
    print('\n'.join(l for l in r.stderr.splitlines() if 'Stream' in l or 'Duration' in l))


if __name__ == '__main__':
    main()
