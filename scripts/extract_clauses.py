"""
Deterministic 'evidence retrieval' for clause extraction.

This is step 1 of an LLM-assisted graph build: pull the RAW text a model would be given.
It does NO interpretation — it just dumps the PDF's text layer (with page markers) and, for
a set of target clause ids, prints the surrounding context. Whatever garbling pdfplumber
produces here is exactly what any downstream LLM has to work from.

Run:  python scripts/extract_clauses.py            # dump full text + show target clauses
      python scripts/extract_clauses.py 26.5.1.1   # just one clause's context
"""
from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PDF = next(iter(glob.glob(os.path.join(HERE, "..", "data", "standards", "*.pdf"))), None)
OUT = os.path.join(HERE, "..", "data", "standards", "is456_text.txt")

TARGETS = ["26.5.1.1", "26.5.1.2", "26.5.3.1", "40.1"]


def dump_text() -> str:
    import pdfplumber
    parts = []
    with pdfplumber.open(PDF) as pdf:
        for i, page in enumerate(pdf.pages):
            parts.append(f"\n===== PAGE {i} =====\n{page.extract_text() or ''}")
    text = "\n".join(parts)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    return text


def context(text: str, needle: str, before: int = 80, after: int = 400) -> list[str]:
    out = []
    for m in re.finditer(re.escape(needle), text):
        s = max(0, m.start() - before)
        out.append(text[s:m.start() + after])
    return out


def main() -> None:
    if not PDF:
        print("no PDF in data/standards/")
        return
    print(f"PDF: {os.path.basename(PDF)}")
    text = dump_text()
    print(f"dumped {len(text):,} chars of text layer -> {os.path.relpath(OUT)}")
    targets = sys.argv[1:] or TARGETS
    for t in targets:
        hits = context(text, t)
        print(f"\n########## '{t}' — {len(hits)} occurrence(s) ##########")
        # Show the first couple of occurrences; later ones are usually cross-references.
        for h in hits[:2]:
            print("-" * 60)
            print(h.strip())


if __name__ == "__main__":
    main()
