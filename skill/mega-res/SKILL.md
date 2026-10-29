---
name: mega-res
description: Tailor a one-page resume to a pasted job posting by selecting whole, verbatim bullets from the user's Mega-Res master resume. Use when asked to tailor a resume, match a resume to a job, or given a job posting to apply to.
---

# Mega-Res

Builds a one-page .docx and .pdf for a job posting by choosing entries and bullets, by id,
from the user's master resume. The Mega-Res tool renders the text straight from the master
and verifies the output word for word, so wording never passes through you.

## Hard rules
1. **The master is read-only to you.** Never create, edit, rewrite, reformat, copy or move the
   master file, even to fix a typo. If you see an error in it, report it to the user.
2. **Never write bullet text.** Your only output to the tool is a selection file of ids.
3. **A build counts only if `VERBATIM CHECK: PASS`.** On FAIL, report it; do not work around it.
4. Respect `priority: must` and the page limit; the tool enforces both.

## Setup
- Locate the Mega-Res repo (this skill lives in `skill/mega-res/` inside it) and install
  `pip install -r requirements.txt`. LibreOffice (`soffice`) and poppler (`pdftotext`, `pdfinfo`,
  `pdftoppm`) must be installed.
- Ask the user for the master's path if you don't know it. Run
  `python -m megares check <MASTER>` and report the SHA256 and whether it is read-only.
  If it is writable, suggest `chmod a-w <MASTER>` to the user; do not run it yourself unless asked.

## Workflow
1. From the posting, extract required skills, preferred skills, domain, seniority and the 3-5
   themes the role weighs most.
2. Read the master in full. Score each bullet 0-3 (3 = direct evidence for a required
   skill/theme, 2 = preferred or adjacent, 1 = general strength, 0 = irrelevant). Judge on
   substance; tags are hints, not the answer.
3. Select:
   - Keep recent entries and entries that prevent a visible gap, with at least one bullet.
     Drop an entry only if it is both irrelevant and older or short.
   - Recent or highly relevant roles: 2-5 bullets; others: 1-2. Projects only if they score >= 2.
   - Order bullets within an entry by score. Keep entries in the master's order.
   - Education lines when relevant. Skills `all`, or an ordered subset of exact strings.
4. Write `selection.yaml` in a working folder outside the master's folder
   (format: `examples/selection.example.yaml`). Then run:
   `python -m megares build <MASTER> selection.yaml out/<Name>_Resume_<Company>_<Role> --require-read-only`
   (drop `--require-read-only` only if the user declined to lock the master).
5. Iterate on the report:
   - `OVERFLOW`: remove the lowest-scoring bullet, rebuild.
   - `ROOM`: add the highest-scoring unused bullet, rebuild; stop before it would overflow.
6. Render the PDF to PNG (`pdftoppm -r 80 -png`) and look at it.
7. Deliver the .docx and .pdf with a short report:
   - selected bullet ids per entry, with the reason for the strongest picks
   - close calls left out
   - posting requirements no master bullet covers (cover-letter material, or new bullets
     the user may want to write into the master themselves)
   - the master SHA256 and the verbatim-check result
