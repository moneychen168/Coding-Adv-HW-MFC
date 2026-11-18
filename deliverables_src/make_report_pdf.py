"""$HW/report.md -> deliverables/report.pdf (WeasyPrint, Noto Sans CJK TC, figures embedded).

report.md itself is not modified. Figures listed in its「附錄：圖」section (incl. globs) are embedded
there as images with their path as caption.
"""
import os
import re
import sys
import glob
import html
from markdown_it import MarkdownIt
from weasyprint import HTML, CSS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

SRC_MD = os.path.join(C.REPO, 'report.md')
HEADER = 'MFC 在 NVIDIA H200 上的效能優化報告'
FONT = C.FONT_DIR


def embed_appendix(md):
    head = re.search(r'^## 附錄：圖\s*$', md, re.M)
    if not head:
        return md
    body = md[head.end():]
    out = [md[:head.end()], '\n\n']
    seen = set()
    for line in body.splitlines():
        if not line.strip().startswith('-'):
            continue
        note = re.sub(r'`[^`]+`', '', line).strip(' -、，')
        for pat in re.findall(r'`([^`]+\.png)`', line):
            for p in sorted(glob.glob(os.path.join(C.REPO, pat))):
                rel = os.path.relpath(p, C.REPO)
                if rel in seen:
                    continue
                seen.add(rel)
                out.append(f'<figure><img src="file://{p}"/><figcaption><code>{html.escape(rel)}</code>'
                           f' {html.escape(note)}</figcaption></figure>\n\n')
    return ''.join(out)


CSS_TXT = f"""
@font-face {{ font-family: 'NotoTC'; src: url('file://{FONT}/NotoSansCJKtc-Regular.otf'); font-weight: 400; }}
@font-face {{ font-family: 'NotoTC'; src: url('file://{FONT}/NotoSansCJKtc-Medium.otf'); font-weight: 500; }}
@font-face {{ font-family: 'NotoTC'; src: url('file://{FONT}/NotoSansCJKtc-Bold.otf'); font-weight: 700; }}
@page {{ size: A4; margin: 16mm 14mm 18mm 14mm;
  @bottom-center {{ content: counter(page) " / " counter(pages); font: 8pt 'NotoTC'; color: #64748B; }}
  @top-right {{ content: "{HEADER}"; font: 7.5pt 'NotoTC'; color: #94A3B8; }} }}
html {{ font-family: 'NotoTC', sans-serif; font-size: 9.6pt; line-height: 1.55; color: #1F2D3D; }}
h1 {{ font-size: 19pt; color: #12263A; margin: 0 0 8pt; }}
h2 {{ font-size: 14pt; color: #12263A; border-bottom: 1.2pt solid #D5DBE3; padding-bottom: 3pt;
      margin-top: 18pt; break-after: avoid; }}
h3 {{ font-size: 11.5pt; color: #0E7C7B; margin-top: 13pt; break-after: avoid; }}
p, li {{ orphans: 2; widows: 2; }}
blockquote {{ margin: 6pt 0; padding: 4pt 10pt; background: #F2F4F7; color: #475569; border-radius: 4pt; }}
code {{ font-family: 'DejaVu Sans Mono', 'NotoTC', monospace; font-size: 0.86em; background: #F2F4F7;
        padding: 0 2pt; border-radius: 2pt; overflow-wrap: anywhere; }}
pre {{ background: #F2F4F7; padding: 6pt 8pt; border-radius: 4pt; white-space: pre-wrap;
       overflow-wrap: anywhere; font-size: 8pt; }}
pre code {{ background: none; padding: 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 7.8pt; line-height: 1.35;
         table-layout: auto; }}
th {{ background: #12263A; color: white; font-weight: 700; }}
th, td {{ border: 0.5pt solid #C9D1DB; padding: 2.5pt 4pt; vertical-align: top; overflow-wrap: break-word; }}
td code, th code {{ overflow-wrap: anywhere; }}
table.wide {{ font-size: 6.9pt; }}
table.wide th, table.wide td {{ padding: 2pt 2.6pt; }}
table.xwide {{ font-size: 6.4pt; }}
table.xwide th, table.xwide td {{ padding: 1.8pt 2.2pt; }}
tr:nth-child(even) td {{ background: #F7F9FB; }}
tr {{ break-inside: avoid; }}
hr {{ border: none; border-top: 0.8pt solid #D5DBE3; margin: 12pt 0; }}
p > img {{ display: block; margin: 6pt auto; max-width: 100%; max-height: 95mm; object-fit: contain; }}
figure {{ margin: 8pt 0 14pt; break-inside: avoid; text-align: center; }}
figure img {{ max-width: 100%; max-height: 120mm; }}
figcaption {{ font-size: 8pt; color: #64748B; margin-top: 3pt; }}
"""


def main():
    md = open(SRC_MD, encoding='utf-8').read()
    md = embed_appendix(md)
    # CommonMark + GFM tables: report.md uses lists right after a paragraph and 2-space nesting
    body = MarkdownIt('commonmark', {'html': True}).enable('table').render(md)

    def tag_table(m):                 # shrink font for wide tables so cells don't break mid-number
        t = m.group(0)
        head = t.split('</tr>', 1)[0]
        n = head.count('<th')
        cls = ' class="xwide"' if n >= 11 else (' class="wide"' if n >= 8 else '')
        return t.replace('<table>', f'<table{cls}>', 1)
    body = re.sub(r'<table>.*?</table>', tag_table, body, flags=re.S)
    doc = f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>MFC 效能優化報告</title></head><body>{body}</body></html>'
    with open(os.path.join(C.BUILD, 'report.html'), 'w', encoding='utf-8') as f:
        f.write(doc)
    out = os.path.join(C.OUT, 'report.pdf')
    HTML(string=doc, base_url=C.REPO).write_pdf(out, stylesheets=[CSS(string=CSS_TXT)])
    print('report', out, os.path.getsize(out))


if __name__ == '__main__':
    main()
