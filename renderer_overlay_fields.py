from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pikepdf
from reportlab.pdfgen import canvas

# --- helpers ---

def load_template(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def get_pdf_page_sizes_points(pdf_path: str) -> List[Tuple[float, float]]:
    """Return [(width_pt, height_pt), ...] from MediaBox for each page."""
    sizes: List[Tuple[float, float]] = []
    with pikepdf.open(pdf_path) as pdf:
        for p in pdf.pages:
            mb = p.MediaBox  # [llx, lly, urx, ury]
            w = float(mb[2]) - float(mb[0])
            h = float(mb[3]) - float(mb[1])
            sizes.append((w, h))
    return sizes

# --- field drawing ---

def _draw_fields_for_page(c: canvas.Canvas, fields: List[Dict[str, Any]]) -> None:
    form = c.acroForm

    for f in fields:
        ftype = f["type"]
        name = f["name"]
        label = f.get("label", "") or name

        x = float(f["x"]); y = float(f["y"])
        w = float(f["w"]); h = float(f["h"])
        required = bool(f.get("required", False))

        if ftype == "text":
            multiline = bool(f.get("multiline", False))
            font_size = int(f.get("font_size", 11))
            value = f.get("default", "")

            flags = 0
            if multiline:
                flags |= 4096  # multiline
            if required:
                flags |= 2     # required

            form.textfield(
                name=name,
                tooltip=label,
                x=x, y=y, width=w, height=h,
                fontName="Helvetica", fontSize=font_size,
                value=value,
                borderStyle="inset", borderWidth=1,
                forceBorder=True,
                fieldFlags=flags,
            )

        elif ftype == "checkbox":
            size = min(w, h)
            form.checkbox(
                name=name,
                tooltip=label,
                x=x, y=y, size=size,
                checked=bool(f.get("default", False)),
                borderWidth=1,
                forceBorder=True,
            )

        elif ftype == "dropdown":
            options = f.get("options") or ["Option A", "Option B"]
            value = f.get("default", options[0] if options else "")
            flags = 2 if required else 0
            form.choice(
                name=name,
                tooltip=label,
                x=x, y=y, width=w, height=h,
                options=options,
                value=value,
                borderStyle="solid",
                borderWidth=1,
                forceBorder=True,
                fieldFlags=flags,
            )

        elif ftype == "radio":
            # ReportLab radio buttons: same "name" for group, different "value"
            # You place multiple radio rects with same name but different export values.
            export_value = f.get("value")
            if not export_value:
                raise ValueError(f"Radio field '{name}' missing 'value' (export value).")

            # size is usually square; use min(w,h)
            size = min(w, h)
            form.radio(
                name=name,  # group name
                tooltip=label,
                value=export_value,
                x=x, y=y,
                buttonStyle="circle",
                selected=(f.get("default") == export_value),
                size=size,
                borderWidth=1,
                forceBorder=True,
            )

        else:
            raise ValueError(f"Unsupported field type: {ftype}")

def build_fields_only_pdf(template_json: str, out_pdf: str) -> None:
    tpl = load_template(template_json)
    bg = (tpl.get("background_pdf") or "").strip()
    if not bg:
        raise ValueError("Template missing background_pdf")

    page_sizes = get_pdf_page_sizes_points(bg)
    pages = tpl.get("pages") or []

    # Index fields by page
    fields_by_page: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(len(page_sizes))}
    for p in pages:
        idx = int(p["index"])
        fields_by_page.setdefault(idx, []).extend(p.get("fields") or [])

    c = None
    for i, (pw, ph) in enumerate(page_sizes):
        c = canvas.Canvas(out_pdf, pagesize=(pw, ph)) if c is None else c
        c.setPageSize((pw, ph))
        _draw_fields_for_page(c, fields_by_page.get(i, []))
        c.showPage()

    if c is None:
        raise ValueError("No pages found.")
    c.save()

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("template", help="Template JSON with background_pdf and pages[]")
    ap.add_argument("out_fields_pdf", help="Output PDF containing only form fields")
    args = ap.parse_args()
    build_fields_only_pdf(args.template, args.out_fields_pdf)
    print("Wrote:", args.out_fields_pdf)