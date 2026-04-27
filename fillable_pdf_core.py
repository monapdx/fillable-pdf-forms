from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pikepdf
from reportlab.pdfgen import canvas


def load_template_json(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_template(
    tpl: Dict[str, Any],
    *,
    require_background_readable: bool = True,
) -> List[str]:
    """
    Return a list of human-readable errors (empty if valid).
    """
    errors: List[str] = []
    bg = (tpl.get("background_pdf") or "").strip()
    if not bg:
        errors.append("Template missing background_pdf.")
        return errors

    bg_path = Path(bg)
    page_count: Optional[int] = None
    if require_background_readable and not bg_path.is_file():
        errors.append(f"Background PDF not found: {bg}")
        return errors
    try:
        with pikepdf.open(str(bg_path)) as pdf:
            page_count = len(pdf.pages)
    except Exception as ex:  # noqa: BLE001 — surface read errors to caller
        if require_background_readable:
            errors.append(f"Cannot read background PDF: {ex}")
            return errors
        page_count = None

    pages = tpl.get("pages")
    if pages is None:
        errors.append("Template missing pages array (use the designer export format).")
    elif not isinstance(pages, list):
        errors.append("Template 'pages' must be a list.")
    else:
        for pi, p in enumerate(pages):
            if not isinstance(p, dict):
                errors.append(f"pages[{pi}] must be an object.")
                continue
            if "index" not in p:
                errors.append(f"pages[{pi}] missing 'index'.")
                continue
            try:
                idx = int(p["index"])
            except (TypeError, ValueError):
                errors.append(f"pages[{pi}] has invalid 'index'.")
                continue
            if page_count is not None and (idx < 0 or idx >= page_count):
                errors.append(
                    f"pages[{pi}] index {idx} is out of range (valid: 0..{page_count - 1})."
                )

            fields = p.get("fields") or []
            if not isinstance(fields, list):
                errors.append(f"pages[{pi}].fields must be a list.")
                continue
            for fi, f in enumerate(fields):
                loc = f"pages[{pi}].fields[{fi}]"
                if not isinstance(f, dict):
                    errors.append(f"{loc} must be an object.")
                    continue
                ft = f.get("type")
                if ft not in ("text", "checkbox", "dropdown", "radio"):
                    errors.append(f"{loc}: unsupported type {ft!r}.")
                name = f.get("name")
                if not name or not str(name).strip():
                    errors.append(f"{loc}: missing or empty name.")
                if ft == "radio" and not (f.get("value") or "").strip():
                    errors.append(f"{loc}: radio field missing 'value' (export value).")

    return errors


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


def draw_fields_for_page(c: canvas.Canvas, fields: List[Dict[str, Any]]) -> None:
    form = c.acroForm

    for f in fields:
        ftype = f["type"]
        name = f["name"]
        label = f.get("label", "") or name

        x = float(f["x"])
        y = float(f["y"])
        w = float(f["w"])
        h = float(f["h"])
        required = bool(f.get("required", False))

        if ftype == "text":
            multiline = bool(f.get("multiline", False))
            font_size = int(f.get("font_size", 11))
            value = f.get("default", "")

            flags = 0
            if multiline:
                flags |= 4096  # multiline
            if required:
                flags |= 2  # required

            form.textfield(
                name=name,
                tooltip=label,
                x=x,
                y=y,
                width=w,
                height=h,
                fontName="Helvetica",
                fontSize=font_size,
                value=value,
                borderStyle="inset",
                borderWidth=1,
                forceBorder=True,
                fieldFlags=flags,
            )

        elif ftype == "checkbox":
            size = min(w, h)
            form.checkbox(
                name=name,
                tooltip=label,
                x=x,
                y=y,
                size=size,
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
                x=x,
                y=y,
                width=w,
                height=h,
                options=options,
                value=value,
                borderStyle="solid",
                borderWidth=1,
                forceBorder=True,
                fieldFlags=flags,
            )

        elif ftype == "radio":
            export_value = f.get("value")
            if not export_value:
                raise ValueError(f"Radio field '{name}' missing 'value' (export value).")

            size = min(w, h)
            form.radio(
                name=name,
                tooltip=label,
                value=export_value,
                x=x,
                y=y,
                buttonStyle="circle",
                selected=(f.get("default") == export_value),
                size=size,
                borderWidth=1,
                forceBorder=True,
            )

        else:
            raise ValueError(f"Unsupported field type: {ftype}")


def build_fields_only_pdf_from_dict(template_dict: Dict[str, Any], out_pdf: str) -> None:
    """
    Build a PDF that contains ONLY the form fields (and their widget annotations),
    matching the page sizes of the background PDF.
    """
    errs = validate_template(template_dict, require_background_readable=True)
    if errs:
        raise ValueError("Invalid template:\n" + "\n".join(errs))

    bg = (template_dict.get("background_pdf") or "").strip()
    page_sizes = get_pdf_page_sizes_points(bg)
    pages = template_dict.get("pages") or []

    fields_by_page: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(len(page_sizes))}
    for p in pages:
        idx = int(p["index"])
        fields_by_page[idx].extend(p.get("fields") or [])

    c: Optional[canvas.Canvas] = None
    for i, (pw, ph) in enumerate(page_sizes):
        if c is None:
            c = canvas.Canvas(out_pdf, pagesize=(pw, ph))
        else:
            c.setPageSize((pw, ph))

        draw_fields_for_page(c, fields_by_page.get(i, []))
        c.showPage()

    if c is None:
        raise ValueError("No pages found.")
    c.save()


