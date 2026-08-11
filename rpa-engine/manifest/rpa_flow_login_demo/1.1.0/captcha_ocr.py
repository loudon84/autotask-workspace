from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Any, Protocol


CAPTCHA_LENGTH = 4
MIN_CONFIDENCE = 0.90
NON_ALPHANUMERIC = re.compile(r"[^0-9a-z]")


class OcrClassifier(Protocol):
    def classification(
        self, image: bytes, probability: bool = False
    ) -> dict[str, Any] | str: ...


@dataclass(frozen=True)
class CaptchaOcrResult:
    text: str
    confidence: float
    accepted: bool
    rejection_reason: str | None = None


@lru_cache(maxsize=1)
def get_classifier() -> OcrClassifier:
    import ddddocr

    return ddddocr.DdddOcr(show_ad=False)


def normalize_captcha_text(value: str) -> str:
    return NON_ALPHANUMERIC.sub("", value.lower())


def recognize_captcha(
    image: bytes, classifier: OcrClassifier | None = None
) -> CaptchaOcrResult:
    if not image:
        raise ValueError("Captcha image is empty")

    engine = classifier or get_classifier()
    prediction = engine.classification(image, probability=True)
    if not isinstance(prediction, dict):
        return CaptchaOcrResult("", 0.0, False, "OCR_RESULT_INVALID")

    text = normalize_captcha_text(str(prediction.get("text", "")))
    confidence = float(prediction.get("confidence", 0.0))
    if len(text) != CAPTCHA_LENGTH:
        return CaptchaOcrResult(text, confidence, False, "OCR_LENGTH_INVALID")
    if confidence < MIN_CONFIDENCE:
        return CaptchaOcrResult(text, confidence, False, "OCR_CONFIDENCE_LOW")

    return CaptchaOcrResult(text, confidence, True)
