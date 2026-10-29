"""mega-res command line. Run from anywhere with the skill folder on PYTHONPATH:

  PYTHONPATH=<skill dir> python -m megares init   MAIN_FOLDER
  PYTHONPATH=<skill dir> python -m megares import RESUME.pdf MAIN_FOLDER
  PYTHONPATH=<skill dir> python -m megares check  MASTER
  PYTHONPATH=<skill dir> python -m megares build  MASTER SELECTION --outdir DIR
                                                  [--company C] [--role R] [--require-read-only]

`build` writes exactly one file to --outdir: "<Person Name>_<Company>_<Role>.pdf".
Intermediate files (.docx) go to a temporary folder unless --keep-docx is given.
"""
import argparse, datetime, os, re, shutil, sys, tempfile, yaml
from . import master as M
from .render import Renderer, to_pdf, fit
from .verify import check_docx, check_pdf

MASTER_NAME = "mega_resume.yaml"
OUTPUTS_NAME = "Resume Outputs"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def clean(part):
    part = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", str(part))
    return re.sub(r"\s+", " ", part).strip().strip(".")

def output_name(person, company=None, role=None):
    parts = [clean(person)] + [clean(p) for p in (company, role) if p and clean(p)]
    if len(parts) == 1:
        parts.append("Resume " + datetime.date.today().isoformat())
    return "_".join(parts)

def unique_path(path):
    base, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(path):
        path = f"{base} ({n}){ext}"; n += 1
    return path

def cmd_init(a):
    os.makedirs(a.folder, exist_ok=True)
    master = os.path.join(a.folder, MASTER_NAME)
    outputs = os.path.join(a.folder, OUTPUTS_NAME)
    os.makedirs(outputs, exist_ok=True)
    if os.path.exists(master):
        print(f"EXISTS: {master} (left untouched)")
    else:
        shutil.copy(os.path.join(HERE, "templates", "mega_resume.example.yaml"), master)
        print(f"CREATED: {master} (example content - replace with yours)")
    print(f"READY: {outputs}")

ORDER = {"education": ["id", "school", "dates", "degree", "lines"],
         "experience": ["id", "org", "location", "title", "dates", "bullets"],
         "projects": ["id", "name", "dates", "bullets"]}

def _ordered(data):
    out = {"style": data["style"], "header": data["header"]}
    for k, keys in ORDER.items():
        out[k] = [{f: e[f] for f in keys if f in e} for e in data[k]]
    out["skills"] = data["skills"]
    return out

IMPORT_NOTE = """# Imported from {src} by `megares import` (rule-based, no AI).
# Every bullet, line and skill below was checked to appear word for word in that PDF.
# Before relying on it, skim the structure: job titles vs. organizations, dates vs.
# locations, and which section each item landed in. Then add tags, priority: must,
# and any experience that wasn't on the PDF. Ids can be renamed as long as they stay unique.

"""

def cmd_import(a):
    from . import importer as I
    target = a.out if a.out else os.path.join(a.folder, MASTER_NAME)
    if os.path.exists(target) and not a.force:
        sys.exit(f"REFUSED: {target} already exists. Choose another --out, or pass --force to replace it.")
    try:
        data, lines, missed, warnings = I.parse(a.pdf)
    except I.ImportError_ as e:
        sys.exit(f"IMPORT FAILED: {e}")
    errors = I.verify(a.pdf, data)
    try:
        M.validate(data)
    except M.MasterError as e:
        errors.append(str(e))
    n_b = sum(len(e["bullets"]) for k in ("experience", "projects") for e in data[k])
    print(f"NAME: {data['header']['name']}")
    print(f"FOUND: {len(data['education'])} education, {len(data['experience'])} experience, "
          f"{len(data['projects'])} projects, {n_b} bullets, {len(data['skills'])} skills")
    for e in data["experience"]:
        print(f"  - {e['org']} | {e.get('title', '')} | {e.get('dates', '')} | {len(e['bullets'])} bullets")
    for w in warnings: print("WARNING: " + w)
    for m in missed: print("UNUSED PDF LINE: " + m)
    for e in errors: print("ERROR: " + e)
    if errors or (missed and not a.allow_unused):
        sys.exit("NOT WRITTEN: fix the problems above (see README: 'Importing a PDF - where it fails')")
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(IMPORT_NOTE.format(src=os.path.basename(a.pdf)))
        yaml.safe_dump(_ordered(data), f, sort_keys=False, allow_unicode=True, width=10000)
    M.load(target)
    if a.folder:
        os.makedirs(os.path.join(a.folder, OUTPUTS_NAME), exist_ok=True)
    print(f"WROTE: {target}")

