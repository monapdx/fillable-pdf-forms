from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog

# Preview rendering
import fitz  # PyMuPDF (GPL)
from PIL import Image, ImageTk

# PDF form generation / overlay
import pikepdf
from reportlab.pdfgen import canvas


# ----------------------------
# Data model
# ----------------------------

@dataclass
class Field:
    type: str  # text, checkbox, dropdown, radio
    name: str
    label: str
    x: float
    y: float
    w: float
    h: float
    font_size: int = 11
    required: bool = False
    multiline: bool = False
    options: Optional[List[str]] = None   # dropdown
    default: Optional[Any] = None         # text: str, checkbox: bool, dropdown: str, radio: value
    value: Optional[str] = None           # radio export value


# ----------------------------
# PDF helpers (fields-only + overlay)
# ----------------------------

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
            export_value = f.get("value")
            if not export_value:
                raise ValueError(f"Radio field '{name}' missing 'value' (export value).")

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


def build_fields_only_pdf(template_dict: Dict[str, Any], out_pdf: str) -> None:
    """
    Build a PDF that contains ONLY the form fields (and their widget annotations),
    matching the page sizes of the background PDF.
    """
    bg = (template_dict.get("background_pdf") or "").strip()
    if not bg:
        raise ValueError("Template missing background_pdf")

    page_sizes = get_pdf_page_sizes_points(bg)
    pages = template_dict.get("pages") or []

    fields_by_page: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(len(page_sizes))}
    for p in pages:
        idx = int(p["index"])
        fields_by_page.setdefault(idx, []).extend(p.get("fields") or [])

    c: Optional[canvas.Canvas] = None
    for i, (pw, ph) in enumerate(page_sizes):
        if c is None:
            c = canvas.Canvas(out_pdf, pagesize=(pw, ph))
        else:
            c.setPageSize((pw, ph))

        _draw_fields_for_page(c, fields_by_page.get(i, []))
        c.showPage()

    if c is None:
        raise ValueError("No pages found.")
    c.save()


def make_fillable_from_background(template_dict: Dict[str, Any], output_pdf: str) -> None:
    """
    1) Create a fields-only PDF (same page sizes as background)
    2) Overlay visuals onto background pages
    3) Copy widget annotations (/Annots) onto background pages (makes fields clickable)
    4) Copy/merge AcroForm using copy_foreign (pikepdf-safe)
    """
    bg = (template_dict.get("background_pdf") or "").strip()
    if not bg:
        raise ValueError("Template missing background_pdf")

    tmp = str(Path(output_pdf).with_suffix(".fields_tmp.pdf"))
    build_fields_only_pdf(template_dict, tmp)

    with pikepdf.open(bg) as bg_pdf, pikepdf.open(tmp) as fields_pdf:
        if len(bg_pdf.pages) != len(fields_pdf.pages):
            raise ValueError("Background and fields PDF page counts do not match.")

        # Overlay visuals + copy widget annotations per page
        for i in range(len(bg_pdf.pages)):
            bg_page = bg_pdf.pages[i]
            fld_page = fields_pdf.pages[i]

            # Visual overlay (optional but nice)
            bg_page.add_overlay(fld_page)

            # Copy widget annotations so fields are clickable/fillable
            if "/Annots" in fld_page:
                if "/Annots" not in bg_page:
                    bg_page["/Annots"] = pikepdf.Array()

                for annot in fld_page["/Annots"]:
                    bg_page["/Annots"].append(bg_pdf.copy_foreign(annot))

        # Copy / merge AcroForm safely across PDFs
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

        # Helps some viewers render appearances
        if "/AcroForm" in bg_pdf.Root:
            bg_pdf.Root["/AcroForm"]["/NeedAppearances"] = pikepdf.Boolean(True)

        bg_pdf.save(output_pdf)

    try:
        Path(tmp).unlink()
    except OSError:
        pass


# ----------------------------
# Preview-filled helper
# ----------------------------

