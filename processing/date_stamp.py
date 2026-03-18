import os
import sys
from PIL import Image, ImageDraw, ImageFont, ImageOps

POSITIONS = [
    "Bottom Right",
    "Bottom Left",
    "Top Right",
    "Top Left",
]


def _find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Find a usable TrueType font, falling back to Pillow's built-in."""
    # Check for a font bundled with the app (or dropped in by the user)
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(__file__)))
    bundled = os.path.join(base, "fonts")
    if os.path.isdir(bundled):
        for name in os.listdir(bundled):
            if name.lower().endswith(".ttf"):
                try:
                    return ImageFont.truetype(os.path.join(bundled, name), size)
                except Exception:
                    pass

    # System font candidates
    if sys.platform == "win32":
        candidates = [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\calibri.ttf",
            r"C:\Windows\Fonts\verdana.ttf",
        ]
    elif sys.platform == "darwin":
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass

    return ImageFont.load_default(size=size)


def _compute_xy(
    img_size: tuple[int, int],
    text_size: tuple[int, int],
    position: str,
    padding: int,
) -> tuple[int, int]:
    iw, ih = img_size
    tw, th = text_size
    if position == "Bottom Right":
        return iw - tw - padding, ih - th - padding
    elif position == "Bottom Left":
        return padding, ih - th - padding
    elif position == "Top Right":
        return iw - tw - padding, padding
    elif position == "Top Left":
        return padding, padding
    # default: bottom right
    return iw - tw - padding, ih - th - padding


def apply_stamp(
    img: Image.Image,
    date_str: str,
    position: str,
    font_size_pct: float,
    color: tuple[int, int, int],
    padding_pct: float = 3.0,
    outline_px: int = 3,
) -> Image.Image:
    """Return a new image with the date string stamped on it."""
    out = img.copy()
    if out.mode not in ("RGB", "RGBA", "L"):
        out = out.convert("RGB")

    short_side = min(out.size)
    font_size = max(1, int(short_side * font_size_pct / 100))
    padding = int(short_side * padding_pct / 100)

    draw = ImageDraw.Draw(out)
    font = _find_font(font_size)

    bbox = draw.textbbox((0, 0), date_str, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    x, y = _compute_xy(out.size, (text_w, text_h), position, padding)

    # Outline for readability on any background
    shadow = (0, 0, 0) if (color[0] + color[1] + color[2]) > 382 else (255, 255, 255)
    if outline_px > 0:
        for dx in range(-outline_px, outline_px + 1):
            for dy in range(-outline_px, outline_px + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), date_str, font=font, fill=shadow)

    draw.text((x, y), date_str, font=font, fill=color)
    return out


def stamp_file(
    input_path: str,
    output_path: str,
    date_str: str,
    position: str,
    font_size_pct: float,
    color: tuple[int, int, int],
    padding_pct: float = 3.0,
    outline_px: int = 3,
) -> None:
    """Read image from input_path, stamp it, write to output_path."""
    with Image.open(input_path) as src:
        save_format = src.format or "JPEG"
        img = ImageOps.exif_transpose(src)

    # exif_transpose resets orientation to 1; grab the updated bytes from the new image
    exif_bytes = img.info.get("exif", b"")

    if save_format in ("JPEG", "JPG") and img.mode != "RGB":
        img = img.convert("RGB")

    stamped = apply_stamp(img, date_str, position, font_size_pct, color, padding_pct, outline_px)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    save_kwargs: dict = {}
    if exif_bytes:
        save_kwargs["exif"] = exif_bytes
    if save_format in ("JPEG", "JPG"):
        save_kwargs["quality"] = 95
        save_kwargs["subsampling"] = 0

    stamped.save(output_path, format=save_format, **save_kwargs)
