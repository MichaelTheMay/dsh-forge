# DSH Forge system report

Upload `DSH_Forge_Overleaf.zip` with **Overleaf > New Project > Upload Project**. Overleaf detects `main.tex` automatically; use pdfLaTeX. Overleaf runs BibTeX automatically. Recompile from scratch if references initially show question marks.

Files:

- `main.tex`: Overleaf entry point
- `paper.tex`: complete editable report, including authors and affiliations
- `dshforge.sty`: independent two-column systems-paper style
- `paper.bib`: source references pinned to the reviewed revision

Local compilation with TeX Live:

```text
pdflatex -interaction=nonstopmode -halt-on-error paper.tex
bibtex paper
pdflatex -interaction=nonstopmode -halt-on-error paper.tex
pdflatex -interaction=nonstopmode -halt-on-error paper.tex
```

Evidence cutoff: 13 September 2026, reviewed revision `fc67d5956538d95c1f4bcb2e71315186cf8c2129`.

The report separates release observations, code and CI evidence, and repository-recorded case studies. No new community code was executed while preparing it. The current public feed was inspected on 13 September 2026; the pinned validation reports 206 Python tests and 43 JavaScript tests passing. The report describes implemented study mechanics but does not present independent human ratings or claim ranking superiority.

Author order and affiliations are written directly in `paper.tex`. Before external publication, confirm licensing, project ownership, and each author's approval of the final text. Update the revision and evidence cutoff whenever the implementation changes. Institutional affiliations identify the authors; they do not imply institutional endorsement.

## MLSys submission note

This ZIP is a public, authored system report. It is not an official MLSys submission package. MLSys 2027 requires its supplied LaTeX style, a two-column paper of at most 10 pages excluding references, and double-blind review. A research-track submission must remove author names, affiliations, acknowledgments, and identifying self-references. Build that anonymized version only when the evaluation described in Section 6 is complete.
