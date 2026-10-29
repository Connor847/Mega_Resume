"""Convert a standard resume PDF into a mega_resume.yaml - deterministically, with no AI.

The parser reads each word's font, size and position and applies fixed rules:
  - the largest text before the first section heading is the name; the lines under it are
    contact details, split on "|", "•" or "·"
  - a section heading is a short line in ALL CAPS (bold or larger than body text)
  - a bullet starts with a bullet character; indented lines under it continue the bullet
  - in Experience/Projects, non-bullet lines open an entry: the first is the organization
    (or project name), the second is the job title; text pushed to the right margin is the
    location or the dates (anything that looks like a date range goes to `dates`)
  - in Education, the first line is the school, an italic or second line is the degree, and
    other lines (including bullets) become selectable education lines
  - Skills are split on commas that are not inside parentheses

Every text field is then checked against the PDF's own text: the import fails if any
bullet, line or skill is not found there verbatim, or if any PDF line was not used.
"""
import re, subprocess
from collections import Counter
import pdfplumber

BULLETS = "●•▪◦‣∙·○■□➢➤►▶-–—*"
DATE_RE = re.compile(
    r"\b((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s*'?\d{2,4}|"
    r"(19|20)\d{2}|Present|Current|Now|Expected)\b", re.I)
SECTION_MAP = [
    ("education", ("EDUCATION", "ACADEMIC")),
    ("skills", ("SKILL", "TECHNOLOG", "TOOLS", "COMPETENC")),
    ("projects", ("PROJECT",)),
    ("experience", ("EXPERIENCE", "EMPLOYMENT", "WORK", "RESEARCH", "POSITIONS", "LEADERSHIP")),
]
INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
FONT_NAMES = {"timesnewroman": "Times New Roman", "times": "Times New Roman", "arial": "Arial",
              "helvetica": "Helvetica", "calibri": "Calibri", "garamond": "Garamond",
              "georgia": "Georgia", "cambria": "Cambria", "lmroman": "Latin Modern Roman",
              "cmr": "Latin Modern Roman", "liberationserif": "Times New Roman",
              "liberationsans": "Arial", "roboto": "Roboto", "lato": "Lato",
              "opensans": "Open Sans", "sourcesanspro": "Source Sans Pro",
              "carlito": "Calibri", "caladea": "Cambria"}


TITLE_WORDS = re.compile(
    r"\b(engineer|intern|analyst|scientist|manager|developer|researcher|assistant|associate|"
    r"director|consultant|lead|specialist|fellow|officer|coordinator|designer|architect|"
    r"technician|president|founder|co-founder|head|vp|ceo|cto|cfo|programmer|administrator|"
    r"instructor|teacher|tutor|professor|lecturer|postdoc|student|volunteer|member|chair|"
    r"captain|representative|advisor|strategist|editor|writer|apprentice|trainee)s?\b", re.I)


class ImportError_(Exception):
    pass


def clean(s):
    s = s.translate(INVISIBLE).replace(" ", " ").replace("\t", " ")
    return re.sub(r"\s+", " ", s).strip()


def squash(s):
    return re.sub(r"\s+", "", clean(s))


def is_bold(f):
    return bool(re.search(r"bold|black|heavy|semibold|demi", f, re.I))


def is_italic(f):
    return bool(re.search(r"italic|oblique", f, re.I))


def base_font(f):
    f = f.split("+", 1)[-1]
    key = re.sub(r"(PS)?[-,]?(Bold|Italic|Oblique|Regular|MT|Roman|Book|Semibold|Medium)+.*$", "", f)
    key = re.sub(r"[^a-z]", "", key.lower())
    for k, v in FONT_NAMES.items():
        if key.startswith(k):
            return v
    return None


# ----------------------------------------------------------------------------- lines
class Line:
    def __init__(self, words, page_w):
        words.sort(key=lambda w: w["x0"])
        self.words = words
        self.x0 = words[0]["x0"]
        self.size = Counter(round(w["size"] * 2) / 2 for w in words).most_common(1)[0][0]
        self.top = min(w["top"] for w in words)
        letters = [w for w in words if re.search(r"[A-Za-z]", w["text"])] or words
        self.bold = sum(is_bold(w["fontname"]) for w in letters) > len(letters) / 2
        self.italic = sum(is_italic(w["fontname"]) for w in letters) > len(letters) / 2
        # split into left / right segments at the widest gap, if it is large
        self.left, self.right = words, []
        gaps = [(words[i + 1]["x0"] - words[i]["x1"], i) for i in range(len(words) - 1)]
        if gaps:
            g, i = max(gaps)
            if g > 40 and words[-1]["x1"] > page_w * 0.75:
                self.left, self.right = words[: i + 1], words[i + 1:]
        self.left_text = clean(" ".join(w["text"] for w in self.left))
        self.right_text = clean(" ".join(w["text"] for w in self.right))
        self.text = clean(" ".join(w["text"] for w in words))
        first = self.text[:1]
        self.bullet = bool(first) and first in BULLETS and (len(self.text) == 1 or self.text[1] == " "
                                                            or words[0]["text"] == first)
        self.body = clean(self.text[1:]) if self.bullet else self.text
        self.used = False


