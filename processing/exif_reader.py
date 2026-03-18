from datetime import datetime
from PIL import Image

# Priority order for EXIF date tags
_DATE_TAGS = [
    36867,  # DateTimeOriginal
    36868,  # DateTimeDigitized
    306,    # DateTime
]
_DATE_FMT = "%Y:%m:%d %H:%M:%S"


def get_capture_date(path: str) -> datetime | None:
    """Return the capture datetime from EXIF, or None if unavailable."""
    try:
        with Image.open(path) as img:
            exif = img._getexif()
            if not exif:
                return None
            for tag in _DATE_TAGS:
                val = exif.get(tag)
                if val:
                    try:
                        return datetime.strptime(val.strip(), _DATE_FMT)
                    except ValueError:
                        continue
    except Exception:
        pass
    return None
