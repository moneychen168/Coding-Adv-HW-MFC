"""Render slide charts (PNG) from content.yaml `charts`. Run inside SLURM."""
import os
import sys
import glob
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

for f in glob.glob(os.path.join(C.FONT_DIR, '*.otf')):
    fm.fontManager.addfont(f)
plt.rcParams.update({
    'font.family': 'Noto Sans CJK TC',
    'font.size': 13,
    'axes.unicode_minus': False,
    'axes.edgecolor': '#AEB7C2',
    'axes.labelcolor': '#2B3A4B',
    'xtick.color': '#4A5868',
    'ytick.color': '#4A5868',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'savefig.dpi': 220,
})

DATA = C.load()
TH = DATA['theme']
INK = '#' + TH['ink']
TEXT = '#' + TH['text']
MUTED = '#' + TH['muted']
ACC = '#' + TH['accent']
WARN = '#' + TH['warn']
GRID = '#E3E8EE'
SLATE = '#5B7A99'
REFC = '#8C96A3'
CAT = [ACC, '#3B5BA9', '#B7791F']      # fixed categorical order (LJ, funcfl, setfl)
OUTDIR = os.path.join(C.BUILD, 'charts')
os.makedirs(OUTDIR, exist_ok=True)

# figure sizes = slide box sizes (inches) so fonts match slide points
BOX = {}
for s in DATA['slides']:
    for b in s.get('blocks', []):
        if b.get('type') == 'image' and 'chart' in b:
            BOX[b['chart']] = (b['box'][2], b['box'][3])


def sci(v):
    m, e = f'{v:.1e}'.split('e')
    m = m.rstrip('0').rstrip('.') if '.' in m else m
    return f'{m}e{int(e)}'


def save(fig, name):
    p = os.path.join(OUTDIR, name + '.png')
    fig.savefig(p, transparent=False, facecolor='white')
    plt.close(fig)
    print('chart', p)


def ladder(name, c):
    fig, ax = plt.subplots(figsize=BOX[name], layout='constrained')
    items = c['items'][::-1]
    lo = c['xlim'][0]
    band = c.get('band')
    if band:
        ax.axvspan(c['xlim'][0], band['hi'], color='#EEF1F5', zorder=0)
        ax.text(band['hi'] / 1.25, len(items) - 0.35, band['label'], ha='right', va='center',
                fontsize=12, color=MUTED)
    for ln in c.get('lines', []):
        ax.axvline(ln['value'], color=WARN, lw=1.6, ls=(0, (5, 3)), zorder=1)
        ax.text(ln['value'] * 1.3, -0.62, ln['label'], ha='left', va='center', fontsize=12, color=WARN)
    colors = {'pass': ACC, 'ref': REFC, 'fail': WARN}
    for i, it in enumerate(items):
        col = colors[it['cls']]
        ax.hlines(i, lo, it['value'], color=col, lw=2, alpha=0.55, zorder=2)
        ax.plot(it['value'], i, 'o', ms=11, color=col, mec='white', mew=2, zorder=3)
        lab = sci(it['value']) + ('  ' + it['note'] if it.get('note') else '')
        ax.text(it['value'] * 1.9, i, lab, va='center', ha='left', fontsize=13, zorder=4,
                color=TEXT, fontweight='bold' if it['cls'] != 'ref' else 'normal',
                bbox=dict(boxstyle='square,pad=0.15', fc='white', ec='none', alpha=0.9))
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels([it['label'] for it in items], fontsize=13)
    for t, it in zip(ax.get_yticklabels(), items):
        t.set_color({'pass': ACC, 'ref': TEXT, 'fail': WARN}[it['cls']])
    ax.set_xscale('log')
    ax.set_xlim(*c['xlim'])
    ax.set_ylim(-0.9, len(items) - 0.1)
    ax.xaxis.set_major_locator(LogLocator(base=10, numticks=20))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: (lambda e: f'1e{e}' if e % 2 == 0 else '')(int(round(__import__("math").log10(v))))))
    ax.tick_params(axis='x', labelsize=11)
    ax.grid(axis='x', color=GRID, lw=0.8)
    ax.tick_params(axis='y', length=0)
    ax.spines['left'].set_visible(False)
    ax.set_xlabel(c['xlabel'], fontsize=12, color=MUTED)
    save(fig, name)


