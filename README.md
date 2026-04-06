# FormFill PDF

**Draw fields. Export fillable PDFs.**

FormFill PDF is a desktop application that lets you turn any existing
PDF into a fully fillable form.\
Simply open a PDF, click and drag where you want fields to go, choose
the field type, and export a professional AcroForm-enabled PDF.

No design tools. No complex editors. Just point, drag, and generate.

------------------------------------------------------------------------

## ✨ Features

-   🖱️ **Click & drag field placement** directly on the PDF
-   🧾 Supports:
    -   Text fields
    -   Multi-line text areas
    -   Checkboxes
    -   Radio buttons (grouped automatically)
    -   Dropdown menus
-   📄 **Multi-page PDFs supported**
-   🔁 **Copy / Paste / Duplicate field groups** for fast form building
-   📐 Move multiple fields together for clean layouts
-   👁️ **Preview a "filled" version** to see how the final form will
    look
-   📤 **Export a true fillable PDF (AcroForm)** --- not flattened,
    fully interactive
-   💾 Save/load layouts via JSON templates

------------------------------------------------------------------------

## 🚀 Typical Workflow

1.  **Open a PDF** you already have (contract, worksheet, intake form,
    etc.)
2.  **Choose a field type** (text, checkbox, radio, dropdown, textarea)
3.  **Click and drag** on the page to place fields
4.  (Optional) **Copy, paste, and duplicate** blocks of fields for
    repeated sections
5.  **Export** as a fillable PDF
6.  (Optional) **Generate a preview-filled version** to verify layout

------------------------------------------------------------------------

## 🛠️ Installation

FormFill PDF runs as a Python desktop app.

### Requirements

-   Python 3.9+
-   Windows (macOS/Linux may work but are not officially tested)

### Install dependencies

``` bash
pip install reportlab pikepdf pymupdf pillow
```

### Run the app

From the project folder:

``` bash
python designer_app.py
```

You can also launch it via a `.bat` file for one-click startup on
Windows.

------------------------------------------------------------------------

## 🧩 Supported Field Types

  Field Type   Description
  ------------ ------------------------------------------
  Text         Single-line text input
  Textarea     Multi-line text input
  Checkbox     Independent on/off field
  Radio        Grouped selection (one choice per group)
  Dropdown     Select from predefined options

Radio buttons copied as a group are **automatically renamed** so each
question remains independent.

------------------------------------------------------------------------

## 📤 Export Options

### 1️⃣ Fillable PDF

Generates a fully interactive PDF with real AcroForm fields that can be
filled in any standard PDF viewer.

### 2️⃣ Preview-Filled PDF

Creates a version with sample data inserted so you can visually confirm
layout and spacing before distributing.

------------------------------------------------------------------------

## 🧠 Why FormFill PDF?

Most tools for making fillable PDFs are either: - Expensive - Web-based
(privacy concerns) - Overly complex

**FormFill PDF focuses on speed, control, and simplicity.**\
If you can draw a box on a page, you can build a form.

------------------------------------------------------------------------

## 📁 Project Structure

``` text
FormFillPDF/
│
├── designer_app.py      # Main desktop application
├── README.md
└── (optional)
    └── launch_formfill.bat
```

------------------------------------------------------------------------

## ⚠️ Known Notes

-   This tool generates **AcroForm** fields (not XFA).
-   Field names must be unique per form (handled automatically when
    duplicating).
-   Background PDFs are never modified --- the fillable layer is merged
    safely.

------------------------------------------------------------------------

## 🧭 Roadmap Ideas

-   Snap-to-grid alignment
-   Label text overlay support
-   Batch processing of multiple PDFs
-   Custom themes / dark mode
-   Packaging as a standalone EXE

------------------------------------------------------------------------

## 📜 License

This project is currently provided as-is for personal and experimental
use.\
If you plan to distribute or commercialize it, verify third-party
library licenses.

------------------------------------------------------------------------

## 💬 About

**FormFill PDF** was built to make creating professional, fillable PDFs
as intuitive as drawing boxes on a page.

If you've ever said *"Why is this so hard?"* when trying to make a form
--- this tool is for you.
