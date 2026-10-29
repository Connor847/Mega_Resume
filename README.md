# Mega-Res

Keep one **master resume** with every job, project and bullet you have ever written.
Paste a job posting into Claude, and Mega-Res builds a **one-page resume** for it by
selecting the most relevant bullets **word for word** from your master. Nothing is reworded.

## Why the wording can't drift

Most "AI resume tailoring" asks a model to rewrite your bullets. Mega-Res makes the model
choose, not write:

| Step | Who does it | Can the wording change? |
|------|-------------|-------------------------|
| Write and edit `master.yaml` | You | You control it |
| Pick bullets for a posting | Claude, as a list of **ids** | No text involved |
| Render .docx / .pdf | `megares build`, reading your master directly | Copied verbatim |
| Verify | `megares build`, automatically | Checked against the master |

`megares build`:
- refuses to run if the master is writable (with `--require-read-only`), so lock it with `chmod a-w`
- fails if the master's SHA-256 changes during the build
- checks every bullet in the .docx equals a master bullet exactly, in the selected order
- extracts the text from the final PDF and checks every selected bullet, education line and skill
  appears verbatim, and that no bullet in the PDF comes from anywhere other than the master
- enforces the page limit and `priority: must` items

Limits: the selection rationale Claude writes for you is model output and isn't verified.
Any agent with write access to your master *could* still change it - locking the file and
checking the SHA-256 that every build prints is how you catch that.

## Install

Requires Python 3.9+, LibreOffice (`soffice`, for PDF conversion) and poppler
(`pdftotext`, `pdfinfo`).

```bash
git clone https://github.com/<you>/mega-res.git && cd mega-res
pip install -r requirements.txt
# macOS: brew install --cask libreoffice && brew install poppler
# Debian/Ubuntu: sudo apt install libreoffice-writer poppler-utils
```

## Set up your master

```bash
mkdir -p my && cp examples/master.example.yaml my/master.yaml   # my/ is git-ignored
# edit my/master.yaml with your content
python -m megares check my/master.yaml
chmod a-w my/master.yaml          # lock it; chmod u+w to edit again
```

Every bullet needs a unique `id`. `tags` are optional hints for selection.
Mark anything that must always appear with `priority: must`.
Tip: write 2-3 versions of an important accomplishment with different emphasis -
selection picks the best fit, which gives you tailoring without rewording.

## Use with Claude

Install the skill in `skill/mega-res/` (Claude Code: copy it to `~/.claude/skills/mega-res/`;
Claude apps: upload the folder as a skill). Then paste a job posting and say
"tailor my resume - master is at my/master.yaml". Claude writes a selection file, runs the
build, adjusts until the page is full but not over, and reports what it chose, what it left
out, and which requirements none of your bullets cover.

## Use without Claude

Write a selection file by hand (see `examples/selection.example.yaml`) and run:

```bash
python -m megares build my/master.yaml selection.yaml out/Resume_Acme --require-read-only
```

## Formatting

The layout is a classic single-column resume (centered name, ruled section headers,
right-aligned dates). Font, sizes, margins, bullet character and page limit are set in the
master's optional `style:` block. Rendering uses LibreOffice; Times New Roman falls back to
the metric-compatible Liberation Serif where it isn't installed, so line breaks match Word.

## Tests

```bash
pip install pytest && python -m pytest tests
```

## License

MIT
