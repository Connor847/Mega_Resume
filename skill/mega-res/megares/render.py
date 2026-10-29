"""Render resolved content to .docx, then .pdf via LibreOffice."""
import os, re, subprocess
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

class Renderer:
    def __init__(self, style):
        self.s = style
        self.text_w = 8.5 - 2 * style["margin_lr_in"]

    def _fmt(self, p, before=0, after=0):
        pf = p.paragraph_format
        pf.space_before, pf.space_after, pf.line_spacing = Pt(before), Pt(after), 1.0
        return p

    def _run(self, p, text, bold=False, italic=False, size=None):
        r = p.add_run(text)
        r.bold, r.italic = bold, italic
        r.font.size = Pt(size or self.s["body_size"]); r.font.name = self.s["font"]
        r._element.rPr.rFonts.set(qn("w:eastAsia"), self.s["font"])
        return r

    def _link(self, p, text, url):
        rid = p.part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
        h = OxmlElement("w:hyperlink"); h.set(qn("r:id"), rid)
        r = OxmlElement("w:r"); rpr = OxmlElement("w:rPr"); f = OxmlElement("w:rFonts")
        for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"): f.set(qn(a), self.s["font"])
        sz = OxmlElement("w:sz"); sz.set(qn("w:val"), str(int(self.s["body_size"] * 2)))
        rpr.append(f); rpr.append(sz); r.append(rpr)
        t = OxmlElement("w:t"); t.text = text; t.set(qn("xml:space"), "preserve"); r.append(t)
        h.append(r); p._p.append(h)

    def _two_col(self, doc, left, right, bold=False, before=0):
        p = self._fmt(doc.add_paragraph(), before=before)
        p.paragraph_format.tab_stops.add_tab_stop(Inches(self.text_w), WD_TAB_ALIGNMENT.RIGHT)
        self._run(p, left, bold=bold)
        if right: self._run(p, "\t" + right)
        p.paragraph_format.keep_with_next = True

    def _section(self, doc, title):
        p = self._fmt(doc.add_paragraph(), before=6, after=2)
        self._run(p, title.upper(), bold=True, size=self.s["section_size"])
        pPr = p._p.get_or_add_pPr(); b = OxmlElement("w:pBdr"); e = OxmlElement("w:bottom")
        for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "000000")): e.set(qn(k), v)
        b.append(e); pPr.append(b)
        p.paragraph_format.keep_with_next = True

    def _bullet(self, doc, text):
        ind = Inches(self.s["bullet_indent_in"])
        p = self._fmt(doc.add_paragraph())
        p.paragraph_format.left_indent, p.paragraph_format.first_line_indent = ind, -ind
        p.paragraph_format.tab_stops.add_tab_stop(ind)
        self._run(p, self.s["bullet_char"] + "\t" + text)

    def docx(self, master, content, path):
        s = self.s
        doc = Document(); sec = doc.sections[0]
        sec.page_width, sec.page_height = Inches(8.5), Inches(11)
        sec.left_margin = sec.right_margin = Inches(s["margin_lr_in"])
        sec.top_margin = sec.bottom_margin = Inches(s["margin_tb_in"])
        st = doc.styles["Normal"]; st.font.name = s["font"]; st.font.size = Pt(s["body_size"])
        st.element.rPr.rFonts.set(qn("w:eastAsia"), s["font"])

        h = master["header"]
        p = self._fmt(doc.add_paragraph()); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self._run(p, h["name"], bold=True, size=s["name_size"])
        p = self._fmt(doc.add_paragraph()); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for k, c in enumerate(h.get("contact", [])):
            if k: self._run(p, " | ")
            self._link(p, c["text"], c["url"]) if c.get("url") else self._run(p, c["text"])

        if content["education"]:
            self._section(doc, "Education")
            for n, (e, lines) in enumerate(content["education"]):
                self._two_col(doc, e["school"], e.get("dates", ""), bold=True, before=0 if n == 0 else 4)
                if e.get("degree"):
                    self._run(self._fmt(doc.add_paragraph()), e["degree"], italic=True)
                for l in lines:
                    self._run(self._fmt(doc.add_paragraph()), l["text"])
        for key, title in (("experience", "Work Experience"), ("projects", "Projects")):
            if not content[key]: continue
            self._section(doc, title)
            for n, (e, bl) in enumerate(content[key]):
                before = 0 if n == 0 else 5
                if key == "projects":
                    self._two_col(doc, e["name"], e.get("dates", ""), bold=True, before=before)
                else:
                    self._two_col(doc, e["org"], e.get("location", ""), bold=True, before=before)
                    self._two_col(doc, e["title"], e.get("dates", ""), bold=True)
                for b in bl: self._bullet(doc, b["text"])
        if content["skills"]:
            self._section(doc, "Technical Skills")
            self._run(self._fmt(doc.add_paragraph()), ", ".join(content["skills"]))
        doc.save(path)

def to_pdf(docx_path):
    outdir = os.path.dirname(os.path.abspath(docx_path))
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", outdir, docx_path],
                   check=True, capture_output=True)
    return os.path.splitext(docx_path)[0] + ".pdf"

def fit(pdf, style):
    info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True, check=True).stdout
    pages = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    bbox = subprocess.run(["pdftotext", "-bbox", "-f", str(pages), "-l", str(pages), pdf, "-"],
                          capture_output=True, text=True, check=True).stdout
    ymax = max(float(v) for v in re.findall(r'yMax="([\d.]+)"', bbox))
    free_in = (792 - style["margin_tb_in"] * 72 - ymax) / 72
    return pages, free_in