def cmd_check(a):
    m = M.load(a.master)
    n = sum(len(e["bullets"]) for k in ("experience", "projects") for e in m.get(k, []))
    print(f"OK: {a.master}\nNAME: {m['header']['name']}\nSHA256: {M.sha256(a.master)}\nBULLETS: {n}")
    print("READ-ONLY: " + ("yes" if M.is_read_only(a.master) else "no"))

def cmd_build(a):
    if a.require_read_only and not M.is_read_only(a.master):
        sys.exit(f"REFUSED: {a.master} is writable. Lock it with: chmod a-w \"{a.master}\"")
    digest_before = M.sha256(a.master)
    m = M.load(a.master)
    with open(a.selection, encoding="utf-8") as f:
        sel = yaml.safe_load(f)
    content = M.resolve(m, sel)

    work = tempfile.mkdtemp(prefix="megares-")
    name = output_name(m["header"]["name"], a.company, a.role)
    docx = os.path.join(work, name + ".docx")
    Renderer(m["style"]).docx(m, content, docx)
    pdf = to_pdf(docx)

    if M.sha256(a.master) != digest_before:
        sys.exit("FAILED: master changed during the build")
    bc = m["style"]["bullet_char"]
    errors = check_docx(docx, m, content, bc) + check_pdf(pdf, m, content, bc)
    pages, free = fit(pdf, m["style"])
    limit = m["style"]["page_limit"]
    ok = not errors and pages <= limit

    print(f"MASTER SHA256: {digest_before}")
    print("VERBATIM CHECK: " + ("PASS" if not errors else "FAIL"))
    for e in errors: print("  - " + e)
    print(f"PAGES: {pages} (limit {limit})")
    if pages > limit:
        print("STATUS: OVERFLOW - remove the lowest-ranked bullet and rebuild")
    elif free > 0.4:
        print(f"STATUS: ROOM - {free:.2f} in free; consider adding the next-best bullet")
    else:
        print(f"STATUS: GOOD FIT ({free:.2f} in free)")

    if a.preview:
        shutil.copy(pdf, a.preview); print(f"PREVIEW: {a.preview}")
    if ok and a.outdir:
        os.makedirs(a.outdir, exist_ok=True)
        dest = os.path.join(a.outdir, name + ".pdf")
        dest = dest if a.overwrite else unique_path(dest)
        shutil.copy(pdf, dest); print(f"WROTE: {dest}")
        if a.keep_docx:
            d = os.path.splitext(dest)[0] + ".docx"; shutil.copy(docx, d); print(f"WROTE: {d}")
    elif not ok:
        print("NOT SAVED: fix the problems above and rebuild")
    shutil.rmtree(work, ignore_errors=True)
    sys.exit(0 if ok else 1)

def main():
    p = argparse.ArgumentParser(prog="megares")
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init"); i.add_argument("folder"); i.set_defaults(fn=cmd_init)
    im = sub.add_parser("import", help="convert a resume PDF into mega_resume.yaml")
    im.add_argument("pdf"); im.add_argument("folder", nargs="?", default="",
                                             help="main folder; writes <folder>/mega_resume.yaml")
    im.add_argument("--out", help="write to this path instead")
    im.add_argument("--force", action="store_true", help="replace an existing file")
    im.add_argument("--allow-unused", action="store_true", help="write even if some PDF lines were not used")
    im.set_defaults(fn=cmd_import)
    c = sub.add_parser("check"); c.add_argument("master"); c.set_defaults(fn=cmd_check)
    b = sub.add_parser("build")
    b.add_argument("master"); b.add_argument("selection")
    b.add_argument("--outdir", help=f"where the final PDF goes (normally '<main folder>/{OUTPUTS_NAME}')")
    b.add_argument("--company"); b.add_argument("--role")
    b.add_argument("--preview", help="also copy the PDF here (for checking a draft without saving it)")
    b.add_argument("--overwrite", action="store_true", help="replace an existing file instead of adding ' (2)'")
    b.add_argument("--keep-docx", action="store_true")
    b.add_argument("--require-read-only", action="store_true")
    b.set_defaults(fn=cmd_build)
    a = p.parse_args()
    try:
        a.fn(a)
    except M.MasterError as e:
        sys.exit(f"ERROR: {e}")

if __name__ == "__main__":
    main()
