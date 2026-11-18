"""slides.pdf (LibreOffice export of slides.pptx) -> BUILD/slides/slide_NN.png at 1920x1080."""
import os
import sys
import glob
import fitz  # PyMuPDF

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

pdf = os.path.join(C.BUILD, 'render', 'slides.pdf')
out = os.path.join(C.BUILD, 'slides')
os.makedirs(out, exist_ok=True)
for f in glob.glob(os.path.join(out, 'slide_*.png')):
    os.remove(f)
doc = fitz.open(pdf)
for i, page in enumerate(doc, 1):
    z = 1920 / page.rect.width
    pix = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
    p = os.path.join(out, f'slide_{i:02d}.png')
    pix.save(p)
    print(p, pix.width, pix.height)
