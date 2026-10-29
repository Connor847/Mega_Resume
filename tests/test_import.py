import os, shutil, subprocess, sys, pytest, yaml

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..", "skill", "mega-res")
sys.path.insert(0, SKILL)
from megares import importer as I

TEMPLATE = os.path.join(SKILL, "templates", "mega_resume.example.yaml")
ENV = {**os.environ, "PYTHONPATH": SKILL}
pytestmark = pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice not installed")

def run(*args):
    return subprocess.run([sys.executable, "-m", "megares", *args], capture_output=True, text=True, env=ENV)

def full_selection(m):
    return {"education": [{"id": e["id"], "lines": [l["id"] for l in e.get("lines", [])]} for e in m["education"]],
            "experience": [{"id": e["id"], "bullets": [b["id"] for b in e["bullets"]]} for e in m["experience"]],
            "projects": [{"id": e["id"], "bullets": [b["id"] for b in e["bullets"]]} for e in m["projects"]],
            "skills": "all"}

def render_all(master_path, tmp_path):
    m = yaml.safe_load(open(master_path))
    sel = tmp_path / "sel.yaml"; sel.write_text(yaml.safe_dump(full_selection(m)))
    pdf = tmp_path / "full.pdf"
    r = run("build", master_path, str(sel), "--preview", str(pdf))
    assert pdf.exists(), r.stdout + r.stderr
    return m, str(pdf)

def test_round_trip_matches_template(tmp_path):
    m, pdf = render_all(TEMPLATE, tmp_path)
    r = run("import", pdf, str(tmp_path / "main"))
    assert r.returncode == 0, r.stdout + r.stderr
    got = yaml.safe_load(open(tmp_path / "main" / "mega_resume.yaml"))
    assert (tmp_path / "main" / "Resume Outputs").is_dir()
    texts = lambda x: [b["text"] for k in ("experience", "projects") for e in x[k] for b in e["bullets"]]
    assert texts(got) == texts(m)
    assert [(e["org"], e["title"], e["location"], e["dates"]) for e in got["experience"]] == \
           [(e["org"], e["title"], e["location"], e["dates"]) for e in m["experience"]]
    assert got["skills"] == m["skills"]
    assert got["header"]["name"] == m["header"]["name"]

def test_import_refuses_to_overwrite(tmp_path):
    _, pdf = render_all(TEMPLATE, tmp_path)
    assert run("import", pdf, str(tmp_path / "main")).returncode == 0
    r = run("import", pdf, str(tmp_path / "main"))
    assert r.returncode != 0 and "already exists" in r.stderr

def _docx_resume(path, title_first, skills_lines, bullet="•"):
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_TAB_ALIGNMENT, WD_ALIGN_PARAGRAPH
    d = Document(); s = d.sections[0]; s.left_margin = s.right_margin = Inches(0.7)
    def para(t, bold=False, italic=False, size=None, right=None, center=False, indent=False):
        p = d.add_paragraph(); p.paragraph_format.space_after = Pt(0)
        if center: p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if right: p.paragraph_format.tab_stops.add_tab_stop(Inches(7.1), WD_TAB_ALIGNMENT.RIGHT)
        if indent: p.paragraph_format.left_indent = Inches(0.3); p.paragraph_format.first_line_indent = Inches(-0.2)
        r = p.add_run(t); r.bold, r.italic = bold, italic
        if size: r.font.size = Pt(size)
        if right: p.add_run("\t" + right)
    para("Priya Natarajan", bold=True, size=20, center=True)
    para("priya.n@example.com | linkedin.com/in/priya-example", center=True)
    para("EDUCATION", bold=True, size=12)
    para("University of Texas at Austin", bold=True, right="May 2021")
    para("B.S. in Mechanical Engineering", italic=True)
    para("PROFESSIONAL EXPERIENCE", bold=True, size=12)
    if title_first:
        para("Battery Test Engineer", bold=True, right="Jun 2023 – Present"); para("Tesla", italic=True, right="Austin, TX")
    else:
        para("Tesla", bold=True, right="Austin, TX"); para("Battery Test Engineer", italic=True, right="Jun 2023 – Present")
    para(bullet + " Automated cell cycling analysis in Python, cutting weekly reporting time from 10 hours to 1 hour across three test labs", indent=True)
    para("SKILLS", bold=True, size=12)
    for l in skills_lines: para(l)
    d.save(path)
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", os.path.dirname(path), path],
                   check=True, capture_output=True)
    return path[:-5] + ".pdf"

@pytest.mark.parametrize("title_first", [False, True])
def test_org_and_title_detected_either_order(tmp_path, title_first):
    pdf = _docx_resume(str(tmp_path / "r.docx"), title_first, ["Python, MATLAB, SQL"])
    data, _, missed, _ = I.parse(pdf)
    assert not missed and not I.verify(pdf, data)
    e = data["experience"][0]
    assert (e["org"], e["title"], e["location"], e["dates"]) == ("Tesla", "Battery Test Engineer", "Austin, TX", "Jun 2023 – Present")
    assert data["skills"] == ["Python", "MATLAB", "SQL"]

def test_categorized_skills_kept_as_lines(tmp_path):
    pdf = _docx_resume(str(tmp_path / "r.docx"), False, ["Languages: Python, C++", "Tools: ANSYS (Fluent, Mechanical), Git"])
    data, _, _, _ = I.parse(pdf)
    assert data["skills"] == ["Languages: Python, C++", "Tools: ANSYS (Fluent, Mechanical), Git"]
    assert data["style"]["skills_layout"] == "lines"

def test_scanned_pdf_fails_clearly(tmp_path):
    PIL = pytest.importorskip("PIL.Image")
    _, pdf = render_all(TEMPLATE, tmp_path)
    subprocess.run(["pdftoppm", "-r", "60", "-png", "-f", "1", "-l", "1", pdf, str(tmp_path / "s")], check=True)
    png = next(p for p in os.listdir(tmp_path) if p.startswith("s") and p.endswith(".png"))
    PIL.open(tmp_path / png).convert("RGB").save(tmp_path / "scan.pdf")
    r = run("import", str(tmp_path / "scan.pdf"), str(tmp_path / "x"))
    assert r.returncode != 0 and "scanned" in r.stderr
    assert not (tmp_path / "x" / "mega_resume.yaml").exists()
