import tkinter as tk
from datetime import datetime
from PIL import Image, ImageOps, ImageTk

from processing.date_stamp import apply_stamp
from processing.exif_reader import get_capture_date

_DEBOUNCE_MS = 120


class PreviewPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._tk_image = None
        self._after_id = None
        self._last_args: tuple | None = None

        tk.Label(self, text="Preview", anchor="w").pack(fill=tk.X)
        self._canvas = tk.Canvas(self, bg="#1e1e1e")
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._canvas.bind("<Configure>", self._on_resize)

    def update(
        self,
        path: str,
        date_str: str,
        position: str,
        font_size_pct: float,
        color: tuple[int, int, int],
        padding_pct: float = 3.0,
        outline_px: int = 3,
    ) -> None:
        self._last_args = (path, date_str, position, font_size_pct, color, padding_pct, outline_px)
        self._schedule_redraw()

    def _on_resize(self, _event):
        self._schedule_redraw()

    def _schedule_redraw(self):
        if self._after_id is not None:
            self.after_cancel(self._after_id)
        self._after_id = self.after(_DEBOUNCE_MS, self._redraw)

    def _redraw(self):
        self._after_id = None
        if self._last_args is None:
            return

        path, date_str, position, font_size_pct, color, padding_pct, outline_px = self._last_args
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        try:
            with Image.open(path) as src:
                img = ImageOps.exif_transpose(src)

            orig_w, orig_h = img.size

            # Scale to fit canvas
            scale = min(cw / orig_w, ch / orig_h)
            new_w = max(1, int(orig_w * scale))
            new_h = max(1, int(orig_h * scale))
            img = img.resize((new_w, new_h), Image.LANCZOS)

            stamped = apply_stamp(img, date_str, position, font_size_pct, color, padding_pct, outline_px)

            self._tk_image = ImageTk.PhotoImage(stamped)
            self._canvas.delete("all")
            self._canvas.create_image(cw // 2, ch // 2, anchor="center", image=self._tk_image)

        except Exception as exc:
            self._canvas.delete("all")
            self._canvas.create_text(
                cw // 2, ch // 2,
                text=f"Preview unavailable\n{exc}",
                fill="#ff6666",
                justify="center",
            )
