"""Build slides.pptx (native editable text + speaker notes) and speech.md from content.yaml."""
import os
import sys
import copy
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

DATA = C.load()
TH = DATA['theme']
FONT = DATA['meta']['font']
CHART_DIR = os.path.join(C.BUILD, 'charts')
SW, SH = 13.333, 7.5


def col(k):
    k = TH.get(k, k)
    return RGBColor.from_string(k.lstrip('#'))


# ------------------------------------------------------------------ low level
def style_run(run, size, color, bold=False):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = col(color)
    f.name = FONT
    rPr = run._r.get_or_add_rPr()
    for tag in ('a:ea', 'a:cs'):
        el = rPr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rPr, qn(tag))
        el.set('typeface', FONT)


def fill_par(p, text, size, color, bold=False, dark=False):
    tag_col = {'b': 'dark_accent' if dark else 'accent', 'w': 'warn', 'm': 'dark_muted' if dark else 'muted'}
    for seg, tag in C.runs(text):
        r = p.add_run()
        r.text = seg
        style_run(r, size, tag_col.get(tag, color), bold=bold or tag in ('b', 'w'))


def textbox(slide, box, name=None, anchor='top', margin=0.0):
    x, y, w, h = box
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    for side in ('margin_left', 'margin_right', 'margin_top', 'margin_bottom'):
        setattr(tf, side, Inches(margin))
    tf.vertical_anchor = {'top': MSO_ANCHOR.TOP, 'middle': MSO_ANCHOR.MIDDLE,
                          'bottom': MSO_ANCHOR.BOTTOM}[anchor]
    return tf


def add_text(slide, box, text, size=16, color='text', bold=False, align='left', anchor='top',
             line=1.15, dark=False, name=None, space_after=0):
    tf = textbox(slide, box, name, anchor)
    for i, para in enumerate(str(text).split('\\n') if '\\n' in str(text) else str(text).split('\n')):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {'left': PP_ALIGN.LEFT, 'center': PP_ALIGN.CENTER, 'right': PP_ALIGN.RIGHT}[align]
        p.line_spacing = line
        if space_after:
            p.space_after = Pt(space_after)
        fill_par(p, para, size, color, bold, dark)
    return tf


def est_width_in(text, size):
    """Rough rendered width (inches): CJK = 1 em, Latin ≈ 0.55 em, plus LibreOffice CJK/Latin autospace."""
    t = C.plain(text)
    units, prev = 0.0, None
    for ch in t:
        cjk = ord(ch) > 0x2e80
        units += 1.0 if cjk else (0.3 if ch == ' ' else 0.56)
        if prev is not None and ch != ' ' and prev != cjk:
            units += 0.22
        if ch != ' ':
            prev = cjk
    return units * size / 72.0


def fit_size(text, width_in, size, min_size=22):
    while size > min_size and est_width_in(text, size) > width_in * 0.97:
        size -= 1
    return size


def set_bullet(p, size, char='•', color=None):
    pPr = p._p.get_or_add_pPr()
    ind = int(Pt(size * 1.05))
    pPr.set('marL', str(ind))
    pPr.set('indent', str(-ind))
    for t in ('a:buClr', 'a:buFont', 'a:buChar', 'a:buNone'):
        for el in pPr.findall(qn(t)):
            pPr.remove(el)
    if color:
        bc = etree.SubElement(pPr, qn('a:buClr'))
        etree.SubElement(bc, qn('a:srgbClr')).set('val', TH.get(color, color))
    etree.SubElement(pPr, qn('a:buFont')).set('typeface', 'Arial')
    etree.SubElement(pPr, qn('a:buChar')).set('char', char)


def add_bullets(slide, box, items, size=16, color='text', dark=False, gap=None, name=None,
                bullet_color='accent'):
    tf = textbox(slide, box, name)
    gap = size * 0.6 if gap is None else gap
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = 1.12
        p.space_after = Pt(gap)
        set_bullet(p, size, color=('dark_accent' if dark else bullet_color))
        fill_par(p, it, size, color, dark=dark)
    return tf


