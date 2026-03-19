import os
import queue
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from processing.exif_reader import get_capture_date
from processing.date_stamp import stamp_file

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".heic", ".heif"}


@dataclass
class BatchConfig:
    input_folder: str
    output_folder: str
    format_str: str
    position: str
    font_size_pct: float
    color: tuple[int, int, int]
    padding_pct: float = 3.0
    outline_px: int = 3
    fallback_date: datetime | None = None
    unstamped_folder: str | None = None


@dataclass
class BatchResult:
    path: str
    success: bool
    error: str | None = None


def collect_images(folder: str) -> list[str]:
    images = []
    for root, _, files in os.walk(folder):
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS:
                images.append(os.path.join(root, name))
    return images


def _copy_to_unstamped(input_path: str, unstamped_path: str) -> None:
    dest_dir = os.path.dirname(unstamped_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)
    shutil.copy2(input_path, unstamped_path)


def _process_one(input_path: str, output_path: str, unstamped_path: str | None, config: BatchConfig) -> BatchResult:
    date = get_capture_date(input_path)
    if date is None:
        if config.fallback_date is not None:
            date = config.fallback_date
        else:
            if unstamped_path:
                _copy_to_unstamped(input_path, unstamped_path)
            return BatchResult(input_path, False, "No EXIF date (skipped)")

    date_str = date.strftime(config.format_str)

    try:
        stamp_file(input_path, output_path, date_str, config.position, config.font_size_pct, config.color, config.padding_pct, config.outline_px)
        return BatchResult(input_path, True)
    except Exception as exc:
        if unstamped_path:
            _copy_to_unstamped(input_path, unstamped_path)
        return BatchResult(input_path, False, str(exc))


def run_batch(
    config: BatchConfig,
    progress_queue: queue.Queue,
    cancel_event: threading.Event,
) -> None:
    """
    Process all images in config.input_folder.
    Puts BatchResult objects into progress_queue as work completes.
    Puts None when finished (sentinel).
    """
    images = collect_images(config.input_folder)

    work: list[tuple[str, str, str | None]] = []
    for img_path in images:
        rel = os.path.relpath(img_path, config.input_folder)
        out_path = os.path.join(config.output_folder, rel)
        unstamped_path = os.path.join(config.unstamped_folder, rel) if config.unstamped_folder else None
        work.append((img_path, out_path, unstamped_path))

    progress_queue.put(("total", len(work)))

    max_workers = min(4, os.cpu_count() or 1)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_one, inp, out, unstamped, config): inp
            for inp, out, unstamped in work
        }
        for future in as_completed(futures):
            if cancel_event.is_set():
                for f in futures:
                    f.cancel()
                break
            result = future.result()
            progress_queue.put(("result", result))

    progress_queue.put(("done", None))