def stacked_bars(name, c):
    fig, ax = plt.subplots(figsize=BOX[name], layout='constrained')
    cats = c['categories']
    x = range(len(cats))
    bottom = [0] * len(cats)
    cols = [SLATE, ACC]
    for k, s in enumerate(c['series']):
        ax.bar(x, s['values'], bottom=bottom, width=0.58, color=cols[k], label=s['name'],
               edgecolor='white', linewidth=2, zorder=2)
        bottom = [b + v for b, v in zip(bottom, s['values'])]
    for i, t in enumerate(c['totals']):
        ax.text(i, bottom[i] + 0.05, t + ' ms', ha='center', va='bottom', fontsize=14,
                color=INK, fontweight='bold')
    ax.set_xticks(list(x))
    ax.set_xticklabels(cats, fontsize=12)
    ax.set_ylabel(c['ylabel'], fontsize=12, color=MUTED)
    ax.set_ylim(0, max(bottom) * 1.22)
    ax.grid(axis='y', color=GRID, lw=0.8, zorder=0)
    ax.tick_params(axis='x', length=0)
    ax.legend(frameon=False, loc='upper right', fontsize=12)
    save(fig, name)


def grouped_hbar(name, c):
    fig, ax = plt.subplots(figsize=BOX[name], layout='constrained')
    cats = c['categories'][::-1]
    n = len(c['series'])
    h = 0.36
    fmt = c.get('fmt', '{v:g}×')
    vmax = max(max(float(v) for v in s['values']) for s in c['series'])
    for k, s in enumerate(c['series']):
        vals = [float(v) for v in s['values'][::-1]]
        col = ACC if s['cls'] == 'accent' else '#C3CAD4'
        ys = [i + (k - (n - 1) / 2) * (h + 0.04) for i in range(len(cats))]
        ax.barh(ys, vals, height=h, color=col, label=s['name'], zorder=2)
        for y, v in zip(ys, vals):
            ax.text(v + vmax * 0.012, y, fmt.format(v=v), va='center', ha='left', fontsize=14,
                    color=INK if s['cls'] == 'accent' else MUTED,
                    fontweight='bold' if s['cls'] == 'accent' else 'normal')
    ax.set_yticks(range(len(cats)))
    ax.set_yticklabels(cats, fontsize=14, color=TEXT)
    ax.set_xlim(0, vmax * 1.17)
    ax.set_xlabel(c['xlabel'], fontsize=12, color=MUTED)
    ax.grid(axis='x', color=GRID, lw=0.8, zorder=0)
    ax.tick_params(axis='y', length=0)
    ax.spines['left'].set_visible(False)
    hs, ls = ax.get_legend_handles_labels()
    ax.legend(hs[::-1], ls[::-1], frameon=False, loc='lower left', bbox_to_anchor=(0.0, 1.0), ncol=2,
              fontsize=12, borderaxespad=0.2)
    save(fig, name)


