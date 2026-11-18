"""Shared paths and text helpers for the MFC (Coding-Adv-HW) deliverables pipeline."""
import os
import re
import hashlib
import yaml

SRC = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SRC)                       # $HW
WORK = '$WORK'
OUT = os.path.join(WORK, 'deliverables')
BUILD = os.path.join(WORK, 'deliver_build')
TOOLS = '/work/$USER/hw3_comd/deliver_tools'     # LibreOffice + Noto CJK fonts, reused READ-ONLY from HW3
FONT_DIR = os.path.join(TOOLS, 'fonts')
SOFFICE = os.path.join(TOOLS, 'libreoffice/opt/libreoffice26.8/program/soffice')
CONTENT = os.environ.get('DELIVER_CONTENT') or os.path.join(SRC, 'content.yaml')   # override for smoke tests

for d in (OUT, BUILD):
    os.makedirs(d, exist_ok=True)


_VAR = re.compile(r'\$\{(\w+)\}')


def _fmt(v):
    return v if isinstance(v, str) else (f'{v:g}' if isinstance(v, float) else str(v))


def _subst(node, vs):
    if isinstance(node, dict):
        return {k: _subst(v, vs) for k, v in node.items()}
    if isinstance(node, list):
        return [_subst(v, vs) for v in node]
    if isinstance(node, str):
        m = _VAR.fullmatch(node.strip())
        if m and m.group(1) in vs and not isinstance(vs[m.group(1)], str):
            return vs[m.group(1)]                      # whole string = one numeric var -> number
        def rep(mm):
            if mm.group(1) not in vs:
                raise KeyError(f'content.yaml: undefined ${{{mm.group(1)}}}')
            return _fmt(vs[mm.group(1)])
        return _VAR.sub(rep, node)
    return node


def load():
    with open(CONTENT, encoding='utf-8') as f:
        data = yaml.safe_load(f)
    vs = data.pop('vars', {}) or {}
    return _subst(data, vs)


# ---------------------------------------------------------------- slide markup
_TAG = re.compile(r'<(b|w|m)>(.*?)</\1>', re.S)


def runs(text):
    """'a <b>x</b> c' -> [('a ', None), ('x', 'b'), (' c', None)]"""
    out, pos = [], 0
    for m in _TAG.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], None))
        out.append((m.group(2), m.group(1)))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], None))
    return out


def plain(text):
    return _TAG.sub(lambda m: m.group(2), text)


# ---------------------------------------------------------------- notes markup
_SAY = re.compile(r'\{([^{}|]*)\|([^{}]*)\}')


def display(s):
    return _SAY.sub(lambda m: m.group(1), s).strip()


def spoken(s):
    return _SAY.sub(lambda m: m.group(2), s).strip()


def sentences(notes):
    """Split marked-up notes into [(display, spoken)] at 。！？ (outside {..})."""
    notes = ' '.join(notes.split())
    parts, buf, depth = [], '', 0
    for ch in notes:
        buf += ch
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        elif ch in '。！？' and depth == 0:
            parts.append(buf.strip())
            buf = ''
    if buf.strip():
        parts.append(buf.strip())
    return [(display(p), spoken(p)) for p in parts]


def count_chars(s):
    """(字數, 純中文字數). 字數 = 中文字 + 全形標點 + 英文詞/數字（每個 token 算 1）."""
    cjk = len(re.findall(r'[㐀-鿿]', s))
    punct = len(re.findall(r'[　-〿＀-￯]', s))
    words = len(re.findall(r'[A-Za-z0-9][A-Za-z0-9_.\-/+%=×]*', s))
    return cjk + punct + words, cjk


def tts_key(voice, rate, text):
    return hashlib.sha1(f'{voice}|{rate}|{text}'.encode()).hexdigest()[:16]