def read_lines(path):
    lines = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(extra_attrs=["fontname", "size"], use_text_flow=False,
                                       keep_blank_chars=False)
            words = [w for w in words if clean(w["text"])]
            for w in words:
                w["text"] = clean(w["text"])
            words.sort(key=lambda w: (round(w["top"]), w["x0"]))
            rows = []
            for w in words:
                if rows and abs(w["top"] - rows[-1][0]["top"]) <= 3:
                    rows[-1].append(w)
                else:
                    rows.append([w])
            lines += [Line(r, page.width) for r in rows]
    if not lines:
        raise ImportError_("no text found - the PDF may be a scanned image (needs OCR first)")
    return lines


def section_of(line, body_size):
    t = line.text.strip(":")
    letters = re.sub(r"[^A-Za-z]", "", t)
    if not letters or len(t) > 40 or line.bullet:
        return None
    if not (t.upper() == t and (line.bold or line.size > body_size)):
        return None
    up = t.upper()
    for key, words in SECTION_MAP:
        if any(w in up for w in words):
            return key
    return "unknown:" + t


def slug(s, n=2):
    words = re.findall(r"[a-z0-9]+", s.lower())
    stop = {"the", "of", "and", "a", "an", "at", "for", "in", "university", "college", "inc", "llc"}
    keep = [w for w in words if w not in stop][:n] or words[:n] or ["item"]
    return "-".join(keep)


def unique(base, used):
    i, cand = 2, base
    while cand in used:
        cand = f"{base}-{i}"; i += 1
    used.add(cand)
    return cand


def is_date(s):
    return bool(s) and bool(DATE_RE.search(s))


# ----------------------------------------------------------------------------- parse
def parse(path):
    lines = read_lines(path)
    body_size = Counter(l.size for l in lines for _ in l.words).most_common(1)[0][0]
    fonts = Counter(base_font(w["fontname"]) for l in lines for w in l.words if not l.bullet or w is not l.words[0])
    font = next((f for f, _ in fonts.most_common() if f), None)

    # header
    first_sec = next((i for i, l in enumerate(lines) if section_of(l, body_size)), None)
    if first_sec is None:
        raise ImportError_("no section headings found (expected ALL-CAPS headings like EXPERIENCE)")
    head = lines[:first_sec]
    if not head:
        raise ImportError_("no name found above the first section heading")
    name_line = max(head, key=lambda l: l.size)
    name_line.used = True
    contact = []
    for l in head:
        if l is name_line:
            continue
        l.used = True
        for part in re.split(r"\s*[|•·]\s*", l.text):
            part = clean(part)
            if not part:
                continue
            item = {"text": part}
            if re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", part):
                item["url"] = "mailto:" + part
            elif re.fullmatch(r"(https?://)?[\w.-]+\.[A-Za-z]{2,}(/\S*)?", part):
                item["url"] = part if part.startswith("http") else "https://" + part
            contact.append(item)

    out = {"header": {"name": name_line.text, "contact": contact},
           "education": [], "experience": [], "projects": [], "skills": []}
    ids, warnings, unknown = set(), [], []

    # split into sections
    sections, cur = [], None
    for l in lines[first_sec:]:
        s = section_of(l, body_size)
        if s:
            l.used = True
            cur = [s, []]; sections.append(cur)
        else:
            cur[1].append(l)

    for key, sl in sections:
        if key.startswith("unknown:"):
            unknown.append(key.split(":", 1)[1])
            continue
        if key == "skills":
            parse_skills(sl, out)
        elif key == "education":
            parse_education(sl, out, ids, body_size)
        else:
            parse_entries(sl, out[key], ids, key == "projects", warnings)
    if unknown:
        warnings.append("sections not imported (unsupported heading): " + ", ".join(unknown))

    style = {"body_size": body_size, "name_size": name_line.size, **out.pop("_style", {})}
    if font:
        style = {"font": font, **style}
    out = {"style": style, **out}
    missed = [l.text for l in lines if not l.used and l.text not in [s for s in unknown]]
    return out, lines, missed, warnings


def join_continuation(prev, nxt):
    if prev.endswith("-") and not prev.endswith(" -"):
        return prev + nxt
    return prev + " " + nxt


def gather_bullets(lines, i):
    """Starting at a bullet line, absorb its continuation lines (indented past the bullet
    character, not bold, nothing at the right margin). Returns (text, next_i)."""
    l = lines[i]; l.used = True
    x_min = l.x0 + 3
    text = l.body
    i += 1
    while i < len(lines):
        n = lines[i]
        if n.bullet or n.bold or n.right_text or n.x0 < x_min:
            break
        n.used = True
        text = join_continuation(text, n.text)
        i += 1
    return text, i