def roofline(name, c):
    import numpy as np
    fig, ax = plt.subplots(figsize=BOX[name], layout='constrained')
    bw = c['dram_tbs'] * 1000.0        # GFLOP/s per FLOP/B
    peak = c['peak_tflops'] * 1000.0   # GFLOP/s
    ridge = peak / bw
    xl = c.get('xlim', [0.5, 1000])
    ai = np.logspace(np.log10(xl[0]), 3, 300)
    ax.plot(ai, np.minimum(ai * bw, peak), color=INK, lw=2, zorder=2)
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlim(*xl)
    ax.set_ylim(100, 100000)
    ax.text(900, peak * 1.12, f'FP64 峰值 {c["peak_tflops"]} TFLOP/s', fontsize=12, color=INK,
            ha='right', va='bottom')
    ax.axvline(ridge, color=MUTED, lw=1, ls=':', zorder=1)
    ax.text(ridge / 1.07, 130, f'ridge {ridge:.1f}', fontsize=11, color=MUTED, va='bottom', ha='right')
    pts = c['points']
    for k, p in enumerate(pts, 1):
        if p.get('hollow'):
            ax.plot(p['ai'], p['gflops'], 'o', ms=11, mfc='white', mec=MUTED, mew=2, zorder=3)
        else:
            ax.plot(p['ai'], p['gflops'], 'o', ms=12, color=ACC, mec='white', mew=2, zorder=4)
        dx, dy, ha_, va_ = p.get('lab', [0, 11, 'center', 'bottom'])   # per-point label offset (points)
        ax.annotate(str(k), (p['ai'], p['gflops']), xytext=(dx, dy), textcoords='offset points',
                    ha=ha_, va=va_, fontsize=12, fontweight='bold',
                    color=MUTED if p.get('hollow') else INK)
    for p in pts:
        if 'arrow_to' in p:
            q = pts[p['arrow_to']]
            ax.annotate('', xy=(q['ai'] / 1.15, q['gflops']), xytext=(p['ai'] * 1.15, p['gflops']),
                        arrowprops=dict(arrowstyle='->', color=MUTED, lw=1.5), zorder=3)
    key = '\n'.join(f'{k}  {p["label"]}：峰值 {p["pct"]}' for k, p in enumerate(pts, 1))
    ax.text(0.985, 0.04, key, transform=ax.transAxes, ha='right', va='bottom', fontsize=11.5, color=TEXT,
            linespacing=1.45, bbox=dict(boxstyle='round,pad=0.5', fc='#F7F9FB', ec='#D5DBE3'))
    # DRAM roof label rotated along the slope (angle measured in display space after layout)
    fig.canvas.draw()
    x0, x1 = 0.7, 2.0
    p0 = ax.transData.transform((x0, x0 * bw))
    p1 = ax.transData.transform((x1, x1 * bw))
    ang = np.degrees(np.arctan2(p1[1] - p0[1], p1[0] - p0[0]))
    xt = max(xl[0] * 1.3, 0.04)
    ax.text(xt, xt * bw * 1.25, f'DRAM {c["dram_tbs"]} TB/s（Triad）', rotation=ang,
            rotation_mode='anchor', fontsize=11.5, color=INK, ha='left', va='bottom')
    ax.set_xlabel('arithmetic intensity（FLOP / DRAM byte）', fontsize=12, color=MUTED)
    ax.set_ylabel('FP64 GFLOP/s', fontsize=12, color=MUTED)
    ax.grid(which='major', color=GRID, lw=0.8)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:g}'))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:,.0f}'))
    save(fig, name)


def crossover(name, c):
    fig, ax = plt.subplots(figsize=BOX[name], layout='constrained')
    ax.axhspan(0.4, 1.0, color='#' + TH['warn_tint'], zorder=0)
    ax.axhline(1.0, color=WARN, lw=1.2, zorder=1)
    ax.text(1.5e7, 0.9, 'CPU 勝（< 1×）', color=WARN, fontsize=12, va='top', ha='right')
    order = sorted(range(len(c['series'])), key=lambda k: -c['series'][k]['pts'][-1][1])
    dy = {k: 15 - 15 * r for r, k in enumerate(order)}    # stack end labels: highest value on top
    for k, s in enumerate(c['series']):
        col = CAT[k]
        xs = [p[0] for p in s['pts']]
        ys = [p[1] for p in s['pts']]
        if s.get('r2'):   # previous round, dashed & faint
            ax.plot([p[0] for p in s['r2']], [p[1] for p in s['r2']], color=col, lw=1.4, ls=(0, (4, 3)),
                    alpha=0.55, zorder=1.5)
        ax.plot(xs, ys, color=col, lw=2, zorder=2)
        for p in s['pts']:
            m2 = len(p) > 2 and p[2] == 'm2'
            ax.plot(p[0], p[1], 'o', ms=9, mfc='white' if m2 else col, mec=col, mew=2, zorder=3)
        ax.annotate(s['name'], (xs[-1], ys[-1]), xytext=(12, dy[k]), textcoords='offset points',
                    va='center', ha='left', fontsize=12.5, color=col, fontweight='bold')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlim(80, 2.0e7)
    ax.set_ylim(0.4, max(p[1] for s in c['series'] for p in s['pts']) * 1.6)
    has_r2 = any(s.get('r2') for s in c['series'])
    ax.set_xlabel('原子數 N' + (c.get('legend_note', '（實線 = 新版，虛線 = r2）') if has_r2
                               else '（空心 = GPU 用前預設 mode 2）'), fontsize=12, color=MUTED)
    ax.set_ylabel(c['ylabel'], fontsize=12, color=MUTED)
    ax.grid(which='major', color=GRID, lw=0.8)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:g}×'))
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: {1e2: '100', 1e3: '1k', 1e4: '10k', 1e5: '100k', 1e6: '1M', 1e7: '10M'}.get(v, '')))
    save(fig, name)


