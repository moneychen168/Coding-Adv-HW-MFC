"""Synthesize narration with edge-tts, one mp3 per sentence (cached by text hash).

Network I/O only -> run on the login node (compute nodes may have no internet).
Writes BUILD/tts/manifest.json used by make_video.py.
"""
import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import edge_tts

DATA = C.load()
META = DATA['meta']
# Male voice only; no female fallback (make_all.sh retries, then fails loudly).
# zh-TW-YunJheNeural was failing server-side on 2026-11-18 (NoAudioReceived for any uncached text);
# the user chose zh-CN-YunyangNeural instead.
assert META['voice'] == 'zh-CN-YunyangNeural', f"voice must be zh-CN-YunyangNeural, got {META['voice']}"
# Privacy guard: text sent to the external TTS service must not contain personal identifiers.
BLOCK = [w for w in os.environ.get('TTS_BLOCKLIST', '').split(',') if w] + [
    '$USER', 'moneychen', '@', 'hgpn', 'nchc', 'nano4', 'GOV1', 'ACD1', '/home/', '/work/']
TTS_DIR = os.path.join(C.BUILD, 'tts')
os.makedirs(TTS_DIR, exist_ok=True)


async def synth(text, path, sem):
    async with sem:
        for attempt in range(5):
            try:
                tmp = path + '.part'
                await edge_tts.Communicate(text, META['voice'], rate=META.get('rate', '+0%')).save(tmp)
                if os.path.getsize(tmp) < 1000:
                    raise RuntimeError('tiny mp3')
                os.replace(tmp, path)
                return
            except Exception as e:  # network hiccup -> retry
                print(f'  retry {attempt + 1}: {e!r}', flush=True)
                await asyncio.sleep(2 + 3 * attempt)
        raise RuntimeError(f'TTS failed: {text[:30]}')


async def main():
    sem = asyncio.Semaphore(2)
    manifest, jobs = [], []
    tot = [0, 0]
    for i, s in enumerate(DATA['slides'], 1):
        sl = []
        for disp, spk in C.sentences(s['notes']):
            bad = [w for w in BLOCK if w.lower() in spk.lower()]
            if bad:
                raise SystemExit(f'slide {i}: narration contains blocked identifier {bad}: {spk[:40]}')
            key = C.tts_key(META['voice'], META.get('rate', '+0%'), spk)
            path = os.path.join(TTS_DIR, key + '.mp3')
            sl.append({'display': disp, 'spoken': spk, 'mp3': path})
            if not os.path.exists(path):
                jobs.append(synth(spk, path, sem))
        a, cjk = C.count_chars(''.join(x['display'] for x in sl))
        tot[0] += a
        tot[1] += cjk
        print(f'slide {i:2d}: {len(sl):2d} sentences, {a:4d} chars ({cjk} CJK)')
        manifest.append({'slide': i, 'id': s['id'], 'sentences': sl})
    print(f'total {tot[0]} chars ({tot[1]} CJK); {len(jobs)} new TTS requests')
    await asyncio.gather(*jobs)
    with open(os.path.join(TTS_DIR, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump({'voice': META['voice'], 'rate': META.get('rate'), 'slides': manifest}, f,
                  ensure_ascii=False, indent=1)
    print('manifest written')


if __name__ == '__main__':
    asyncio.run(main())