def _first_on_state_from_widget(widget: pikepdf.Object) -> Optional[pikepdf.Name]:
    """
    For checkbox/radio widgets, find an 'on' appearance name from /AP /N keys.
    Typical keys: /Off and /Yes (or export value).
    """
    try:
        ap = widget.get("/AP", None)
        if not ap:
            return None
        n = ap.get("/N", None)
        if not n:
            return None

        # n is a dict-like object whose keys are Names
        keys = list(n.keys())
        for k in keys:
            if str(k) != "/Off":
                return k  # return the first non-Off
    except Exception:
        return None
    return None


def create_preview_filled_pdf(fillable_pdf_path: str, out_preview_pdf_path: str) -> None:
    """
    Write a second PDF where form fields have sample values.
    Uses /NeedAppearances so most viewers will render the filled values.
    """
    with pikepdf.open(fillable_pdf_path) as pdf:
        if "/AcroForm" not in pdf.Root:
            raise ValueError("No /AcroForm found in PDF.")

        af = pdf.Root["/AcroForm"]
        af["/NeedAppearances"] = pikepdf.Boolean(True)

        # Walk all pages' widget annotations (most reliable for mixed forms)
        for page in pdf.pages:
            if "/Annots" not in page:
                continue

            for annot in page["/Annots"]:
                # Widget annotations typically have /Subtype /Widget
                subtype = annot.get("/Subtype", None)
                if str(subtype) != "/Widget":
                    continue

                ft = annot.get("/FT", None)  # /Tx /Btn /Ch
                if not ft:
                    continue

                ft_s = str(ft)

                if ft_s == "/Tx":
                    # Text field
                    annot["/V"] = pikepdf.String("Sample text")
                    # leave /DA etc alone

                elif ft_s == "/Ch":
                    # Choice (dropdown/list)
                    # Try /Opt from the field/annot (may be on parent)
                    opt = annot.get("/Opt", None)
                    if opt is None and "/Parent" in annot:
                        opt = annot["/Parent"].get("/Opt", None)
                    if opt and len(opt) > 0:
                        # options can be strings or [export, display]
                        first = opt[0]
                        if isinstance(first, pikepdf.Array) and len(first) > 0:
                            annot["/V"] = first[0]
                        else:
                            annot["/V"] = first
                    else:
                        annot["/V"] = pikepdf.String("Option A")

                elif ft_s == "/Btn":
                    # Button: checkbox or radio
                    # Radio groups have /Kids; individual widgets still /Btn
                    on_state = _first_on_state_from_widget(annot)
                    if on_state is None:
                        continue
                    annot["/V"] = on_state
                    annot["/AS"] = on_state  # appearance state

        pdf.save(out_preview_pdf_path)


# ----------------------------
# Designer App
# ----------------------------

class DesignerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF Fillable Form Designer (Multi-page MVP)")
        self.geometry("1280x860")

        # PDF state
        self.background_pdf: str = ""
        self.doc: Optional[fitz.Document] = None
        self.page_count: int = 0
        self.current_page: int = 0

        # Preview state
        self.zoom: float = 1.6
        self.current_image: Optional[ImageTk.PhotoImage] = None
        self.page_points: Tuple[float, float] = (612, 792)  # updated per page
        self.preview_scale: float = self.zoom              # pixels per point (approx)

        # Fields: per-page list
        self.fields_by_page: Dict[int, List[Field]] = {}

        # Drag state
        self._mode: str = "idle"  # idle | create | move
        self._drag_start: Optional[Tuple[int, int]] = None
        self._drag_rect_id: Optional[int] = None

        # Selection/move state
        self.selected_index: Optional[int] = None
        self._move_start_xy_px: Optional[Tuple[int, int]] = None
        self._move_orig_xy_pt: Optional[Tuple[float, float]] = None

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(side="top", fill="x", padx=8, pady=8)

        ttk.Button(top, text="Open PDF…", command=self.open_pdf).pack(side="left")

        nav = ttk.Frame(top)
        nav.pack(side="left", padx=(12, 0))
        ttk.Button(nav, text="◀ Prev", command=self.prev_page).pack(side="left")
        ttk.Button(nav, text="Next ▶", command=self.next_page).pack(side="left", padx=(6, 0))

        ttk.Label(nav, text="Page:").pack(side="left", padx=(12, 4))
        self.page_var = tk.StringVar(value="0 / 0")
        ttk.Label(nav, textvariable=self.page_var).pack(side="left")

        ttk.Label(nav, text="Jump:").pack(side="left", padx=(12, 4))
        self.jump_var = tk.StringVar(value="1")
        ttk.Entry(nav, textvariable=self.jump_var, width=5).pack(side="left")
        ttk.Button(nav, text="Go", command=self.jump_to_page).pack(side="left", padx=(6, 0))

        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=12)

        ttk.Button(top, text="Export Template JSON…", command=self.export_template).pack(side="left")
        ttk.Button(top, text="Generate Fillable PDF…", command=self.generate_fillable_pdf).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="Preview Filled PDF…", command=self.preview_filled_pdf).pack(side="left", padx=(8, 0))

        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=12)

        ttk.Label(top, text="Type:").pack(side="left", padx=(0, 4))
        self.field_type = tk.StringVar(value="text")
        ttk.Combobox(
            top,
            textvariable=self.field_type,
            values=["text", "textarea", "checkbox", "radio", "dropdown"],
            width=10,
            state="readonly",
        ).pack(side="left")

        ttk.Label(top, text="Name/Group:").pack(side="left", padx=(12, 4))
        self.field_name = tk.StringVar(value="field_1")
        ttk.Entry(top, textvariable=self.field_name, width=16).pack(side="left")

        ttk.Label(top, text="Label:").pack(side="left", padx=(12, 4))
        self.field_label = tk.StringVar(value="Label")
        ttk.Entry(top, textvariable=self.field_label, width=20).pack(side="left")

        self.required_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Required", variable=self.required_var).pack(side="left", padx=(10, 0))

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=8, pady=8)

        self.canvas = tk.Canvas(main, bg="#ddd")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        right = ttk.Frame(main, width=360)
        right.pack(side="right", fill="y", padx=(10, 0))

        ttk.Label(right, text="Fields on this page").pack(anchor="w")
        self.listbox = tk.Listbox(right, height=18)
        self.listbox.pack(fill="x", pady=(4, 6))
        self.listbox.bind("<<ListboxSelect>>", self.on_list_select)

        btnrow = ttk.Frame(right)
        btnrow.pack(fill="x")
        ttk.Button(btnrow, text="Delete", command=self.delete_selected).pack(side="left", fill="x", expand=True)
        ttk.Button(btnrow, text="Rename…", command=self.rename_selected).pack(side="left", fill="x", expand=True, padx=(6, 0))

        size_row = ttk.Frame(right)
        size_row.pack(fill="x", pady=(8, 0))
        ttk.Button(size_row, text="Match size → ALL on page", command=self.match_size_all).pack(side="left", fill="x", expand=True)
        ttk.Button(size_row, text="Match size → SAME TYPE", command=self.match_size_same_type).pack(side="left", fill="x", expand=True, padx=(6, 0))

        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=10)

        self.info = tk.Text(right, height=18, wrap="word")
        self.info.pack(fill="both", expand=True)
        self._refresh_info()

    # ----------------------------
    # PDF open / preview
    # ----------------------------

    def open_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not path:
            return

        try:
            if self.doc is not None:
                self.doc.close()
        except Exception:
            pass

        self.background_pdf = path
        self.doc = fitz.open(path)
        self.page_count = self.doc.page_count
        self.current_page = 0
        self.fields_by_page = {i: [] for i in range(self.page_count)}
        self.selected_index = None

        self._render_current_page()
        self._update_page_label()
        self._refresh_fields_list()
        messagebox.showinfo("Loaded", f"Loaded PDF with {self.page_count} pages.\n\nTip: Click a field to select, drag to move.")

    def _render_current_page(self):
        if not self.doc:
            return

        page = self.doc.load_page(self.current_page)
        rect = page.rect  # points
        self.page_points = (rect.width, rect.height)

        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.preview_scale = self.zoom

        self.current_image = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, img.size[0], img.size[1]))
        self.canvas.create_image(0, 0, anchor="nw", image=self.current_image)
        self._redraw_field_boxes()

    def _update_page_label(self):
        self.page_var.set(f"{self.current_page + 1} / {self.page_count}")

    def prev_page(self):
        if not self.doc:
            return
        if self.current_page > 0:
            self.current_page -= 1
            self.selected_index = None
            self._render_current_page()
            self._update_page_label()
            self._refresh_fields_list()

    def next_page(self):
        if not self.doc:
            return
        if self.current_page < self.page_count - 1:
            self.current_page += 1
            self.selected_index = None
            self._render_current_page()
            self._update_page_label()
            self._refresh_fields_list()

    def jump_to_page(self):
        if not self.doc:
            return
        try:
            p = int(self.jump_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid", "Enter a page number (1-based).")
            return
        if p < 1 or p > self.page_count:
            messagebox.showerror("Out of range", f"Page must be 1 to {self.page_count}.")
            return
        self.current_page = p - 1
        self.selected_index = None
        self._render_current_page()
        self._update_page_label()
        self._refresh_fields_list()

    # ----------------------------
    # Selection / hit-testing
    # ----------------------------

    def _field_rect_canvas_px(self, f: Field) -> Tuple[float, float, float, float]:
        """Return (left, top, right, bottom) in canvas pixels for a field."""
        page_h_px = self.page_points[1] * self.preview_scale

        left = f.x * self.preview_scale
        right = (f.x + f.w) * self.preview_scale

        top = page_h_px - (f.y + f.h) * self.preview_scale
        bottom = page_h_px - f.y * self.preview_scale
        return left, top, right, bottom

    def _hit_test_field(self, x_px: float, y_px: float) -> Optional[int]:
        """Return index of topmost field containing point, else None."""
        fields = self.fields_by_page.get(self.current_page, [])
        # iterate reverse so later fields are treated as "on top"
        for idx in range(len(fields) - 1, -1, -1):
            l, t, r, b = self._field_rect_canvas_px(fields[idx])
            if l <= x_px <= r and t <= y_px <= b:
                return idx
        return None

    def _select_index(self, idx: Optional[int]):
        self.selected_index = idx
        # sync listbox selection
        self.listbox.selection_clear(0, "end")
        if idx is not None:
            self.listbox.selection_set(idx)
            self.listbox.activate(idx)
        self._redraw_field_boxes()

    def on_list_select(self, _evt):
        sel = self.listbox.curselection()
        if not sel:
            self._select_index(None)
            return
        self._select_index(sel[0])

    # ----------------------------
    # Mouse interactions: create vs move
    # ----------------------------

    def on_mouse_down(self, e):
        if not self.doc:
            return

        hit = self._hit_test_field(e.x, e.y)
        if hit is not None:
            # MOVE MODE
            self._mode = "move"
            self._select_index(hit)
            self._move_start_xy_px = (e.x, e.y)

            f = self.fields_by_page[self.current_page][hit]
            self._move_orig_xy_pt = (f.x, f.y)
            return

        # Otherwise CREATE MODE
        self._mode = "create"
        self._drag_start = (e.x, e.y)
        self._drag_rect_id = self.canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="red", width=2)

        # deselect when creating
        self._select_index(None)

    def on_mouse_drag(self, e):
        if self._mode == "create":
            if not self._drag_start or not self._drag_rect_id:
                return
            x0, y0 = self._drag_start
            self.canvas.coords(self._drag_rect_id, x0, y0, e.x, e.y)

        elif self._mode == "move":
            if self.selected_index is None or self._move_start_xy_px is None or self._move_orig_xy_pt is None:
                return

            dx_px = e.x - self._move_start_xy_px[0]
            dy_px = e.y - self._move_start_xy_px[1]

            dx_pt = dx_px / self.preview_scale
            dy_pt = -dy_px / self.preview_scale  # canvas down = pdf y decreases

            f = self.fields_by_page[self.current_page][self.selected_index]
            new_x = self._move_orig_xy_pt[0] + dx_pt
            new_y = self._move_orig_xy_pt[1] + dy_pt

            # clamp within page
            page_w_pt, page_h_pt = self.page_points
            new_x = max(0, min(new_x, page_w_pt - f.w))
            new_y = max(0, min(new_y, page_h_pt - f.h))

            f.x = float(new_x)
            f.y = float(new_y)
            self._redraw_field_boxes()

    def on_mouse_up(self, e):
        if not self.doc:
            return

        if self._mode == "move":
            self._mode = "idle"
            self._move_start_xy_px = None
            self._move_orig_xy_pt = None
            self._refresh_fields_list()
            return

        if self._mode != "create":
            self._mode = "idle"
            return

        if not self._drag_start or not self._drag_rect_id:
            self._mode = "idle"
            return

        x0, y0 = self._drag_start
        x1, y1 = e.x, e.y

        left, right = sorted([x0, x1])
        top, bottom = sorted([y0, y1])

        # min size
        if (right - left) < 8 or (bottom - top) < 8:
            self._cancel_create()
            self._mode = "idle"
            return

        # Convert canvas pixels (top-left origin) to PDF points (bottom-left origin)
        page_h_px = self.page_points[1] * self.preview_scale

        x_pt = left / self.preview_scale
        y_pt = (page_h_px - bottom) / self.preview_scale
        w_pt = (right - left) / self.preview_scale
        h_pt = (bottom - top) / self.preview_scale

        ui_type = self.field_type.get().strip()
        required = bool(self.required_var.get())
        label = self.field_label.get().strip()
        name_or_group = self.field_name.get().strip() or f"field_{self._next_field_number()}"

        field: Optional[Field] = None

        if ui_type in ("text", "textarea"):
            multiline = (ui_type == "textarea")
            font_size = simpledialog.askinteger(
                "Font size",
                "Font size (e.g., 10–12):",
                initialvalue=11,
                minvalue=6,
                maxvalue=36,
                parent=self,
            )
            if font_size is None:
                self._cancel_create()
                self._mode = "idle"
                return

            field = Field(
                type="text",
                name=name_or_group,
                label=label,
                x=float(x_pt), y=float(y_pt), w=float(w_pt), h=float(h_pt),
                font_size=int(font_size),
                required=required,
                multiline=multiline,
                default="",
            )

        elif ui_type == "checkbox":
            field = Field(
                type="checkbox",
                name=name_or_group,
                label=label,
                x=float(x_pt), y=float(y_pt), w=float(w_pt), h=float(h_pt),
                required=required,
                default=False,
            )

        elif ui_type == "dropdown":
            options_str = simpledialog.askstring(
                "Dropdown options",
                "Enter options separated by commas:\nExample: Red, Green, Blue",
                initialvalue="Option A, Option B",
                parent=self,
            )
            if options_str is None:
                self._cancel_create()
                self._mode = "idle"
                return
            options = [o.strip() for o in options_str.split(",") if o.strip()]
            if not options:
                messagebox.showerror("Invalid", "Dropdown needs at least one option.")
                self._cancel_create()
                self._mode = "idle"
                return

            field = Field(
                type="dropdown",
                name=name_or_group,
                label=label,
                x=float(x_pt), y=float(y_pt), w=float(w_pt), h=float(h_pt),
                required=required,
                options=options,
                default=options[0],
            )

        elif ui_type == "radio":
            export_value = simpledialog.askstring(
                "Radio option value",
                "Enter the export value for this radio button.\nExample: email",
                initialvalue="option1",
                parent=self,
            )
            if export_value is None or not export_value.strip():
                self._cancel_create()
                self._mode = "idle"
                return

            field = Field(
                type="radio",
                name=name_or_group,          # group name
                label=label,
                x=float(x_pt), y=float(y_pt), w=float(w_pt), h=float(h_pt),
                required=required,
                value=export_value.strip(),  # per-button value
                default=None,
            )

        else:
            messagebox.showerror("Unsupported", f"Unknown type: {ui_type}")
            self._cancel_create()
            self._mode = "idle"
            return

        self.fields_by_page.setdefault(self.current_page, []).append(field)

        # select newly added
        self._select_index(len(self.fields_by_page[self.current_page]) - 1)

        self._refresh_fields_list()
        self._redraw_field_boxes()
        self._cancel_create()

        self.field_name.set(f"field_{self._next_field_number()}")
        self._mode = "idle"

    def _cancel_create(self):
        if self._drag_rect_id:
            try:
                self.canvas.delete(self._drag_rect_id)
            except Exception:
                pass
        self._drag_start = None
        self._drag_rect_id = None

    def _next_field_number(self) -> int:
        total = sum(len(v) for v in self.fields_by_page.values()) if self.fields_by_page else 0
        return total + 1

    # ----------------------------
    # Uniform size tools
    # ----------------------------

    def match_size_all(self):
        """Match selected field size to ALL fields on current page."""
        if self.selected_index is None:
            messagebox.showinfo("Select a field", "Click a field (or select one in the list) first.")
            return
        fields = self.fields_by_page.get(self.current_page, [])
        if not fields:
            return
        src = fields[self.selected_index]
        for f in fields:
            f.w = src.w
            f.h = src.h
        self._redraw_field_boxes()

    def match_size_same_type(self):
        """Match selected field size to fields of SAME TYPE on current page."""
        if self.selected_index is None:
            messagebox.showinfo("Select a field", "Click a field (or select one in the list) first.")
            return
        fields = self.fields_by_page.get(self.current_page, [])
        if not fields:
            return
        src = fields[self.selected_index]
        src_type_key = ("textarea" if (src.type == "text" and src.multiline) else src.type)

        for f in fields:
            f_type_key = ("textarea" if (f.type == "text" and f.multiline) else f.type)
            if f_type_key == src_type_key:
                f.w = src.w
                f.h = src.h
        self._redraw_field_boxes()

    # ----------------------------
    # Field list / edit
    # ----------------------------

    def _refresh_fields_list(self):
        self.listbox.delete(0, "end")
        page_fields = self.fields_by_page.get(self.current_page, [])
        for f in page_fields:
            if f.type == "radio":
                self.listbox.insert("end", f"radio: {f.name} = {f.value}")
            elif f.type == "text" and f.multiline:
                self.listbox.insert("end", f"textarea: {f.name}")
            else:
                self.listbox.insert("end", f"{f.type}: {f.name}")

        # keep selection if possible
        if self.selected_index is not None and 0 <= self.selected_index < len(page_fields):
            self.listbox.selection_set(self.selected_index)
            self.listbox.activate(self.selected_index)

    def delete_selected(self):
        if self.selected_index is None:
            return
        page_fields = self.fields_by_page.get(self.current_page, [])
        if 0 <= self.selected_index < len(page_fields):
            del page_fields[self.selected_index]
        self.selected_index = None
        self._refresh_fields_list()
        self._redraw_field_boxes()

    def rename_selected(self):
        if self.selected_index is None:
            return
        page_fields = self.fields_by_page.get(self.current_page, [])
        if not (0 <= self.selected_index < len(page_fields)):
            return
        f = page_fields[self.selected_index]

        new_name = simpledialog.askstring(
            "Rename field",
            "Enter new field name (for radio: group name):",
            initialvalue=f.name,
            parent=self,
        )
        if new_name and new_name.strip():
            f.name = new_name.strip()

        if f.type == "radio":
            new_val = simpledialog.askstring(
                "Radio option value",
                "Enter export value for this radio button:",
                initialvalue=f.value or "",
                parent=self,
            )
            if new_val and new_val.strip():
                f.value = new_val.strip()

        self._refresh_fields_list()
        self._redraw_field_boxes()

    # ----------------------------
    # Drawing overlays
    # ----------------------------

    def _redraw_field_boxes(self):
        self.canvas.delete("fieldbox")
        if not self.doc:
            return

        fields = self.fields_by_page.get(self.current_page, [])
        for idx, f in enumerate(fields):
            l, t, r, b = self._field_rect_canvas_px(f)

            # selected highlight
            if self.selected_index == idx:
                outline = "red"
                width = 3
            else:
                outline = "blue"
                width = 2

            self.canvas.create_rectangle(l, t, r, b, outline=outline, width=width, tags="fieldbox")

            if f.type == "radio":
                label = f"{f.name}={f.value}"
            elif f.type == "text" and f.multiline:
                label = f"{f.name} (textarea)"
            else:
                label = f.name

            self.canvas.create_text(l + 4, t + 10, anchor="w", text=label, fill=outline, tags="fieldbox")

    # ----------------------------
    # Export / generate / preview-filled
    # ----------------------------

    def _build_template_dict(self) -> Dict[str, Any]:
        pages: List[Dict[str, Any]] = []
        for idx in range(self.page_count):
            fields = [asdict(f) for f in self.fields_by_page.get(idx, [])]
            pages.append({"index": idx, "fields": fields})

        return {
            "meta": {"title": "Fillable Form", "author": "PDF Fillable Form Designer"},
            "background_pdf": self.background_pdf,
            "pages": pages,
        }

    def export_template(self):
        if not self.doc or not self.background_pdf:
            messagebox.showerror("No PDF", "Open a PDF first.")
            return

        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return

        tpl = self._build_template_dict()
        Path(path).write_text(json.dumps(tpl, indent=2), encoding="utf-8")
        messagebox.showinfo("Exported", f"Template saved:\n{path}")

    def generate_fillable_pdf(self):
        if not self.doc or not self.background_pdf:
            messagebox.showerror("No PDF", "Open a PDF first.")
            return

        out_pdf = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out_pdf:
            return

        tpl = self._build_template_dict()
        try:
            make_fillable_from_background(tpl, out_pdf)
        except Exception as ex:
            messagebox.showerror("Error", str(ex))
            return

        messagebox.showinfo("Done", f"Fillable PDF created:\n{out_pdf}")

    def preview_filled_pdf(self):
        if not self.doc or not self.background_pdf:
            messagebox.showerror("No PDF", "Open a PDF first.")
            return

        # choose output preview file
        out_preview = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            title="Save Preview Filled PDF As…"
        )
        if not out_preview:
            return

        # create a temp fillable, then fill it
        tmp_fillable = str(Path(out_preview).with_suffix(".fillable_tmp.pdf"))

        tpl = self._build_template_dict()
        try:
            make_fillable_from_background(tpl, tmp_fillable)
            create_preview_filled_pdf(tmp_fillable, out_preview)
        except Exception as ex:
            messagebox.showerror("Error", str(ex))
            return
        finally:
            try:
                Path(tmp_fillable).unlink()
            except OSError:
                pass

        messagebox.showinfo("Done", f"Preview Filled PDF created:\n{out_preview}")

    def _refresh_info(self):
        self.info.delete("1.0", "end")
        self.info.insert("end", "How to use:\n")
        self.info.insert("end", "1) Open PDF…\n")
        self.info.insert("end", "2) Navigate pages (Prev/Next or Jump)\n")
        self.info.insert("end", "3) Drag empty area to CREATE a field\n")
        self.info.insert("end", "4) Click a field to SELECT it\n")
        self.info.insert("end", "5) Drag a selected field to MOVE it\n\n")
        self.info.insert("end", "Uniform sizing:\n")
        self.info.insert("end", "- Select a field, then use match-size buttons\n\n")
        self.info.insert("end", "Preview Filled PDF:\n")
        self.info.insert("end", "- Generates a fillable PDF and saves a second version with sample values.\n")
        self.info.insert("end", "- /NeedAppearances is enabled for better viewer rendering.\n")


if __name__ == "__main__":
    app = DesignerApp()
    app.mainloop()