def overlay_hbar(name, c):
    """Total bar (gray) with the inner subset overlaid (accent); labels are the given numbers only."""
    fig, ax = plt.subplots(figsize=BOX[name], layout='constrained')
    cats = c['categories'][::-1]
    tot = c['total'][::-1]
    inn = c['inner'][::-1]
    ys = range(len(cats))
    ax.barh(ys, tot, height=0.55, color='#D3D9E1', zorder=2)
    ax.barh(ys, inn, height=0.55, color=ACC, zorder=3)
    for y, t, i in zip(ys, tot, inn):
        ax.text(t + max(tot) * 0.015, y, f'{t} 個{c["total_label"]}', va='center', ha='left', fontsize=14, color=MUTED)
        ax.text(i + max(tot) * 0.015, y, f'{i} 個{c["inner_label"]}', va='center', ha='left', fontsize=14,
                color=INK, fontweight='bold', zorder=4,
                bbox=dict(boxstyle='square,pad=0.1', fc='#D3D9E1', ec='none'))
    ax.set_yticks(list(ys))
    ax.set_yticklabels(cats, fontsize=15, color=TEXT)
    ax.set_xlim(0, max(tot) * 1.32)
    ax.set_xlabel(c['xlabel'], fontsize=12, color=MUTED)
    ax.grid(axis='x', color=GRID, lw=0.8, zorder=0)
    ax.tick_params(axis='y', length=0)
    ax.spines['left'].set_visible(False)
    save(fig, name)


def kernel_groups(name, c):
    """Grouped stacked columns: per potential, bars r2 / P1 / P2 with segment values labelled inside."""
    fig, ax = plt.subplots(figsize=BOX[name], layout='constrained')
    kcol = {'scan': '#AEB9C7', 'f0': '#C3CAD4', 'f1': SLATE, 'f2': ACC, 'warn': WARN}
    x, ticks, labels, gpos = 0.0, [], [], []
    for g in c['groups']:            # values may be strings ('1.90') to keep trailing zeros in labels
        for b in g['bars']:
            b['segs'] = [[s[0], float(s[1]), s[2], s[1] if isinstance(s[1], str) else f'{s[1]:g}']
                         for s in b['segs']]
    ymax = max(sum(s[1] for s in b['segs']) for g in c['groups'] for b in g['bars'])
    for gi, g in enumerate(c['groups']):
        start = x
        for b in g['bars']:
            bot = 0.0
            for seg in b['segs']:
                ax.bar(x, seg[1], bottom=bot, width=0.72, color=kcol[seg[2]], edgecolor='white', linewidth=2,
                       zorder=2)
                if seg[1] >= ymax * 0.07:
                    ax.text(x, bot + seg[1] / 2, seg[3], ha='center', va='center', fontsize=11.5,
                            color=INK if seg[2] in ('scan', 'f0') else 'white', zorder=3)
                bot += seg[1]
            ticks.append(x)
            labels.append(f'{g["name"]}\n{b["label"]}')
            x += 1.0
        x += 0.7
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=12.5)
    ax.set_ylim(0, ymax * 1.08)
    ax.set_ylabel(c['ylabel'], fontsize=12, color=MUTED)
    ax.grid(axis='y', color=GRID, lw=0.8, zorder=0)
    ax.tick_params(axis='x', length=0)
    from matplotlib.patches import Patch
    ax.legend([Patch(color=kcol[k]) for k, _ in c['legend']], [l for _, l in c['legend']], frameon=False,
              loc='upper right', fontsize=11.5)
    save(fig, name)


def _has_todo(node):
    if isinstance(node, dict):
        return any(_has_todo(v) for k, v in node.items() if k != 'pending')
    if isinstance(node, list):
        return any(_has_todo(v) for v in node)
    return isinstance(node, str) and 'TODO' in node


