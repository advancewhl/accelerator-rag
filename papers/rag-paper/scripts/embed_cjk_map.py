"""Embed a self-contained ToUnicode CMap for Adobe-GB1 Chinese fonts.

Preserve glyph programs, content streams, page geometry, and mathematics.
This avoids depending on a viewer's external Adobe-GB1-UCS2 resources.
"""
import argparse
from pathlib import Path
import sys

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, DecodedStreamObject
except ImportError:
    sys.path.append('/home/whloong/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages')
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, DecodedStreamObject


def embed(path):
    reader = PdfReader(path)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    cmap = DecodedStreamObject()
    cmap.set_data((Path(__file__).resolve().parents[1] / 'fonts/Adobe-GB1-UCS2').read_bytes())
    cmap_ref = None
    seen = set()
    repaired = []

    def visit(resources):
        nonlocal cmap_ref
        resources = resources.get_object()
        for font in resources.get('/Font', {}).values():
            font = font.get_object()
            if id(font) in seen:
                continue
            seen.add(id(font))
            descendants = font.get('/DescendantFonts', [])
            if not descendants or '/ToUnicode' in font:
                continue
            info = descendants[0].get_object().get('/CIDSystemInfo', {})
            if (info.get('/Registry'), info.get('/Ordering')) != ('Adobe', 'GB1'):
                continue
            if font.get('/Encoding') != '/Identity-H':
                raise ValueError('Adobe-GB1 map requires Identity-H character-to-CID encoding')
            if cmap_ref is None:
                cmap_ref = writer._add_object(cmap.flate_encode())
            font[NameObject('/ToUnicode')] = cmap_ref
            repaired.append(str(font.get('/BaseFont')))
        for obj in resources.get('/XObject', {}).values():
            obj = obj.get_object()
            if obj.get('/Subtype') == '/Form' and '/Resources' in obj:
                visit(obj['/Resources'])

    for page in writer.pages:
        visit(page['/Resources'])
    if repaired:
        temp = path.with_suffix('.fontmap-tmp.pdf')
        writer.write(temp)
        temp.replace(path)
    print(f'Embedded Adobe-GB1 ToUnicode map: {len(repaired)} font subsets; {len(reader.pages)} pages preserved.')
    for name in repaired:
        print('  ' + name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    embed(parser.parse_args().pdf)
