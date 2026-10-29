# Mega-Res

Keep one **mega resume** with every job, project and bullet you have ever written.
Give Claude a job posting, and Mega-Res builds a **one-page resume PDF** for it by selecting
the most relevant bullets **word for word** from your mega resume. Nothing is reworded.

## How you use it

1. Make a folder for your job applications (your **main folder**):

   ```
   Applications/
     mega_resume.yaml      <- everything you've done, written once, by you
     Resume Outputs/       <- tailored PDFs land here
   ```

2. Add the Mega-Res skill to Claude and connect your main folder.
3. Paste a job posting and say "tailor my resume."
4. Claude picks the bullets, builds the PDF, checks it, and saves it as
   `Resume Outputs/<Your Name>_<Company>_<Role>.pdf`. It also tells you what it chose,
   what it left out, and which requirements none of your bullets cover.

## Why the wording can't drift

Most AI resume tools ask a model to rewrite your bullets. Mega-Res makes the model
choose, not write:

| Step | Who does it | Can the wording change? |
|------|-------------|-------------------------|
| Write `mega_resume.yaml` | You | You control it |
| Pick bullets for a posting | Claude, as a list of **ids** | No text involved |
| Render the PDF | The bundled tool, reading your file directly | Copied verbatim |
| Verify | The bundled tool, on every build | Checked against your file |

Every build:
- fails if your mega resume changes during the build, and prints its SHA-256 fingerprint
- checks each bullet in the document equals a bullet in your mega resume exactly
- reads the text back out of the final PDF and checks every selected bullet, education
  line and skill is there verbatim, and that no bullet came from anywhere else
- enforces the page limit and any `priority: must` items
- refuses to save to `Resume Outputs` unless all of the above pass

The skill also instructs Claude never to edit your mega resume.

Limits: Claude's explanation of *why* it picked bullets is model output and isn't verified.
Anything with write access to your mega resume could change it; lock it
(`chmod a-w mega_resume.yaml`, `chmod u+w` to edit again) and compare the fingerprint each
build prints if you want to be sure.

## Install the skill

The skill is the folder `skill/mega-res/`. It is self-contained: instructions (`SKILL.md`),
the Python tool (`megares/`), and templates.

**Claude app (desktop/web):** zip the `skill/mega-res` folder and upload it as a skill in
Claude's settings. Then, in a chat, connect your main folder and paste a job posting.

**Claude Code:** copy the folder to `~/.claude/skills/mega-res`, then run `claude` from your
main folder and paste a job posting. Building locally needs:
- Python 3.9+ and `pip install -r skill/mega-res/requirements.txt`
- LibreOffice and poppler, for making and reading PDFs
  - macOS: `brew install --cask libreoffice && brew install poppler`
  - Debian/Ubuntu: `sudo apt install libreoffice-writer poppler-utils`

## Write your mega resume

Start from the template - Claude can do this for you, or run:

```bash
PYTHONPATH=skill/mega-res python3 -m megares init ~/Applications
```

Then replace the example content in `mega_resume.yaml` with yours. Every bullet needs a
unique `id`; `tags` are optional hints; `priority: must` forces an entry or bullet into every
resume. Tip: write 2-3 versions of an important accomplishment with different emphasis -
choosing between them gives you tailoring without rewording.

Check it any time:

```bash
PYTHONPATH=skill/mega-res python3 -m megares check ~/Applications/mega_resume.yaml
```

## Use without Claude

Write a selection file by hand (`skill/mega-res/templates/selection.example.yaml`), then:

```bash
PYTHONPATH=skill/mega-res python3 -m megares build ~/Applications/mega_resume.yaml selection.yaml \
  --company "Acme" --role "Data Scientist" --outdir ~/Applications/"Resume Outputs"
```

## Formatting

A classic single-column layout: centered name, ruled section headers, right-aligned dates.
Font, sizes, margins, bullet character and page limit are set in the optional `style:` block
of your mega resume. Rendering uses LibreOffice; Times New Roman falls back to the
metric-compatible Liberation Serif where it isn't installed, so line breaks stay the same.

## Development

```bash
pip install -r skill/mega-res/requirements.txt pytest
python3 -m pytest tests
```

## License

MIT