def placeholder(name, c):
    """Data not available yet (values still TODO): draw an explicit placeholder, never fake numbers."""
    fig, ax = plt.subplots(figsize=BOX[name], layout='constrained')
    ax.set_axis_off()
    ax.add_patch(plt.Rectangle((0.02, 0.02), 0.96, 0.96, transform=ax.transAxes, fc='#F7F9FB', ec='#C9D1DB',
                               lw=1.5, ls=(0, (6, 4))))
    ax.text(0.5, 0.55, 'TODO：等待結果檔', ha='center', va='center', fontsize=22, color=WARN, fontweight='bold',
            transform=ax.transAxes)
    ax.text(0.5, 0.42, c.get('pending', name), ha='center', va='center', fontsize=13, color=MUTED,
            transform=ax.transAxes, wrap=True)
    save(fig, name)


def bars(name, c):
    """Vertical bars (e.g. grindtime per version); value labels as given strings; optional ratio labels."""
    fig, ax = plt.subplots(figsize=BOX[name], layout='constrained')
    cats = [it['label'] for it in c['items']]
    vals = [float(it['value']) for it in c['items']]
    cols = [{'base': '#C3CAD4', 'step': SLATE, 'final': ACC, 'neg': WARN}[it.get('cls', 'step')] for it in c['items']]
    xs = range(len(cats))
    ax.bar(xs, vals, width=0.62, color=cols, zorder=2)
    vmax = max(vals)
    for x, it, v in zip(xs, c['items'], vals):
        lab = str(it['value']) + c.get('unit', '')
        ax.text(x, v + vmax * 0.02, lab, ha='center', va='bottom', fontsize=13, color=INK, fontweight='bold')
        if it.get('note'):
            ax.text(x, v / 2, it['note'], ha='center', va='center', fontsize=12, color='white', fontweight='bold')
    ax.set_xticks(list(xs))
    ax.set_xticklabels(cats, fontsize=12)
    ax.set_ylim(0, vmax * 1.18)
    ax.set_ylabel(c['ylabel'], fontsize=12, color=MUTED)
    ax.grid(axis='y', color=GRID, lw=0.8, zorder=0)
    ax.tick_params(axis='x', length=0)
    save(fig, name)


def share_hbar(name, c):
    """Horizontal bars of time share (%) per kernel / phase, largest first; labels = given strings."""
    fig, ax = plt.subplots(figsize=BOX[name], layout='constrained')
    items = c['items'][::-1]
    vals = [float(it['value']) for it in items]
    ys = range(len(items))
    cols = [ACC if it.get('hl') else '#C3CAD4' for it in items]
    ax.barh(ys, vals, height=0.6, color=cols, zorder=2)
    vmax = max(vals)
    for y, it, v in zip(ys, items, vals):
        ax.text(v + vmax * 0.015, y, str(it['value']) + c.get('unit', '%'), va='center', ha='left', fontsize=13,
                color=INK if it.get('hl') else MUTED, fontweight='bold' if it.get('hl') else 'normal')
    ax.set_yticks(list(ys))
    ax.set_yticklabels([it['label'] for it in items], fontsize=12.5, color=TEXT)
    ax.set_xlim(0, vmax * 1.2)
    ax.set_xlabel(c['xlabel'], fontsize=12, color=MUTED)
    ax.grid(axis='x', color=GRID, lw=0.8, zorder=0)
    ax.tick_params(axis='y', length=0)
    ax.spines['left'].set_visible(False)
    save(fig, name)


