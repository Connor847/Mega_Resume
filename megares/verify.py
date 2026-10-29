"""Verify a rendered resume contains only verbatim master text.

Two independent checks:
  1. DOCX: every bullet paragraph equals a master bullet exactly, and nothing else is a bullet.
  2. PDF:  every selected bullet/line/skill appears in the final PDF text (whitespace-insensitive,
           to tolerate line wrapping), and the PDF contains no bullet text absent from the master.
"""
import re, subprocess
from docx import Document

def _squash(s):
    return re.sub(r"\s+", "", s)

def check_docx(docx_path, master, content, bullet_char):
    errors = []
    master_bullets = {b["text"] for k in ("experience", "projects") for e in master.get(k, []) for b in e["bullets"]}
    expected = [b["text"] for k in ("experience", "projects") for _, bl in content[k] for b in bl]
    found = []
    for p in Document(docx_path).paragraphs:
        if p.text.startswith(bullet_char + "\t"):
            t = p.text[len(bullet_char) + 1:]
            found.append(t)
            if t not in master_bullets:
                errors.append(f"DOCX bullet not in master: {t[:80]}...")
    if found != expected:
        errors.append(f"DOCX bullets differ from selection ({len(found)} found, {len(expected)} expected)")
    return errors

def check_pdf(pdf_path, master, content, bullet_char):
    errors = []
    raw = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True, check=True).stdout
    flat = _squash(raw)
    items = [b["text"] for k in ("experience", "projects") for _, bl in content[k] for b in bl]
    items += [l["text"] for _, lines in content["education"] for l in lines]
    items += content["skills"]
    for t in items:
        if _squash(t) not in flat:
            errors.append(f"PDF missing verbatim text: {t[:80]}...")
    # every bullet chunk in the PDF must match some master bullet
    master_sq = [_squash(b["text"]) for k in ("experience", "projects") for e in master.get(k, []) for b in e["bullets"]]
    for chunk in raw.split(bullet_char)[1:]:
        c = _squash(chunk)
        if not any(c.startswith(m) for m in master_sq):
            errors.append(f"PDF bullet does not start with any master bullet: {chunk.strip()[:80]}...")
    return errors
