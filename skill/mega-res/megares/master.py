"""Load and validate a master resume file. Read-only: nothing here writes to the master."""
import hashlib, os, stat, yaml

DEFAULT_STYLE = {
    "font": "Times New Roman", "body_size": 10, "name_size": 18, "section_size": 12,
    "margin_lr_in": 0.5, "margin_tb_in": 0.5, "bullet_indent_in": 0.375,
    "bullet_char": "●", "page_limit": 1,
    "skills_layout": "inline",   # "inline": one comma-separated line; "lines": one item per line
}

class MasterError(Exception):
    pass

def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def is_read_only(path):
    return not (os.stat(path).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))

def load(path):
    with open(path, encoding="utf-8") as f:
        m = yaml.safe_load(f)
    validate(m)
    m["style"] = {**DEFAULT_STYLE, **(m.get("style") or {})}
    return m

def validate(m):
    if not isinstance(m, dict) or "header" not in m:
        raise MasterError("master must contain a 'header' section")
    seen = set()
    def claim(i, where):
        if not i:
            raise MasterError(f"missing id in {where}")
        if i in seen:
            raise MasterError(f"duplicate id '{i}'")
        seen.add(i)
    for e in m.get("education", []):
        claim(e.get("id"), "education")
        for l in e.get("lines", []):
            claim(l.get("id"), f"education '{e.get('id')}'")
            if not l.get("text"): raise MasterError(f"line '{l['id']}' has no text")
    for key in ("experience", "projects"):
        for e in m.get(key, []):
            claim(e.get("id"), key)
            for b in e.get("bullets", []):
                claim(b.get("id"), f"{key} '{e.get('id')}'")
                if not b.get("text"): raise MasterError(f"bullet '{b['id']}' has no text")
    skills = m.get("skills", [])
    if len(skills) != len(set(skills)):
        raise MasterError("duplicate skill strings")

def find(items, ident, kind, parent):
    for i in items:
        if i["id"] == ident:
            return i
    raise MasterError(f"unknown {kind} id '{ident}' in {parent}")

def resolve(master, sel):
    """Turn a selection (ids only) into the verbatim content to render."""
    out = {"education": [], "experience": [], "projects": [], "skills": []}
    eds = sel.get("education")
    if eds is None:
        eds = [{"id": e["id"], "lines": [l["id"] for l in e.get("lines", [])]} for e in master.get("education", [])]
    for es in eds:
        e = find(master.get("education", []), es["id"], "education", "education")
        lines = [find(e.get("lines", []), i, "education line", e["id"]) for i in es.get("lines", [])]
        out["education"].append((e, lines))
    for key in ("experience", "projects"):
        for es in sel.get(key) or []:
            e = find(master.get(key, []), es["id"], key, key)
            bl = [find(e["bullets"], i, "bullet", e["id"]) for i in es.get("bullets", [])]
            if not bl:
                raise MasterError(f"entry '{e['id']}' selected with zero bullets")
            if len(set(es["bullets"])) != len(es["bullets"]):
                raise MasterError(f"entry '{e['id']}' repeats a bullet")
            out[key].append((e, bl))
    sk = sel.get("skills", "all")
    if sk == "all":
        sk = list(master.get("skills", []))
    for s in sk:
        if s not in master.get("skills", []):
            raise MasterError(f"skill not in master (must match exactly): {s}")
    out["skills"] = sk
    # must-include enforcement
    chosen = {b["id"] for _, bl in out["experience"] + out["projects"] for b in bl}
    chosen_entries = {e["id"] for e, _ in out["experience"] + out["projects"]}
    for key in ("experience", "projects"):
        for e in master.get(key, []):
            if e.get("priority") == "must" and e["id"] not in chosen_entries:
                raise MasterError(f"entry '{e['id']}' is priority: must but not selected")
            for b in e.get("bullets", []):
                if b.get("priority") == "must" and b["id"] not in chosen:
                    raise MasterError(f"bullet '{b['id']}' is priority: must but not selected")
    return out
