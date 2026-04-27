from __future__ import annotations

from fillable_pdf_core import make_fillable_from_template_path


def overlay_fields_onto_background(template_path: str, output_pdf: str) -> None:
    """
    Overlay AcroForm fields from a designer template onto the background PDF.
    Uses the same merge logic as the GUI (annot copy + AcroForm merge).
    """
    make_fillable_from_template_path(template_path, output_pdf)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Overlay fillable fields onto a background PDF.")
    ap.add_argument("template", help="Path to template JSON (with background_pdf set)")
    ap.add_argument("output", help="Output PDF path")
    args = ap.parse_args()

    overlay_fields_onto_background(args.template, args.output)
    print(f"Wrote: {args.output}")
