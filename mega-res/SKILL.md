---
name: mega-res
description: Tailor a one-page resume to a job posting by selecting whole, verbatim bullets from the user's mega_resume.yaml and saving the PDF to their Resume Outputs folder. Use when the user pastes a job posting, asks to tailor a resume, or mentions Mega-Res.
---

# Mega-Res

Builds a one-page resume PDF for a job posting by choosing entries and bullets, **by id**, from
the user's master resume. The bundled tool renders the text straight from the master and
verifies the PDF word for word, so bullet wording never passes through you.

This skill folder is self-contained. `SKILL_DIR` below means the folder this SKILL.md is in.
Run the tool as:

    PYTHONPATH="$SKILL_DIR" python3 -m megares <command> ...

## The user's main folder

    <main folder>/
      mega_resume.yaml      <- the master (the user writes and edits it)
      Resume Outputs/       <- finished PDFs: "<Person Name>_<Company>_<Role>.pdf"

If the folder has no `mega_resume.yaml`:
- If the user has a resume PDF (in the main folder, or attached), offer to import it:
  `python3 -m megares import "<resume.pdf>" "<main folder>"`. The tool writes the master
  itself after verifying every item against the PDF; you never write it. Show the user the
  summary it prints (organizations, titles, dates, bullet counts) and any warnings or unused
  lines, and ask them to skim the file. If it fails, explain the reason using the README's
  "where it fails" table; do not hand-write a master to work around it.
  In mode B, stage the PDF, run the import in the workspace with `--out`, then copy the
  resulting file into the main folder with the file-commit tool (never over an existing one).
- Otherwise offer `python3 -m megares init "<main folder>"` (folder structure plus an example
  master the user replaces with their own content).

## Hard rules
1. **The master is read-only to you.** Never create (except via `init` or `import`), edit, rewrite, reformat
   or retype `mega_resume.yaml`, even to fix a typo. Report problems in it to the user instead.
   Move it only as a byte-for-byte file copy (cp, or the file-staging tool), never by writing
   its contents yourself.
2. **Never write bullet text.** Your only input to the tool is a selection file of ids.
3. **Save only builds that print `VERBATIM CHECK: PASS`** and fit the page limit; the tool
   refuses to save anything else. On FAIL, report it; do not work around it.
4. Only the final PDF goes in `Resume Outputs`. Drafts go to a scratch location via `--preview`.

## Step 0 - find where things run
Pick the first that applies:

**A. Local shell with the main folder** (Claude Code, or a shell on the user's computer that has
Python, LibreOffice `soffice` and poppler `pdftotext`/`pdfinfo`):
run everything in place. `MASTER="<main folder>/mega_resume.yaml"`,
`OUTDIR="<main folder>/Resume Outputs"`.

**B. Cloud workspace + the main folder connected from the user's computer** (rendering tools
are missing on the computer, or there is no shell there):
1. Stage `mega_resume.yaml` into the workspace with the file-staging tool (a byte copy).
2. If a shell on the computer is available, run `shasum -a 256` on the original and compare it
   with `python3 -m megares check` on the staged copy. They must match; if not, stop and report.
3. Build in the workspace with `OUTDIR` = a local folder, then copy the finished PDF into the
   connected folder's `Resume Outputs/` with the file-commit tool. Do not overwrite an existing
   file with the same name; add " (2)" instead.

**C. No folder connected:** ask the user to connect their main folder (preferred) or attach
`mega_resume.yaml`. With an attachment, build in the workspace and send the PDF to the user;
say that the check proves the PDF matches the attached copy.

Install anything missing: `pip install -r "$SKILL_DIR/requirements.txt"` (add
`--break-system-packages` if pip asks); LibreOffice and poppler from the system package manager.

## Workflow
1. Run `check` on the master. Note the person's name, SHA256 and bullet count.
2. From the posting, extract company, role title, required skills, preferred skills, domain,
   seniority and the 3-5 themes the role weighs most. If the company or role isn't in the
   posting, ask once; if still unknown, omit it (the tool falls back to a dated name).
3. Read the master in full. Score each bullet 0-3 (3 = direct evidence for a required
   skill/theme, 2 = preferred or adjacent, 1 = general strength, 0 = irrelevant). Judge on
   substance; tags are hints.
4. Select:
   - Keep recent entries and entries that prevent a visible timeline gap, with at least one
     bullet. Drop an entry only if it is both irrelevant and older or short.
   - Recent or highly relevant roles: 2-5 bullets; others: 1-2. Projects only if they score >= 2.
   - Order bullets within an entry by score. Keep entries in the master's order.
   - Education lines when relevant. Skills `all`, or an ordered subset of exact strings.
   - Include everything marked `priority: must`.
5. Write `selection.yaml` in a scratch folder - never in the main folder
   (format: `$SKILL_DIR/templates/selection.example.yaml`).
6. Draft builds (nothing saved to Resume Outputs):

       python3 -m megares build "$MASTER" selection.yaml --company "<Company>" --role "<Role>" --preview draft.pdf

   - `OVERFLOW`: remove the lowest-scoring bullet, rebuild.
   - `ROOM`: add the highest-scoring unused bullet, rebuild; stop before it would overflow.
7. Look at the draft (`pdftoppm -r 80 -png draft.pdf draft`) to confirm the layout.
8. Final build, same command with `--outdir "$OUTDIR"` instead of `--preview` (in mode B,
   then copy the PDF into the user's `Resume Outputs`).
9. Report briefly:
   - the saved file name and where it is
   - selected bullet ids per entry, with the reason for the strongest picks
   - close calls left out
   - posting requirements no bullet covers (cover-letter material, or bullets the user may
     want to add to the master themselves)
   - the verbatim-check result and the master SHA256

## Master file format
See `$SKILL_DIR/templates/mega_resume.example.yaml`. Every bullet has a unique `id` and verbatim
`text`; `tags` are optional; `priority: must` forces an entry or bullet in. An optional `style:`
block sets font, sizes, margins and page limit.
