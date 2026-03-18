from datetime import datetime
from PIL import Image

# DateTimeOriginal and DateTimeDigitized live in the ExifIFD sub-table (0x8769).
# DateTime (306) is in the main IFD but reflects last-modified time, so it is excluded.
_EXIF_IFD_TAG = 0x8769
_DATE_TAGS = [
    36867,  # DateTimeOriginal
    36868,  # DateTimeDigitized
]
_DATE_FMT = "%Y:%m:%d %H:%M:%S"


def get_capture_date(path: str) -> datetime | None:
    """Return the capture datetime from EXIF, or None if unavailable."""
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None
            exif_ifd = exif.get_ifd(_EXIF_IFD_TAG)
            for tag in _DATE_TAGS:
                val = exif_ifd.get(tag)
                if val:
                    try:
                        return datetime.strptime(val.strip(), _DATE_FMT)
                    except ValueError:
                        continue
    except Exception:
        pass
    return None
