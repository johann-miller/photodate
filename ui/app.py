import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import colorchooser, filedialog, messagebox, ttk

from processing.batch import BatchConfig, BatchResult, collect_images, run_batch
from processing.date_stamp import POSITIONS
from processing.exif_reader import get_capture_date
from ui.preview import PreviewPanel

_POLL_MS = 50  # progress queue poll interval

_FORMAT_PRESETS = [
    ("%Y-%m-%d",      "2026-03-18"),
    ("%d/%m/%Y",      "18/03/2026"),
    ("%m/%d/%Y",      "03/18/2026"),
    ("%Y-%m-%d %H:%M", "2026-03-18 14:30"),
    ("%B %d, %Y",     "March 18, 2026"),
]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("photodate")
        self.minsize(920, 560)

        self._color: tuple[int, int, int] = (255, 255, 255)
        self._cancel_event = threading.Event()
        self._progress_queue: queue.Queue = queue.Queue()
        self._batch_total = 0
        self._batch_done = 0
        self._batch_ok = 0
        self._batch_fail = 0
        self._batch_running = False

        self._build_ui()

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        main = tk.Frame(self, padx=8, pady=8)
        main.pack(fill=tk.BOTH, expand=True)

        top = tk.Frame(main)
        top.pack(fill=tk.BOTH, expand=True)

        settings = ttk.LabelFrame(top, text="Settings", padding=10)
        settings.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        self._build_settings(settings)

        self._preview = PreviewPanel(top)
        self._preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Separator(main, orient="horizontal").pack(fill=tk.X, pady=8)
        self._build_bottom(main)

    def _build_settings(self, f):
        r = 0

        # Input folder
        ttk.Label(f, text="Input folder:").grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        self._input_var = tk.StringVar()
        ttk.Entry(f, textvariable=self._input_var, width=26).grid(row=r, column=0, sticky="ew")
        ttk.Button(f, text="…", width=2, command=self._browse_input).grid(row=r, column=1, padx=(4, 0))
        r += 1

        # Output folder
        ttk.Label(f, text="Output folder:").grid(row=r, column=0, columnspan=2, sticky="w", pady=(6, 0))
        r += 1
        self._output_var = tk.StringVar()
        ttk.Entry(f, textvariable=self._output_var, width=26).grid(row=r, column=0, sticky="ew")
        ttk.Button(f, text="…", width=2, command=self._browse_output).grid(row=r, column=1, padx=(4, 0))
        r += 1

        ttk.Separator(f, orient="horizontal").grid(row=r, column=0, columnspan=2, sticky="ew", pady=8)
        r += 1

        # Date format
        ttk.Label(f, text="Date/time format:").grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        self._format_var = tk.StringVar(value="%Y-%m-%d")
        self._format_var.trace_add("write", lambda *_: self._refresh_preview())
        ttk.Entry(f, textvariable=self._format_var, width=22).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1

        presets_frame = ttk.LabelFrame(f, text="Presets", padding=4)
        presets_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        for fmt, label in _FORMAT_PRESETS:
            ttk.Button(
                presets_frame, text=label,
                command=lambda v=fmt: self._set_format(v),
            ).pack(fill="x", anchor="w")
        r += 1

        ttk.Separator(f, orient="horizontal").grid(row=r, column=0, columnspan=2, sticky="ew", pady=8)
        r += 1

        # Position
        ttk.Label(f, text="Position:").grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        self._pos_var = tk.StringVar(value=POSITIONS[0])
        pos = ttk.Combobox(f, textvariable=self._pos_var, values=POSITIONS, state="readonly", width=18)
        pos.grid(row=r, column=0, columnspan=2, sticky="w")
        pos.bind("<<ComboboxSelected>>", lambda _: self._refresh_preview())
        r += 1

        # Font size
        ttk.Label(f, text="Font size:").grid(row=r, column=0, columnspan=2, sticky="w", pady=(6, 0))
        r += 1
        self._size_var = tk.IntVar(value=48)
        sz = ttk.Spinbox(f, from_=8, to=500, textvariable=self._size_var, width=8,
                         command=self._refresh_preview)
        sz.grid(row=r, column=0, columnspan=2, sticky="w")
        self._size_var.trace_add("write", lambda *_: self._refresh_preview())
        r += 1

        # Color
        ttk.Label(f, text="Text color:").grid(row=r, column=0, columnspan=2, sticky="w", pady=(6, 0))
        r += 1
        color_row = tk.Frame(f)
        color_row.grid(row=r, column=0, columnspan=2, sticky="w")
        self._swatch = tk.Label(color_row, bg="#ffffff", width=3, relief="raised")
        self._swatch.pack(side=tk.LEFT)
        ttk.Button(color_row, text="Pick…", command=self._pick_color).pack(side=tk.LEFT, padx=(6, 0))
        r += 1

        ttk.Separator(f, orient="horizontal").grid(row=r, column=0, columnspan=2, sticky="ew", pady=8)
        r += 1

        # Fallback date
        ttk.Label(f, text="Fallback date (no EXIF):").grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        self._fallback_var = tk.StringVar()
        ttk.Entry(f, textvariable=self._fallback_var, width=14).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        ttk.Label(f, text="YYYY-MM-DD  (blank = skip)", foreground="gray").grid(
            row=r, column=0, columnspan=2, sticky="w")
        r += 1

        ttk.Separator(f, orient="horizontal").grid(row=r, column=0, columnspan=2, sticky="ew", pady=8)
        r += 1

        # Preview photo
        ttk.Label(f, text="Preview photo:").grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        self._prev_var = tk.StringVar()
        ttk.Entry(f, textvariable=self._prev_var, width=26).grid(row=r, column=0, sticky="ew")
        ttk.Button(f, text="…", width=2, command=self._browse_preview).grid(row=r, column=1, padx=(4, 0))

    def _build_bottom(self, parent):
        self._progress_var = tk.DoubleVar()
        ttk.Progressbar(parent, variable=self._progress_var, maximum=100).pack(fill=tk.X)

        btns = tk.Frame(parent)
        btns.pack(fill=tk.X, pady=(6, 0))

        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(btns, textvariable=self._status_var).pack(side=tk.LEFT)

        self._cancel_btn = ttk.Button(btns, text="Cancel", state="disabled", command=self._cancel)
        self._cancel_btn.pack(side=tk.RIGHT, padx=(4, 0))
        self._start_btn = ttk.Button(btns, text="Start", command=self._start)
        self._start_btn.pack(side=tk.RIGHT)

    # --------------------------------------------------------------- actions

    def _browse_input(self):
        d = filedialog.askdirectory(title="Select input folder")
        if not d:
            return
        self._input_var.set(d)
        if not self._output_var.get():
            self._output_var.set(d.rstrip("/\\") + "_stamped")
        if not self._prev_var.get():
            imgs = collect_images(d)
            if imgs:
                self._prev_var.set(imgs[0])
                self._refresh_preview()

    def _browse_output(self):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self._output_var.set(d)

    def _browse_preview(self):
        p = filedialog.askopenfilename(
            title="Select preview photo",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.tiff *.tif"), ("All files", "*.*")],
        )
        if p:
            self._prev_var.set(p)
            self._refresh_preview()

    def _set_format(self, fmt: str):
        self._format_var.set(fmt)

    def _pick_color(self):
        init = "#{:02x}{:02x}{:02x}".format(*self._color)
        result = colorchooser.askcolor(color=init, title="Choose text color")
        if result and result[0]:
            r, g, b = (int(c) for c in result[0])
            self._color = (r, g, b)
            self._swatch.config(bg=result[1])
            self._refresh_preview()

    def _refresh_preview(self):
        path = self._prev_var.get()
        if not path or not os.path.isfile(path):
            return
        try:
            font_size = self._size_var.get()
        except tk.TclError:
            return

        date = get_capture_date(path) or datetime.now()
        try:
            date_str = date.strftime(self._format_var.get())
        except ValueError:
            date_str = str(date)

        self._preview.update(path, date_str, self._pos_var.get(), font_size, self._color)

    def _start(self):
        inp = self._input_var.get().strip()
        out = self._output_var.get().strip()

        if not inp or not os.path.isdir(inp):
            messagebox.showerror("Error", "Select a valid input folder.")
            return
        if not out:
            messagebox.showerror("Error", "Select an output folder.")
            return
        if os.path.abspath(inp) == os.path.abspath(out):
            messagebox.showerror(
                "Error",
                "Output folder must be different from input folder.\n"
                "Overwriting originals is not allowed.",
            )
            return

        fallback: datetime | None = None
        fb_str = self._fallback_var.get().strip()
        if fb_str:
            try:
                fallback = datetime.strptime(fb_str, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Fallback date must be in YYYY-MM-DD format.")
                return

        # Validate format string
        try:
            datetime.now().strftime(self._format_var.get())
        except ValueError as exc:
            messagebox.showerror("Error", f"Invalid date format: {exc}")
            return

        config = BatchConfig(
            input_folder=inp,
            output_folder=out,
            format_str=self._format_var.get(),
            position=self._pos_var.get(),
            font_size=self._size_var.get(),
            color=self._color,
            fallback_date=fallback,
        )

        self._cancel_event.clear()
        self._batch_total = 0
        self._batch_done = 0
        self._batch_ok = 0
        self._batch_fail = 0
        self._batch_running = True

        self._start_btn.config(state="disabled")
        self._cancel_btn.config(state="normal")
        self._progress_var.set(0)
        self._status_var.set("Starting…")

        threading.Thread(
            target=run_batch,
            args=(config, self._progress_queue, self._cancel_event),
            daemon=True,
        ).start()

        self.after(_POLL_MS, self._poll_progress)

    def _poll_progress(self):
        try:
            while True:
                msg = self._progress_queue.get_nowait()
                kind, payload = msg

                if kind == "total":
                    self._batch_total = payload
                elif kind == "result":
                    result: BatchResult = payload
                    self._batch_done += 1
                    if result.success:
                        self._batch_ok += 1
                    else:
                        self._batch_fail += 1
                    pct = (self._batch_done / self._batch_total * 100) if self._batch_total else 0
                    self._progress_var.set(pct)
                    self._status_var.set(
                        f"{self._batch_done}/{self._batch_total}  —  {os.path.basename(result.path)}"
                    )
                elif kind == "done":
                    self._on_batch_done()
                    return
        except queue.Empty:
            pass

        if self._batch_running:
            self.after(_POLL_MS, self._poll_progress)

    def _on_batch_done(self):
        self._batch_running = False
        self._start_btn.config(state="normal")
        self._cancel_btn.config(state="disabled")

        ok, fail = self._batch_ok, self._batch_fail
        if self._cancel_event.is_set():
            self._status_var.set(f"Cancelled — {ok} done, {fail} skipped/failed")
        else:
            self._progress_var.set(100)
            self._status_var.set(f"Done — {ok} succeeded, {fail} skipped/failed")
            if fail == 0:
                messagebox.showinfo("Done", f"{ok} photos processed successfully.")
            else:
                messagebox.showwarning(
                    "Done", f"{ok} succeeded, {fail} skipped or failed\n(no EXIF date or processing error)."
                )

    def _cancel(self):
        self._cancel_event.set()
        self._status_var.set("Cancelling…")
