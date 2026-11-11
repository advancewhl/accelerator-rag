"""Build the Chinese review manuscript with real LaTeX-compatible formula rendering.

Source: rag-chapter.md. No browser/CDN, TeX installation, or model inference required.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/rag-paper-matplotlib")
BUNDLED = Path("/home/whloong/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages")
try:
    import reportlab
except ImportError:
    if BUNDLED.exists():
        sys.path.append(str(BUNDLED))
    import reportlab

import matplotlib
matplotlib.use("Agg")
from matplotlib import mathtext
from matplotlib.font_manager import FontProperties
from fontTools.ttLib import TTFont as FontToolsFont
from PIL import Image as PILImage
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                               Spacer, Table, TableStyle, Image, KeepTogether,
                               PageBreak, Flowable)
from reportlab.platypus.tableofcontents import TableOfContents

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[1]
PDF = ROOT / "output/pdf/rag-thesis-chapter.pdf"
EQ = OUT / "equations"
QA = OUT / "qa"
PAGE_W, PAGE_H = A4
LEFT, RIGHT, TOP, BOTTOM = 49, 49, 48, 46
TEXT_W = PAGE_W - LEFT - RIGHT
LATIN_PATH = "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf"
LATIN_BOLD_PATH = "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf"
CJK_PATH = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
pdfmetrics.registerFont(TTFont("BodyLatin", LATIN_PATH))
pdfmetrics.registerFont(TTFont("BodyLatinBold", LATIN_BOLD_PATH))
pdfmetrics.registerFont(TTFont("BodyCJK", CJK_PATH))
pdfmetrics.registerFont(TTFont("MonoLatin", "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf"))
LATIN_CMAP = FontToolsFont(LATIN_PATH).getBestCmap()
CJK_CMAP = FontToolsFont(CJK_PATH).getBestCmap()
MISSING = set()
EQUATIONS = []


def runs(text, bold=False, mono=False):
    output, current, buffer = [], None, []
    for c in text:
        if ord(c) in LATIN_CMAP:
            name = "MonoLatin" if mono else "BodyLatinBold" if bold else "BodyLatin"
        else:
            name = "BodyCJK"
            if ord(c) not in CJK_CMAP and not c.isspace():
                MISSING.add(c)
        if name != current and buffer:
            output.append(f'<font name="{current}">{html.escape("".join(buffer))}</font>')
            buffer = []
        buffer.append(c); current = name
    if buffer:
        output.append(f'<font name="{current}">{html.escape("".join(buffer))}</font>')
    return "".join(output)


def math_asset(latex, size=10.2, display=False):
    digest = hashlib.sha256(f"{size}:{latex}".encode()).hexdigest()[:12]
    stem = f"eq-{len(EQUATIONS)+1:02d}" if display else f"inline-{digest}"
    path = EQ / f"{stem}.png"
    prop = FontProperties(size=size, math_fontfamily="dejavuserif")
    mathtext.math_to_image("$" + latex + "$", path, prop=prop, dpi=600, format="png", color="#202020")
    im = PILImage.open(path)
    width, height = im.width * 72 / 600, im.height * 72 / 600
    (EQ / f"{stem}.tex").write_text("\\[\n" + latex + "\n\\]\n")
    if display:
        EQUATIONS.append({"number": len(EQUATIONS)+1, "latex": latex, "image": path.name,
                          "width_pt": width, "height_pt": height, "font_size_pt": size})
    return path, width, height


def inline(text, size=10.2, bold=False):
    pattern = r"(\\\(.*?\\\)|`[^`]+`|\*\*.*?\*\*|\[[^\]]+\]\([^)]+\))"
    parts = re.split(pattern, text)
    result = []
    for part in parts:
        if part.startswith("\\("):
            path,w,h=math_asset(part[2:-2],size=size)
            result.append(f'<img src="{path}" width="{w:.3f}" height="{h:.3f}" valign="middle"/>')
        elif part.startswith("`"):
            result.append(runs(part[1:-1],mono=True))
        elif part.startswith("**"):
            result.append(runs(part[2:-2],bold=True))
        elif re.fullmatch(r"\[.*?\]\(.*?\)",part):
            match=re.match(r"\[(.*?)\]\((.*?)\)",part)
            target=match[2]
            if target.startswith("https://"):
                result.append(f'<link href="{html.escape(target,quote=True)}" color="#0072B2">{runs(match[1])}</link>')
            else: result.append(runs(match[1]))
        else: result.append(runs(part,bold=bold))
    return "".join(result)


BODY=ParagraphStyle("Body",fontName="BodyCJK",fontSize=10.2,leading=16.6,
                    wordWrap="CJK",spaceAfter=6,splitLongWords=True,allowWidows=0,allowOrphans=0)
TITLE=ParagraphStyle("Title",parent=BODY,fontSize=19,leading=29,spaceAfter=16)
H1=ParagraphStyle("H1",parent=BODY,fontSize=14,leading=21,spaceBefore=15,spaceAfter=9,keepWithNext=True)
H2=ParagraphStyle("H2",parent=BODY,fontSize=11.3,leading=18,spaceBefore=10,spaceAfter=6,keepWithNext=True)
CAPTION=ParagraphStyle("Caption",parent=BODY,fontSize=8.6,leading=13.4,spaceAfter=12)
CELL=ParagraphStyle("Cell",parent=BODY,fontSize=8.0,leading=12.4,spaceAfter=0)
CODE=ParagraphStyle("Code",parent=BODY,fontSize=8.1,leading=12.5,spaceAfter=0,leftIndent=8,rightIndent=8)
SMALL=ParagraphStyle("Small",parent=BODY,fontSize=8.3,leading=13.2,spaceAfter=6)


class Equation(Flowable):
    def __init__(self, latex):
        super().__init__()
        self.path,self.w,self.h=math_asset(latex,display=True)
        self.number=len(EQUATIONS)
        self.scale=min(1,(TEXT_W-42)/self.w)
        self.width=TEXT_W
        self.height=max(25,self.h*self.scale+17)

    def draw(self):
        w,h=self.w*self.scale,self.h*self.scale
        self.canv.drawImage(str(self.path),(TEXT_W-w)/2,(self.height-h)/2,width=w,height=h,mask="auto")
        self.canv.setFont("BodyLatin",9)
        self.canv.drawRightString(TEXT_W,self.height/2-3,f"({self.number})")


def footer(canvas,doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D3D7DB"));canvas.setLineWidth(.35)
    canvas.line(LEFT,PAGE_H-31,PAGE_W-RIGHT,PAGE_H-31)
    canvas.setFont("BodyCJK",7)
    canvas.drawString(LEFT,PAGE_H-23,"加速器技术文档的检索增强问答")
    canvas.setFont("BodyLatin",7.5)
    canvas.drawRightString(PAGE_W-RIGHT,25,str(doc.page))
    canvas.restoreState()


class Document(BaseDocTemplate):
    def afterFlowable(self,flowable):
        if isinstance(flowable,Paragraph) and flowable.style.name in {"H1","H2"}:
            text=flowable.getPlainText()
            level=0 if flowable.style.name=="H1" else 1
            anchor="sec-"+hashlib.sha256(text.encode()).hexdigest()[:12]
            self.canv.bookmarkPage(anchor)
            self.canv.addOutlineEntry(text,anchor,level=level,closed=False)
            if level == 0 and text != "目录":
                self.notify("TOCEntry",(level,inline(text,9.1),self.page,anchor))


def table(lines):
    rows=[[c.strip() for c in line.strip().strip("|").split("|")] for line in lines]
    rows=[r for r in rows if not all(re.fullmatch(r":?-+:?",c.replace(" ","")) for c in r)]
    n=len(rows[0]);header=rows[0]
    if n==6 and header[0]=="文档": widths=[.32,.24,.08,.10,.13,.13]
    elif n==6:widths=[.36,.12,.12,.12,.13,.15]
    elif n==5:widths=[.39,.12,.19,.12,.18]
    elif n==4:widths=[.15,.32,.28,.25]
    elif n==3 and header[0]=="编号":widths=[.08,.60,.32]
    elif n==3:widths=[.21,.38,.41]
    else:widths=[.23,.77]
    if len(widths)!=n:widths=[1/n]*n
    cells=[[Paragraph(inline(cell,8.0,bold=i==0),CELL) for cell in row] for i,row in enumerate(rows)]
    result=Table(cells,colWidths=[w*TEXT_W for w in widths],repeatRows=1,hAlign="LEFT")
    result.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                               ("LINEABOVE",(0,0),(-1,0),.7,colors.HexColor("#24292E")),
                               ("LINEBELOW",(0,0),(-1,0),.4,colors.HexColor("#8B9298")),
                               ("LINEBELOW",(0,-1),(-1,-1),.7,colors.HexColor("#24292E")),
                               ("BOTTOMPADDING",(0,0),(-1,-1),5),
                               ("TOPPADDING",(0,0),(-1,-1),5),
                               ("LEFTPADDING",(0,0),(-1,-1),5),
                               ("RIGHTPADDING",(0,0),(-1,-1),5)]))
    return result


def main():
    EQ.mkdir(parents=True,exist_ok=True);QA.mkdir(parents=True,exist_ok=True);PDF.parent.mkdir(parents=True,exist_ok=True)
    lines=(OUT/"rag-chapter.md").read_text().splitlines();story=[];i=0;title_used=False
    while i<len(lines):
        line=lines[i].strip()
        if not line: i+=1;continue
        if line.startswith("# "):
            story.append(Paragraph(inline(line[2:],19,bold=True),TITLE));title_used=True;i+=1;continue
        if line.startswith("## "):
            if line[3:]=="1 研究背景与问题定义":
                story.append(PageBreak())
                story.append(Paragraph(inline("目录",14,bold=True),H1))
                toc=TableOfContents()
                toc.levelStyles=[ParagraphStyle("T0",fontName="BodyLatin",fontSize=9.1,leading=16,leftIndent=0,spaceBefore=5),
                                 ParagraphStyle("T1",fontName="BodyLatin",fontSize=8.2,leading=14,leftIndent=15,spaceBefore=1)]
                story.append(toc);story.append(PageBreak())
            if line[3:].startswith("附录") or line[3:]=="参考文献":story.append(PageBreak())
            story.append(Paragraph(inline(line[3:],14,bold=True),H1));i+=1;continue
        if line.startswith("### "):
            story.append(Paragraph(inline(line[4:],11.3,bold=True),H2));i+=1;continue
        if line=="$$":
            latex=[];i+=1
            while i<len(lines) and lines[i].strip()!="$$":latex.append(lines[i]);i+=1
            story.append(Equation(" ".join(latex)));i+=1;continue
        if line.startswith("!["):
            m=re.match(r"!\[(.*)\]\((.*)\)",line);p=OUT/m[2]
            im=PILImage.open(p);w=TEXT_W;h=w*im.height/im.width
            img=Image(str(p),width=w,height=h)
            caption=Paragraph(inline(m[1],8.6),CAPTION)
            story.append(KeepTogether([Spacer(1,7),img,Spacer(1,6),caption]));i+=1;continue
        if line.startswith("|"):
            batch=[]
            while i<len(lines) and lines[i].strip().startswith("|"):batch.append(lines[i]);i+=1
            story.extend([table(batch),Spacer(1,10)]);continue
        if line.startswith("```"):
            code=[];i+=1
            while i<len(lines) and not lines[i].strip().startswith("```"):code.append(lines[i]);i+=1
            content="<br/>".join(runs(x,mono=True) for x in code)
            story.append(KeepTogether([Paragraph(content,CODE),Spacer(1,10)]));i+=1;continue
        para=[line];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].lstrip().startswith(("#","|","![","$$","```")):
            para.append(lines[i].strip());i+=1
        text=" ".join(para)
        style=SMALL if re.match(r"\[[1-9]\]",text) or text.startswith("注：") else BODY
        if re.match(r"表 [A-Z]?\d",text):
            st=ParagraphStyle("TableTitle",parent=CAPTION,keepWithNext=True,spaceBefore=8,spaceAfter=5)
            story.append(Paragraph(inline(text,8.6,bold=True),st))
        else:story.append(Paragraph(inline(text,style.fontSize),style))
    doc=Document(str(PDF),pagesize=A4,leftMargin=LEFT,rightMargin=RIGHT,topMargin=TOP,bottomMargin=BOTTOM,
                 title="面向加速器技术文档的可追溯检索增强问答系统",author="",subject="RAG thesis chapter; local evidence through 2026-10-27")
    frame=Frame(LEFT,BOTTOM,TEXT_W,PAGE_H-TOP-BOTTOM,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0,id="body")
    doc.addPageTemplates(PageTemplate(id="paper",frames=frame,onPage=footer))
    doc.multiBuild(story)
    if MISSING:raise ValueError(f"Missing font glyphs: {MISSING}")
    (EQ/"formula-manifest.json").write_text(json.dumps(EQUATIONS,ensure_ascii=False,indent=2)+"\n")
    # Convenience source for copying all display math into a thesis LaTeX project.
    (EQ/"all-formulas.latex").write_text("\n\n".join("% Equation "+str(e["number"])+"\n\\[\n"+e["latex"]+"\n\\]" for e in EQUATIONS)+"\n")
    print(f"PDF: {PDF}; pages: {doc.page}; equations: {len(EQUATIONS)}; missing glyphs: {len(MISSING)}")


if __name__=="__main__":
    main()