def rect(slide, box, fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06, line=None, name=None):
    x, y, w, h = box
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        s.name = name
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = col(fill)
    if line:
        s.line.color.rgb = col(line)
        s.line.width = Pt(1)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    s.text_frame.text = ''
    return s


def shape_text(s, text, size, color, bold=True, align='center'):
    tf = s.text_frame
    tf.word_wrap = True
    for side in ('margin_left', 'margin_right', 'margin_top', 'margin_bottom'):
        setattr(tf, side, Inches(0.04))
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = {'left': PP_ALIGN.LEFT, 'center': PP_ALIGN.CENTER}[align]
    fill_par(p, text, size, color, bold)


# ------------------------------------------------------------------ blocks
def b_text(sl, b, dark):
    add_text(sl, b['box'], b['text'], size=b.get('size', 16), color=b.get('color', 'dark_text' if dark else 'text'),
             bold=b.get('bold', False), align=b.get('align', 'left'), anchor=b.get('anchor', 'top'), dark=dark)


def b_bullets(sl, b, dark):
    add_bullets(sl, b['box'], b['items'], size=b.get('size', 16),
                color=b.get('color', 'dark_text' if dark else 'text'), dark=dark)


def b_stat(sl, b, dark):
    x, y, w, h = b['box']
    vs = b.get('value_size', 44)
    if b.get('inline'):
        vw = 1.75
        add_text(sl, [x, y, vw, h], b['value'], size=vs, color=b.get('color', 'accent'), bold=True,
                 anchor='middle', line=1.0)
        add_text(sl, [x + vw + 0.1, y, w - vw - 0.1, h], b['label'], size=b.get('label_size', 15),
                 color='text', anchor='middle')
        return
    vh = vs / 72 * 1.25
    add_text(sl, [x, y, w, vh], b['value'], size=vs, color=b.get('color', 'accent'), bold=True, line=1.0)
    add_text(sl, [x, y + vh + 0.05, w, h - vh - 0.05], b['label'], size=b.get('label_size', 15),
             color='muted' if not dark else 'dark_muted')


def b_card(sl, b, dark):
    x, y, w, h = b['box']
    rect(sl, b['box'], b.get('fill', 'card'))
    pad = 0.25
    cy = y + pad
    size = b.get('size', 15)
    if b.get('badge'):
        d = 0.5
        s = rect(sl, [x + pad, cy, d, d], b.get('badge_color', 'accent'), shape=MSO_SHAPE.OVAL)
        shape_text(s, b['badge'], 16, 'FFFFFF')
        narrow = w < 3.5
        if b.get('heading') and not narrow:
            add_text(sl, [x + pad + d + 0.15, cy, w - 2 * pad - d - 0.15, d], b['heading'], size=18,
                     color='ink', bold=True, anchor='middle', line=1.0)
        cy += d + 0.2
        if b.get('heading') and narrow:     # narrow card: heading on its own line under the badge
            hs = fit_size(b['heading'], w - 2 * pad, 18, 15)
            add_text(sl, [x + pad, cy, w - 2 * pad, 0.4], b['heading'], size=hs, color='ink', bold=True, line=1.0)
            cy += 0.55
            size = max(size, 16)
    elif b.get('heading'):
        hs = 18 if size >= 15 else 16
        add_text(sl, [x + pad, cy, w - 2 * pad, hs / 72 * 1.35], b['heading'], size=hs, color='ink', bold=True,
                 line=1.0)
        cy += hs / 72 * 1.35 + 0.1
    if b.get('stat'):
        add_text(sl, [x + pad, cy, w - 2 * pad, 0.95], b['stat'], size=48, color=b.get('stat_color', 'accent'),
                 bold=True, line=1.0)
        cy += 1.0
    key_h = 0.0
    if b.get('key'):
        key_h = 0.5
        add_text(sl, [x + pad, y + h - pad - key_h, w - 2 * pad, key_h], b['key'], size=size + 1,
                 color='accent', bold=True, anchor='bottom', line=1.0)
    body = b.get('body')
    if body:
        bh = y + h - pad - key_h - cy
        if isinstance(body, list):
            add_bullets(sl, [x + pad, cy, w - 2 * pad, bh], body, size=size + 1)
        else:
            add_text(sl, [x + pad, cy, w - 2 * pad, bh], body, size=size, color='text', line=1.2)


