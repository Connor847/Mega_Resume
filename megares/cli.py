"""mega-res command line.

  python -m megares check  MASTER
  python -m megares build  MASTER SELECTION OUT_BASENAME [--require-read-only]
"""
import argparse, os, sys, yaml
from . import master as M
from .render import Renderer, to_pdf, fit
from .verify import check_docx, check_pdf

def cmd_check(a):
    m = M.load(a.master)
    n = sum(len(e["bullets"]) for k in ("experience", "projects") for e in m.get(k, []))
    print(f"OK: {a.master}\nSHA256: {M.sha256(a.master)}\nBULLETS: {n}")
    print("READ-ONLY: " + ("yes" if M.is_read_only(a.master) else "no"))

def cmd_build(a):
    if a.require_read_only and not M.is_read_only(a.master):
        sys.exit(f"REFUSED: {a.master} is writable. Run: chmod a-w {a.master}")
    digest_before = M.sha256(a.master)
    m = M.load(a.master)
    with open(a.selection, encoding="utf-8") as f:
        sel = yaml.safe_load(f)
    content = M.resolve(m, sel)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    docx = a.out + ".docx"
    Renderer(m["style"]).docx(m, content, docx)
    pdf = to_pdf(docx)
    if M.sha256(a.master) != digest_before:
        sys.exit("FAILED: master changed during the build")
    bc = m["style"]["bullet_char"]
    errors = check_docx(docx, m, content, bc) + check_pdf(pdf, m, content, bc)
    pages, free = fit(pdf, m["style"])
    print(f"WROTE: {docx}\nWROTE: {pdf}\nMASTER SHA256: {digest_before}")
    print("VERBATIM CHECK: " + ("PASS" if not errors else "FAIL"))
    for e in errors: print("  - " + e)
    print(f"PAGES: {pages} (limit {m['style']['page_limit']})")
    if pages > m["style"]["page_limit"]:
        print("STATUS: OVERFLOW - remove the lowest-ranked bullet and rebuild")
    elif free > 0.4:
        print(f"STATUS: ROOM - {free:.2f} in free; consider adding the next-best bullet")
    else:
        print(f"STATUS: GOOD FIT ({free:.2f} in free)")
    if errors or pages > m["style"]["page_limit"]:
        sys.exit(1)

def main():
    p = argparse.ArgumentParser(prog="megares")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("master"); c.set_defaults(fn=cmd_check)
    b = sub.add_parser("build"); b.add_argument("master"); b.add_argument("selection"); b.add_argument("out")
    b.add_argument("--require-read-only", action="store_true"); b.set_defaults(fn=cmd_build)
    a = p.parse_args()
    try:
        a.fn(a)
    except M.MasterError as e:
        sys.exit(f"ERROR: {e}")

if __name__ == "__main__":
    main()
