from __future__ import annotations

"""
Legacy single-page template renderer (root-level "fields", optional "page.size").

For multi-page PDFs and designer exports, use fillable_pdf_core.make_fillable_from_background
or overlay_fillable / pdf_overlay with a template JSON that includes background_pdf and pages[].
"""

import json
from pathlib import Path
from typing import Any, Dict

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.colors import black


PAGE_SIZES = {
    "LETTER": letter,
    "A4": A4,
}


def load_template(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def render_fillable_pdf(template_path: str, output_pdf: str) -> None:
    tpl = load_template(Path(template_path))

    page_size_name = (tpl.get("page") or {}).get("size", "LETTER")
    page_size = PAGE_SIZES.get(page_size_name.upper(), letter)
    w_page, h_page = page_size

    c = canvas.Canvas(output_pdf, pagesize=page_size)

    # Basic doc info
    meta = tpl.get("meta") or {}
    if meta.get("title"):
        c.setTitle(meta["title"])
    if meta.get("author"):
        c.setAuthor(meta["author"])

    form = c.acroForm

    # Optional: draw labels + outlines (you can remove later)
    c.setStrokeColor(black)

    for f in tpl.get("fields", []):
        ftype = f["type"]
        name = f["name"]

        x = float(f["x"])
        y = float(f["y"])
        fw = float(f["w"])
        fh = float(f["h"])

        label = f.get("label", "")
        font_size = int(f.get("font_size", 11))
        required = bool(f.get("required", False))

        # Draw label above field (optional)
        if label:
            c.setFont("Helvetica", 10)
            c.drawString(x, y + fh + 4, label)

        if ftype == "text":
            multiline = bool(f.get("multiline", False))
            value = f.get("default", "")

            # ReportLab uses fieldFlags for multiline etc via "fieldFlags" param
            # Multiline flag is 4096; required is 2 (per PDF spec flags)
            flags = 0
            if multiline:
                flags |= 4096
            if required:
                flags |= 2

            form.textfield(
                name=name,
                tooltip=label or name,
                x=x, y=y,
                width=fw, height=fh,
                fontName="Helvetica",
                fontSize=font_size,
                value=value,
                borderStyle="inset",
                borderWidth=1,
                forceBorder=True,
                fieldFlags=flags,
            )

        elif ftype == "checkbox":
            # Checkbox size usually square; we’ll respect w/h but use min as size
            size = min(fw, fh)
            form.checkbox(
                name=name,
                tooltip=label or name,
                x=x, y=y,
                size=size,
                checked=bool(f.get("default", False)),
                borderWidth=1,
                forceBorder=True,
            )

        elif ftype == "dropdown":
            options = f.get("options", ["Option A", "Option B"])
            value = f.get("default", options[0] if options else "")
            flags = 0
            if required:
                flags |= 2

            form.choice(
                name=name,
                tooltip=label or name,
                x=x, y=y,
                width=fw, height=fh,
                options=options,
                value=value,
                borderStyle="solid",
                borderWidth=1,
                forceBorder=True,
                fieldFlags=flags,
            )

        else:
            raise ValueError(f"Unsupported field type: {ftype}")

    c.showPage()
    c.save()


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Render a fillable PDF from a JSON template.")
    ap.add_argument("template", help="Path to template JSON")
    ap.add_argument("output", help="Output PDF path")
    args = ap.parse_args()

    render_fillable_pdf(args.template, args.output)
    print(f"Wrote: {args.output}")