def _median(v):
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def final_grind(name, c):
    """Final results straight from results/final/results.tsv: median grind per (case, config), two panels."""
    import csv
    rows = list(csv.DictReader(open(os.path.expanduser(c['tsv'])), delimiter='\t'))
    med = {}
    for r in rows:
        med.setdefault((r['case'], r['config']), []).append(float(r['grind_ns']))
    med = {k: _median(v) for k, v in med.items()}
    panels = c['panels']
    widths = [len(pn['configs']) for pn in panels]
    fig, axes = plt.subplots(1, len(panels), figsize=BOX[name], layout='constrained',
                             gridspec_kw={'width_ratios': widths})
    colmap = {'base': '#C3CAD4', 'bit': ACC, 'full': SLATE, 'co': '#B7791F'}
    for ax, pn in zip(axes, panels):
        base = med[(pn['case'], 'baseline')]
        xs = range(len(pn['configs']))
        vals = [med[(pn['case'], cf['key'])] for cf in pn['configs']]
        ax.bar(xs, vals, width=0.66, color=[colmap[cf['cls']] for cf in pn['configs']], zorder=2)
        for x, v, cf in zip(xs, vals, pn['configs']):
            ax.text(x, v + max(vals) * 0.02, f'{v:.3f}\n{base / v:.2f}×', ha='center', va='bottom', fontsize=11.5,
                    color=INK, fontweight='bold' if cf['cls'] == 'bit' else 'normal', linespacing=1.1)
        ax.set_xticks(list(xs))
        ax.set_xticklabels([cf['label'] for cf in pn['configs']], fontsize=10.5)
        ax.set_ylim(0, max(vals) * 1.32)
        ax.set_title(pn['title'], fontsize=12.5, color=INK, loc='left')
        ax.grid(axis='y', color=GRID, lw=0.8, zorder=0)
        ax.tick_params(axis='x', length=0)
    axes[0].set_ylabel(c['ylabel'], fontsize=11.5, color=MUTED)
    print('final_grind medians', {f'{k[0]}/{k[1]}': round(v, 5) for k, v in med.items()})
    save(fig, name)


def kernel_ba(name, c):
    """Before/after kernel time per group, parsed from results/final/profile_before_after.txt."""
    lines = open(os.path.expanduser(c['src'])).read().splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith('group\t'))
    groups = []
    for l in lines[i + 1:]:
        if not l.strip() or l.startswith('nvtx') or l.startswith('#'):
            break
        f = l.split('\t')
        groups.append((f[0], float(f[1]), float(f[3])))
    labels = c.get('labels', {})
    groups = [g for g in groups if g[0].split()[0] not in c.get('skip', [])]
    groups = groups[::-1]
    fig, ax = plt.subplots(figsize=BOX[name], layout='constrained')
    h = 0.38
    ys = range(len(groups))
    ax.barh([y + h / 2 for y in ys], [g[1] for g in groups], height=h, color='#C3CAD4', label=c['before'], zorder=2)
    ax.barh([y - h / 2 for y in ys], [g[2] for g in groups], height=h, color=ACC, label=c['after'], zorder=2)
    vmax = max(g[1] for g in groups)
    for y, g in zip(ys, groups):
        ax.text(g[1] + vmax * 0.01, y + h / 2, f'{g[1]:.2f} s', va='center', fontsize=11, color=MUTED)
        sp = '已移除' if g[2] == 0 else f'{g[2]:.2f} s（{g[1] / g[2]:.2f}×）'
        ax.text(g[2] + vmax * 0.01, y - h / 2, sp, va='center', fontsize=11, color=INK, fontweight='bold')
    ax.set_yticks(list(ys))
    ax.set_yticklabels([labels.get(g[0].split()[0], g[0].split()[0]) for g in groups], fontsize=12, color=TEXT)
    ax.set_xlim(0, vmax * 1.3)
    ax.set_xlabel(c['xlabel'], fontsize=11.5, color=MUTED)
    ax.grid(axis='x', color=GRID, lw=0.8, zorder=0)
    ax.tick_params(axis='y', length=0)
    ax.spines['left'].set_visible(False)
    ax.legend(frameon=False, loc='lower right', fontsize=11.5)
    save(fig, name)


KINDS = dict(ladder=ladder, stacked_bars=stacked_bars, grouped_hbar=grouped_hbar,
             roofline=roofline, crossover=crossover, overlay_hbar=overlay_hbar, kernel_groups=kernel_groups,
             bars=bars, share_hbar=share_hbar, final_grind=final_grind, kernel_ba=kernel_ba)

if __name__ == '__main__':
    for name, spec in DATA['charts'].items():
        if name not in BOX:
            print('skip (unused)', name)
            continue
        (placeholder if _has_todo(spec) else KINDS[spec['kind']])(name, spec)
