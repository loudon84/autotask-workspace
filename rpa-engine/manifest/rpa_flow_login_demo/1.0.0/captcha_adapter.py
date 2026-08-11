from pathlib import PurePosixPath
from urllib.parse import urlparse


CAPTCHA_CODES = {
    "code01": "mp3s",
    "code02": "0ada",
    "code03": "sez0",
    "code04": "ggmh",
    "code05": "rpyt",
    "code06": "y5na",
    "code07": "elhx",
    "code08": "el0m",
    "code09": "aqh9",
    "code10": "gqcy",
}


def resolve_demo_captcha(src: str | None) -> str | None:
    """Resolve only the fixed captcha images supplied by the mock SRM portal."""
    if not src:
        return None

    image_key = PurePosixPath(urlparse(src).path).stem.lower()
    return CAPTCHA_CODES.get(image_key)