def b_image(sl, b, dark):
    x, y, w, h = b['box']
    p = os.path.join(CHART_DIR, b['chart'] + '.png') if 'chart' in b else os.path.join(C.REPO, b['path'])
    iw, ih = Image.open(p).size
    sc = min(w / iw, h / ih)
    pw, ph = iw * sc, ih * sc
    pic = sl.shapes.add_picture(p, Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2), Inches(pw), Inches(ph))
    pic.name = b.get('chart', os.path.basename(p))


def b_table(sl, b, dark):
    x, y, w, h = b['box']
    rows = [b['header']] + b['rows']
    shp = sl.shapes.add_table(len(rows), len(b['header']), Inches(x), Inches(y), Inches(w), Inches(h))
    tbl = shp.table
    # drop built-in style banding so our fills rule
    tblPr = tbl._tbl.tblPr
    for a in ('bandRow', 'firstRow'):
        tblPr.set(a, '0')
    for j, cw in enumerate(b['col_w']):
        tbl.columns[j].width = Inches(cw)
    size = b.get('size', 14)
    vc = b.get('verdict_col')
    for i, r in enumerate(rows):
        tbl.rows[i].height = Inches(h / len(rows))
        for j, val in enumerate(r):
            cell = tbl.cell(i, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = col('ink' if i == 0 else ('FFFFFF' if i % 2 else 'card'))
            cell.margin_left = cell.margin_right = Inches(0.12)
            cell.margin_top = cell.margin_bottom = Inches(0.05)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            colr, bold = ('FFFFFF', True) if i == 0 else ('text', False)
            if i > 0 and j == vc:
                bold = True
                colr = 'warn' if any(k in val for k in ('推翻', '低估', '不成立', 'FAIL')) else 'accent'
            fill_par(p, str(val), size, colr, bold)


def b_flow(sl, b, dark):
    x, y, w, h = b['box']
    steps = b['steps']
    tone_fill = {'warn': 'warn_tint', 'accent': 'accent_tint', 'neutral': 'card'}
    tone_head = {'warn': 'warn', 'accent': 'accent', 'neutral': 'ink'}
    if b.get('direction') == 'vertical':
        top = y
        if b.get('title'):
            add_text(sl, [x, y, w, 0.45], b['title'], size=16, color='ink', bold=True, line=1.0)
            top += 0.6
        n = len(steps)
        arrow = 0.32
        bh = (y + h - top - arrow * (n - 1)) / n
        for i, st in enumerate(steps):
            by = top + i * (bh + arrow)
            t = st.get('tone', 'neutral')
            rect(sl, [x, by, w, bh], tone_fill[t])
            add_text(sl, [x + 0.25, by + 0.12, w - 0.5, 0.4], st['head'], size=17, color=tone_head[t],
                     bold=True, line=1.0)
            add_text(sl, [x + 0.25, by + 0.55, w - 0.5, bh - 0.62], st['body'], size=b.get('body_size', 14), color='text',
                     line=1.15)
            if i < n - 1:
                a = rect(sl, [x + w / 2 - 0.2, by + bh + 0.04, 0.4, arrow - 0.08], 'muted',
                         shape=MSO_SHAPE.DOWN_ARROW)
        return
    n = len(steps)
    arrow = 0.42
    bw = (w - arrow * (n - 1)) / n
    for i, st in enumerate(steps):
        bx = x + i * (bw + arrow)
        t = st.get('tone', 'neutral')
        rect(sl, [bx, y, bw, h], 'accent_tint' if t == 'neutral' else tone_fill[t])
        add_text(sl, [bx + 0.15, y + 0.15, bw - 0.3, 0.45], st['head'], size=17, color='ink', bold=True,
                 align='center', line=1.0)
        add_text(sl, [bx + 0.15, y + 0.62, bw - 0.3, h - 0.7], st['body'], size=13, color='text',
                 align='center', line=1.1)
        if i < n - 1:
            rect(sl, [bx + bw + 0.08, y + h / 2 - 0.17, arrow - 0.16, 0.34], 'accent',
                 shape=MSO_SHAPE.RIGHT_ARROW)


def b_tiles(sl, b, dark):
    x, y, w, h = b['box']
    items = b['items']
    cols = b.get('cols', 2)
    rows = (len(items) + cols - 1) // cols
    gx, gy = 0.18, 0.12
    tw = (w - gx * (cols - 1)) / cols
    th = (h - gy * (rows - 1)) / rows
    fills = {'killed': 'accent', 'story': 'accent', 'equiv': '94A3B8'}
    for k, it in enumerate(items):
        r, c = divmod(k, cols)
        bx, by = x + c * (tw + gx), y + r * (th + gy)
        rect(sl, [bx, by, tw, th], fills[it['state']], radius=0.12)
        tf = textbox(sl, [bx + 0.18, by, tw - 0.36, th], anchor='middle')
        p = tf.paragraphs[0]
        p.line_spacing = 1.0
        fill_par(p, it['label'], 14, 'FFFFFF', bold=True)
        if it.get('tag'):
            p2 = tf.add_paragraph()
            p2.line_spacing = 1.0
            p2.space_before = Pt(2)
            fill_par(p2, it['tag'], 12, 'FFFFFF')
    # legend
    ly = y + h + 0.18
    lx = x
    for fillk, lab in (('accent', '被殺（判定 FAIL）'), ('94A3B8', '等價 mutant（本來就不該被殺）')):
        rect(sl, [lx, ly + 0.07, 0.22, 0.22], fillk, radius=0.2)
        add_text(sl, [lx + 0.3, ly, 3.0, 0.36], lab, size=13, color='muted', anchor='middle', line=1.0)
        lx += 2.4


TILE_STATE = {  # state -> (fill, text color, legend label)
    'killed': ('accent', 'FFFFFF', '被殺'),
    'story': ('warn', 'FFFFFF', '先存活、補測資後被殺'),
    'equiv': ('94A3B8', 'FFFFFF', '預期等價（不該被殺）'),
    'survived': ('FFFFFF', 'warn', '存活（照實列出）'),
}


def b_tilegroups(sl, b, dark):
    """Columns of small tiles (one column per group) + legend underneath."""
    x, y, w, h = b['box']
    groups = b['groups']
    gx = 0.2
    cw = (w - gx * (len(groups) - 1)) / len(groups)
    legend_h = 0.42
    head_h = 0.42
    rows = max(len(g['items']) for g in groups)
    gy = 0.07
    th = (h - legend_h - head_h - gy * (rows - 1)) / rows
    for gi, g in enumerate(groups):
        cx = x + gi * (cw + gx)
        add_text(sl, [cx, y, cw, head_h - 0.05], g['title'], size=14, color='ink', bold=True, line=1.0)
        for k, it in enumerate(g['items']):
            fillk, tcol, _ = TILE_STATE[it['state']]
            ty = y + head_h + k * (th + gy)
            s = rect(sl, [cx, ty, cw, th], fillk, radius=0.15, line='warn' if it['state'] == 'survived' else None)
            tf = textbox(sl, [cx + 0.1, ty, cw - 0.2, th], anchor='middle')
            fill_par(tf.paragraphs[0], it['label'], 11.5, tcol, bold=True)
    used = []
    for g in groups:
        for it in g['items']:
            if it['state'] not in used:
                used.append(it['state'])
    lx, ly = x, y + h - legend_h + 0.08
    for st in ('killed', 'story', 'equiv', 'survived'):
        if st not in used:
            continue
        fillk, _, lab = TILE_STATE[st]
        rect(sl, [lx, ly + 0.07, 0.2, 0.2], fillk, radius=0.2, line='warn' if st == 'survived' else None)
        add_text(sl, [lx + 0.26, ly, 2.4, 0.34], lab, size=12, color='muted', anchor='middle', line=1.0)
        lx += 0.4 + est_width_in(lab, 12)


def b_rings(sl, b, dark):
    """Verlet skin diagram: outer ring rc+skin, inner circle rc, central atom, caption below."""
    x, y, w, h = b['box']
    d_out = min(w, h - 1.6)
    cx, cy = x + w / 2, y + d_out / 2
    rect(sl, [cx - d_out / 2, cy - d_out / 2, d_out, d_out], 'accent_tint', shape=MSO_SHAPE.OVAL, line='accent')
    d_in = d_out * 0.68
    rect(sl, [cx - d_in / 2, cy - d_in / 2, d_in, d_in], 'FFFFFF', shape=MSO_SHAPE.OVAL, line='accent')
    rect(sl, [cx - 0.11, cy - 0.11, 0.22, 0.22], 'ink', shape=MSO_SHAPE.OVAL)
    add_text(sl, [cx - 1.0, cy + 0.15, 2.0, 0.4], 'i', size=14, color='ink', bold=True, align='center', line=1.0)
    add_text(sl, [cx - 1.2, cy - d_in / 2 + 0.12, 2.4, 0.4], b['inner'], size=16, color='accent', bold=True,
             align='center', line=1.0)
    add_text(sl, [cx - 1.4, cy - d_out / 2 + 0.06, 2.8, 0.4], b['outer'], size=16, color='accent', bold=True,
             align='center', line=1.0)
    add_text(sl, [x, y + d_out + 0.15, w, h - d_out - 0.15], b['caption'], size=14, color='text', line=1.2)


BLOCKS = dict(text=b_text, bullets=b_bullets, stat=b_stat, card=b_card, image=b_image, table=b_table,
              flow=b_flow, tiles=b_tiles, tilegroups=b_tilegroups, rings=b_rings)


# ------------------------------------------------------------------ layouts
def footer(sl, s, idx, n, dark):
    if s.get('source'):
        add_text(sl, [0.6, 7.02, 11.2, 0.32], s['source'], size=10.5, color='dark_muted' if dark else 'muted',
                 line=1.0, name='source')
    add_text(sl, [12.03, 7.02, 0.7, 0.32], f'{idx} / {n}', size=10.5, color='dark_muted' if dark else 'muted',
             align='right', line=1.0, name='page')


def dark_bg(sl):
    bg = sl.background.fill
    bg.solid()
    bg.fore_color.rgb = col('ink')


def lay_title(sl, s):
    dark_bg(sl)
    add_text(sl, [0.8, 0.9, 11.7, 0.45], s['kicker'], size=16, color='dark_accent', bold=True)
    add_text(sl, [0.8, 1.55, 11.7, 1.9], s['title'], size=40, color='dark_text', bold=True, line=1.12,
             name='title')
    add_text(sl, [0.8, 3.3, 11.7, 0.75], s['subtitle'], size=18, color='dark_muted')
    chips = s.get('chips', [])
    cw = (11.73 - 0.3 * (len(chips) - 1)) / max(1, len(chips))
    for i, ch in enumerate(chips):
        cx = 0.8 + i * (cw + 0.3)
        rect(sl, [cx, 4.2, cw, 1.4], '1D3550')   # chips + author kept above the video subtitle band (y > 6.3 in)
        add_text(sl, [cx + 0.25, 4.3, cw - 0.5, 0.7], ch['value'], size=30, color='dark_accent', bold=True,
                 line=1.0)
        add_text(sl, [cx + 0.25, 4.98, cw - 0.5, 0.6], ch['label'], size=13, color='dark_muted', line=1.1)
    add_text(sl, [0.8, 5.75, 6.0, 0.45], s['author'], size=20, color='dark_text', bold=True)


def lay_content(sl, s):
    add_text(sl, [0.6, 0.32, 12.13, 0.35], s.get('kicker', ''), size=14, color='accent', bold=True, line=1.0)
    add_text(sl, [0.6, 0.66, 12.13, 1.0], s['title'], size=fit_size(s['title'], 12.13, 28), color='ink',
             bold=True, line=1.08, name='title')
    for b in s.get('blocks', []):
        BLOCKS[b['type']](sl, b, False)


def lay_closing(sl, s):
    dark_bg(sl)
    add_text(sl, [0.6, 0.32, 12.13, 0.35], s.get('kicker', ''), size=14, color='dark_accent', bold=True, line=1.0)
    add_text(sl, [0.6, 0.66, 12.13, 1.0], s['title'], size=fit_size(s['title'], 12.13, 30), color='dark_text',
             bold=True, line=1.08, name='title')
    cols = s.get('columns', [])
    gap = 0.4
    cw = (12.13 - gap * (len(cols) - 1)) / max(1, len(cols))
    for i, c in enumerate(cols):
        cx = 0.6 + i * (cw + gap)
        rect(sl, [cx, 1.85, cw, 4.75], '1D3550')
        add_text(sl, [cx + 0.3, 2.05, cw - 0.6, 0.5], c['heading'], size=20, color='dark_accent', bold=True,
                 line=1.0)
        add_bullets(sl, [cx + 0.3, 2.7, cw - 0.6, 3.8], c['items'], size=15.5, color='dark_text', dark=True,
                    gap=9)
    for b in s.get('blocks', []):
        BLOCKS[b['type']](sl, b, True)


LAYOUTS = dict(title=lay_title, content=lay_content, closing=lay_closing)


def build(path):
    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    blank = prs.slide_layouts[6]
    n = len(DATA['slides'])
    for i, s in enumerate(DATA['slides'], 1):
        sl = prs.slides.add_slide(blank)
        LAYOUTS[s['layout']](sl, s)
        footer(sl, s, i, n, s['layout'] in ('title', 'closing'))
        sl.notes_slide.notes_text_frame.text = C.display(' '.join(s['notes'].split()))
    prs.core_properties.title = DATA['meta']['title']
    prs.core_properties.author = DATA['meta']['author']
    prs.save(path)
    print('pptx', path)


def write_speech(path, timings=None):
    meta = DATA['meta']
    lines, tot_all, tot_cjk = [], 0, 0
    body = []
    for i, s in enumerate(DATA['slides'], 1):
        txt = C.display(' '.join(s['notes'].split()))
        a, cjk = C.count_chars(txt)
        tot_all += a
        tot_cjk += cjk
        dur = f'，旁白 {timings[i - 1]:.0f} 秒' if timings else ''
        title = C.plain(s['title']).replace('\\n', '｜')
        body.append(f'## 第 {i} 頁｜{title}\n\n{txt}\n\n<sub>（{a} 字，其中中文 {cjk} 字{dur}）</sub>\n')
    total_t = f'；影片旁白總長 {sum(timings) / 60:.1f} 分鐘（{sum(timings):.0f} 秒）' if timings else ''
    lines.append(f'# 講稿：{meta["title"]}\n')
    lines.append(f'作者：{meta["author"]}　｜　共 {len(DATA["slides"])} 頁　｜　總字數 {tot_all}（中文 {tot_cjk} 字）{total_t}\n')
    lines.append('> 本檔由 `deliverables_src/content.yaml` 自動產生，請改內容檔後重跑 `make_all.sh`。'
                 '技術名詞（kernel、launch、WENO、Riemann solver、grindtime、profiling…）保留英文。\n')
    if meta.get('glossary'):
        lines.append('自創代號：' + meta['glossary'] + '\n')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n' + '\n'.join(body))
    print('speech', path, tot_all, tot_cjk)
    return tot_all, tot_cjk


if __name__ == '__main__':
    build(os.path.join(C.OUT, 'slides.pptx'))
    write_speech(os.path.join(C.OUT, 'speech.md'))
