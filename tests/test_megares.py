import os, shutil, subprocess, sys, pytest, yaml
from megares import master as M

HERE = os.path.dirname(__file__)
EX = os.path.join(HERE, "..", "examples")
MASTER = os.path.join(EX, "master.example.yaml")

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
    r = subprocess.run([sys.executable, "-m", "megares", "build", MASTER,
                        os.path.join(EX, "selection.example.yaml"), str(tmp_path / "out")],
                       capture_output=True, text=True, cwd=os.path.join(HERE, ".."))
    assert "VERBATIM CHECK: PASS" in r.stdout, r.stdout + r.stderr
    assert r.returncode == 0

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
