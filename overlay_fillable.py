from __future__ import annotations

from fillable_pdf_core import make_fillable_from_template_path


def make_fillable_from_background(template_json: str, output_pdf: str) -> None:
    """CLI-compatible wrapper: template JSON path → fillable PDF (same pipeline as the GUI)."""
    make_fillable_from_template_path(template_json, output_pdf)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("template", help="Template JSON")
    ap.add_argument("output", help="Output fillable PDF")
    args = ap.parse_args()
    make_fillable_from_background(args.template, args.output)
    print("Wrote:", args.output)
