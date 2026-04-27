from __future__ import annotations

from fillable_pdf_core import build_fields_only_pdf_from_path


def build_fields_only_pdf(template_path: str, out_pdf: str) -> None:
    """Build a fields-only PDF from a designer template JSON file path."""
    build_fields_only_pdf_from_path(template_path, out_pdf)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("template", help="Template JSON with background_pdf and pages[]")
    ap.add_argument("out_fields_pdf", help="Output PDF containing only form fields")
    args = ap.parse_args()
    build_fields_only_pdf(args.template, args.out_fields_pdf)
    print("Wrote:", args.out_fields_pdf)