def parse_entries(sl, target, ids, is_project, warnings):
    i, entry = 0, None
    while i < len(sl):
        l = sl[i]
        if l.bullet:
            if entry is None:
                entry = new_entry(target, ids, is_project, "Untitled")
                warnings.append(f"bullet with no heading above it: '{l.body[:50]}...' (put under 'Untitled')")
            text, i = gather_bullets(sl, i)
            entry["bullets"].append({"id": unique(entry["id"] + "-" + slug(text, 2), ids), "text": text})
            continue
        # non-bullet line: start a new entry, or add the title line to the current one
        l.used = True
        left, right = l.left_text, l.right_text
        if entry is not None and not entry["bullets"] and not is_project and "title" not in entry:
            entry["title"] = left
            if right:
                place(entry, right)
        elif entry is not None and not entry["bullets"] and is_project:
            entry["name"] = entry["name"] + " " + left
            if right:
                place(entry, right)
        else:
            entry = new_entry(target, ids, is_project, left)
            if right:
                place(entry, right)
        i += 1
    for e in target:
        if not is_project and e.get("title") and \
                TITLE_WORDS.search(e["org"]) and not TITLE_WORDS.search(e["title"]):
            e["org"], e["title"] = e["title"], e["org"]
        if not e["bullets"]:
            warnings.append(f"entry '{e.get('org') or e.get('name')}' has no bullets")
        if not is_project:
            e.setdefault("title", "")


def new_entry(target, ids, is_project, heading):
    e = {"id": unique(slug(heading), ids)}
    e["name" if is_project else "org"] = heading
    e["bullets"] = []
    target.append(e)
    return e


def place(entry, right):
    if is_date(right) and "dates" not in entry:
        entry["dates"] = right
    elif "location" not in entry and "org" in entry:
        entry["location"] = right
    elif "dates" not in entry:
        entry["dates"] = right


def parse_education(sl, out, ids, body_size):
    i, e = 0, None
    while i < len(sl):
        l = sl[i]
        if l.bullet:
            if e is None:
                e = {"id": unique("education", ids), "school": "", "lines": []}
                out["education"].append(e)
            text, i = gather_bullets(sl, i)
            e["lines"].append({"id": unique(e["id"] + "-" + slug(text, 2), ids), "text": text})
            continue
        l.used = True
        if l.bold or e is None:
            e = {"id": unique(slug(l.left_text, 1), ids), "school": l.left_text, "lines": []}
            if l.right_text:
                e["dates"] = l.right_text
            out["education"].append(e)
        elif "degree" not in e and (l.italic or not e["lines"]):
            e["degree"] = l.left_text
            if l.right_text and "dates" not in e:
                e["dates"] = l.right_text
            elif l.right_text:
                e["lines"].append({"id": unique(e["id"] + "-" + slug(l.right_text, 2), ids), "text": l.right_text})
        else:
            # continuation of the previous line if indented past the margin and it doesn't look new
            e["lines"].append({"id": unique(e["id"] + "-" + slug(l.text, 2), ids), "text": l.text})
        i += 1


def split_top_level(s):
    out, depth, buf = [], 0, ""
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if ch in ",;" and depth == 0:
            out.append(buf); buf = ""
        else:
            buf += ch
    out.append(buf)
    return [clean(x) for x in out if clean(x)]


LABEL_RE = re.compile(r"^[A-Z][\w &/+.-]{0,30}:\s")


def parse_skills(sl, out):
    rows = []
    for l in sl:
        l.used = True
        t = l.body if l.bullet else l.text
        if LABEL_RE.match(t) or not rows:
            rows.append(t)
        else:
            rows[-1] = join_continuation(rows[-1], t)
    if len(rows) > 1 or (rows and LABEL_RE.match(rows[0])):
        if all(LABEL_RE.match(r) for r in rows):
            out["skills"] = rows
            out.setdefault("_style", {})["skills_layout"] = "lines"
            return
    text = ""
    for l in sl:
        l.used = True
        t = l.body if l.bullet else l.text
        text = t if not text else (join_continuation(text, t) if not text.rstrip().endswith((",", ";")) else text + " " + t)
    seen = set()
    for item in split_top_level(text):
        if item not in seen:
            seen.add(item); out["skills"].append(item)


# ----------------------------------------------------------------------------- verify
def verify(path, data):
    raw = subprocess.run(["pdftotext", "-raw", path, "-"], capture_output=True, text=True, check=True).stdout
    flat = squash(raw)
    errors = []
    items = [("bullet", b["text"]) for k in ("experience", "projects") for e in data[k] for b in e["bullets"]]
    items += [("education line", l["text"]) for e in data["education"] for l in e["lines"]]
    items += [("skill", s) for s in data["skills"]]
    for kind, t in items:
        if squash(t) not in flat:
            errors.append(f"{kind} not found verbatim in the PDF: {t[:70]}")
    return errors