def build_fields_only_pdf_from_path(template_path: str | Path, out_pdf: str) -> None:
    tpl = load_template_json(template_path)
    build_fields_only_pdf_from_dict(tpl, out_pdf)


def _merge_fields_pdf_onto_background(
    bg_path: str,
    fields_pdf_path: str,
    output_pdf: str,
) -> None:
    with pikepdf.open(bg_path) as bg_pdf, pikepdf.open(fields_pdf_path) as fields_pdf:
        if len(bg_pdf.pages) != len(fields_pdf.pages):
            raise ValueError("Background and fields PDF page counts do not match.")

        for i in range(len(bg_pdf.pages)):
            bg_page = bg_pdf.pages[i]
            fld_page = fields_pdf.pages[i]

            bg_page.add_overlay(fld_page)

            if "/Annots" in fld_page:
                if "/Annots" not in bg_page:
                    bg_page["/Annots"] = pikepdf.Array()

                for annot in fld_page["/Annots"]:
                    bg_page["/Annots"].append(bg_pdf.copy_foreign(annot))

        if "/AcroForm" in fields_pdf.Root:
            foreign_af = bg_pdf.copy_foreign(fields_pdf.Root["/AcroForm"])

            if "/AcroForm" not in bg_pdf.Root:
                bg_pdf.Root["/AcroForm"] = foreign_af
            else:
                bg_af = bg_pdf.Root["/AcroForm"]

                if "/Fields" not in bg_af:
                    bg_af["/Fields"] = pikepdf.Array()

                if "/Fields" in foreign_af:
                    for fld in foreign_af["/Fields"]:
                        bg_af["/Fields"].append(fld)

                if "/NeedAppearances" in foreign_af and "/NeedAppearances" not in bg_af:
                    bg_af["/NeedAppearances"] = foreign_af["/NeedAppearances"]

        if "/AcroForm" in bg_pdf.Root:
            bg_pdf.Root["/AcroForm"]["/NeedAppearances"] = pikepdf.Boolean(True)

        bg_pdf.save(output_pdf)


def make_fillable_from_background(template_dict: Dict[str, Any], output_pdf: str) -> None:
    """
    Create a fillable PDF: fields-only PDF overlaid on the background, with AcroForm merged.
    """
    bg = (template_dict.get("background_pdf") or "").strip()
    fd, tmp_path = tempfile.mkstemp(prefix="fillable_fields_", suffix=".pdf")
    os.close(fd)
    try:
        build_fields_only_pdf_from_dict(template_dict, tmp_path)
        _merge_fields_pdf_onto_background(bg, tmp_path, output_pdf)
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass


def make_fillable_from_template_path(template_path: str | Path, output_pdf: str) -> None:
    tpl = load_template_json(template_path)
    make_fillable_from_background(tpl, output_pdf)


def first_on_state_from_widget(widget: pikepdf.Object) -> Optional[pikepdf.Name]:
    """
    For checkbox/radio widgets, find an 'on' appearance name from /AP /N keys.
    """
    try:
        ap = widget.get("/AP", None)
        if not ap:
            return None
        n = ap.get("/N", None)
        if not n:
            return None

        for k in n.keys():
            if str(k) != "/Off":
                return k
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return None


def create_preview_filled_pdf(fillable_pdf_path: str, out_preview_pdf_path: str) -> None:
    """
    Write a second PDF where form fields have sample values.
    """
    with pikepdf.open(fillable_pdf_path) as pdf:
        if "/AcroForm" not in pdf.Root:
            raise ValueError("No /AcroForm found in PDF.")

        af = pdf.Root["/AcroForm"]
        af["/NeedAppearances"] = pikepdf.Boolean(True)

        for page in pdf.pages:
            if "/Annots" not in page:
                continue

            for annot in page["/Annots"]:
                subtype = annot.get("/Subtype", None)
                if str(subtype) != "/Widget":
                    continue

                ft = annot.get("/FT", None)
                if not ft:
                    continue

                ft_s = str(ft)

                if ft_s == "/Tx":
                    annot["/V"] = pikepdf.String("Sample text")

                elif ft_s == "/Ch":
                    opt = annot.get("/Opt", None)
                    if opt is None and "/Parent" in annot:
                        opt = annot["/Parent"].get("/Opt", None)
                    if opt and len(opt) > 0:
                        first = opt[0]
                        if isinstance(first, pikepdf.Array) and len(first) > 0:
                            annot["/V"] = first[0]
                        else:
                            annot["/V"] = first
                    else:
                        annot["/V"] = pikepdf.String("Option A")

                elif ft_s == "/Btn":
                    on_state = first_on_state_from_widget(annot)
                    if on_state is None:
                        continue
                    annot["/V"] = on_state
                    annot["/AS"] = on_state

        pdf.save(out_preview_pdf_path)
