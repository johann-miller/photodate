# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`photodate` is a local desktop application that stamps date/time text onto photos in bulk (1,000–2,000 photos). It targets Windows and Linux, is packaged with PyInstaller, and has no web component.

## Setup and running

```bash
pip install -r requirements.txt
python main.py
```

## Architecture

```
main.py                  # entry point; freeze_support guard for PyInstaller
processing/
  exif_reader.py         # reads capture datetime from EXIF (priority: DateTimeOriginal > DateTimeDigitized > DateTime)
  date_stamp.py          # POSITIONS constant; apply_stamp() returns a new PIL Image; stamp_file() for batch I/O
  batch.py               # ThreadPoolExecutor runner; puts BatchResult objects into a queue.Queue; sentinel None on done
ui/
  preview.py             # Tkinter Canvas with 120ms debounce on resize; scales font proportionally to preview size
  app.py                 # main window; polls progress_queue every 50ms with after(); pre-flight validation before batch
```

## Key module contracts

- `apply_stamp(img, date_str, position, font_size, color) -> Image` — takes a pre-formatted string, returns a **new** image (does not mutate the input). Used by both the preview and batch path.
- `stamp_file(input_path, output_path, date_str, ...)` — file-based wrapper; preserves original EXIF bytes and JPEG quality.
- `POSITIONS` in `date_stamp.py` is the single source of truth for position strings — imported by `app.py` to populate the dropdown.
- Batch progress is communicated via `queue.Queue` with typed tuples: `("total", int)`, `("result", BatchResult)`, `("done", None)`. Never use `self.after(0, callback)` in a tight loop from the batch thread.
- `cancel_event` (threading.Event) is checked before each `img.save()` call in the batch worker, not just at the top of the loop.

## Fonts

Place any `.ttf` file in a `fonts/` directory next to `main.py` to use it for stamping. Without a bundled font, the app falls back to common system fonts, then to Pillow's built-in bitmap font. For PyInstaller builds, fonts in `fonts/` are resolved via `sys._MEIPASS`.
