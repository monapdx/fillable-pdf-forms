from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pikepdf

from renderer import render_fillable_pdf


def overlay_fields_onto_background(template_path: str, output_pdf: str) -> None:
    tpl = json.loads(Path(template_path).read_text(encoding="utf-8"))
    bg = (tpl.get("background_pdf") or "").strip()
    if not bg:
        raise ValueError("Template has no background_pdf set. Provide a background PDF path.")

    tmp_fields_pdf = Path(output_pdf).with_suffix(".fields_tmp.pdf")
    render_fillable_pdf(template_path, str(tmp_fields_pdf))

    with pikepdf.open(bg) as bg_pdf, pikepdf.open(tmp_fields_pdf) as fields_pdf:
        if len(bg_pdf.pages) != len(fields_pdf.pages):
            # MVP: require same page count
            raise ValueError("Background PDF and fields PDF must have same page count (MVP).")

        for i in range(len(bg_pdf.pages)):
            # Put field drawings on top (as content)
            bg_pdf.pages[i].add_overlay(fields_pdf.pages[i])

        # IMPORTANT: AcroForm lives at document level; copy it over so fields remain fillable
        if "/AcroForm" in fields_pdf.Root:
            bg_pdf.Root["/AcroForm"] = fields_pdf.Root["/AcroForm"]

        bg_pdf.save(output_pdf)

    try:
        tmp_fields_pdf.unlink()
    except OSError:
        pass


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Overlay fillable fields onto a background PDF.")
    ap.add_argument("template", help="Path to template JSON (with background_pdf set)")
    ap.add_argument("output", help="Output PDF path")
    args = ap.parse_args()

    overlay_fields_onto_background(args.template, args.output)
    print(f"Wrote: {args.output}")