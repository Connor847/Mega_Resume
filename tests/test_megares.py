import os, shutil, subprocess, sys, pytest, yaml

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..", "skill", "mega-res")
sys.path.insert(0, SKILL)
from megares import master as M
from megares.cli import output_name

EX = os.path.join(SKILL, "templates")
MASTER = os.path.join(EX, "mega_resume.example.yaml")
ENV = {**os.environ, "PYTHONPATH": SKILL}

def run(*args, cwd=None):
    return subprocess.run([sys.executable, "-m", "megares", *args], capture_output=True, text=True, env=ENV, cwd=cwd)

def test_example_master_valid():
    M.load(MASTER)

def test_unknown_id_rejected():
    m = M.load(MASTER)
    with pytest.raises(M.MasterError):
        M.resolve(m, {"experience": [{"id": "acme", "bullets": ["made-up"]}]})

def test_must_entry_enforced():
    m = M.load(MASTER)
    with pytest.raises(M.MasterError):
        M.resolve(m, {"experience": [{"id": "lab", "bullets": ["lab-cv"]}]})

def test_skill_must_match_exactly():
    m = M.load(MASTER)
    with pytest.raises(M.MasterError):
        M.resolve(m, {"experience": [{"id": "acme", "bullets": ["acme-ab"]}], "skills": ["python"]})

def test_duplicate_ids_rejected(tmp_path):
    m = yaml.safe_load(open(MASTER))
    m["experience"][1]["bullets"][0]["id"] = "acme-forecast"
    p = tmp_path / "m.yaml"; p.write_text(yaml.safe_dump(m))
    with pytest.raises(M.MasterError):
        M.load(str(p))

@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice not installed")
def test_build_passes_verbatim_check(tmp_path):
    out = tmp_path / "Resume Outputs"
    sel = os.path.join(EX, "selection.example.yaml")
    r = run("build", MASTER, sel, "--outdir", str(out), "--company", "Acme Corp", "--role", "Data Scientist")
    assert "VERBATIM CHECK: PASS" in r.stdout, r.stdout + r.stderr
    assert r.returncode == 0
    assert sorted(os.listdir(out)) == ["Jordan Rivera_Acme Corp_Data Scientist.pdf"]
    r = run("build", MASTER, sel, "--outdir", str(out), "--company", "Acme Corp", "--role", "Data Scientist")
    assert "Jordan Rivera_Acme Corp_Data Scientist (2).pdf" in os.listdir(out)

@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice not installed")
def test_preview_does_not_save(tmp_path):
    out = tmp_path / "Resume Outputs"
    r = run("build", MASTER, os.path.join(EX, "selection.example.yaml"), "--preview", str(tmp_path / "d.pdf"))
    assert r.returncode == 0 and (tmp_path / "d.pdf").exists() and not out.exists()

def test_output_name_sanitized():
    assert output_name("Jordan Rivera", "AT&T / Labs", "ML Eng: Vision") == "Jordan Rivera_AT&T Labs_ML Eng Vision"
    assert output_name("Jordan Rivera").startswith("Jordan Rivera_Resume ")

def test_init_creates_layout(tmp_path):
    r = run("init", str(tmp_path / "Apps"))
    assert r.returncode == 0
    assert (tmp_path / "Apps" / "mega_resume.yaml").exists()
    assert (tmp_path / "Apps" / "Resume Outputs").is_dir()
    before = (tmp_path / "Apps" / "mega_resume.yaml").read_text()
    run("init", str(tmp_path / "Apps"))
    assert (tmp_path / "Apps" / "mega_resume.yaml").read_text() == before

@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice not installed")
def test_tampered_docx_detected(tmp_path):
    from megares.render import Renderer
    from megares.verify import check_docx
    m = M.load(MASTER)
    c = M.resolve(m, yaml.safe_load(open(os.path.join(EX, "selection.example.yaml"))))
    c["experience"][0][1][0] = dict(c["experience"][0][1][0], text="Reworded by a model")
    out = str(tmp_path / "t.docx")
    Renderer(m["style"]).docx(m, c, out)
    real = M.resolve(m, yaml.safe_load(open(os.path.join(EX, "selection.example.yaml"))))
    assert check_docx(out, m, real, m["style"]["bullet_char"])
