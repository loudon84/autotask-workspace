"""Official-portal CAPTCHA OCR. Never log recognized text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

CAPTCHA_LENGTH = 4
NON_ALPHANUMERIC = re.compile(r"[^0-9a-z]")


class OcrClassifier(Protocol):
    def classification(
        self, image: bytes, probability: bool = False
    ) -> dict[str, Any] | str: ...


@dataclass(frozen=True, slots=True)
class CaptchaOcrResult:
    text: str
    confidence: float
    accepted: bool
    rejection_reason: str | None = None


@lru_cache(maxsize=1)
def get_classifier() -> OcrClassifier:
    try:
        import ddddocr
    except ImportError as exc:
        raise RuntimeError("CAPTCHA_OCR_UNAVAILABLE") from exc
    return ddddocr.DdddOcr(show_ad=False)


def normalize_captcha_text(value: str) -> str:
    return NON_ALPHANUMERIC.sub("", str(value or "").lower())


def _from_probability_rows(prediction: dict[str, Any]) -> tuple[str, float]:
    charsets = prediction.get("charset") or prediction.get("charsets") or []
    rows = prediction.get("probabilities") or prediction.get("probability") or []
    if not charsets or not rows:
        return "", 0.0
    chars: list[str] = []
    scores: list[float] = []
    for row in rows:
        if not row:
            continue
        index = max(range(len(row)), key=lambda i: float(row[i]))
        chars.append(str(charsets[index]))
        scores.append(float(row[index]))
    text = normalize_captcha_text("".join(chars))
    confidence = sum(scores) / len(scores) if scores else 0.0
    return text, confidence


def parse_ocr_prediction(prediction: dict[str, Any] | str) -> CaptchaOcrResult:
    if isinstance(prediction, str):
        text = normalize_captcha_text(prediction)
        if len(text) != CAPTCHA_LENGTH:
            return CaptchaOcrResult(text, 0.0, False, "OCR_LENGTH_INVALID")
        return CaptchaOcrResult(text, 1.0, True)
    if not isinstance(prediction, dict):
        return CaptchaOcrResult("", 0.0, False, "OCR_RESULT_INVALID")
    raw_text = prediction.get("text")
    if isinstance(raw_text, list):
        raw_text = "".join(str(part) for part in raw_text)
    if isinstance(raw_text, str) and raw_text.strip():
        text = normalize_captcha_text(raw_text)
        confidence = float(prediction.get("confidence") or 0.0)
    else:
        text, confidence = _from_probability_rows(prediction)
    if len(text) != CAPTCHA_LENGTH:
        return CaptchaOcrResult(text, confidence, False, "OCR_LENGTH_INVALID")
    return CaptchaOcrResult(text, confidence, True)


def recognize_captcha(
    image: bytes, classifier: OcrClassifier | None = None
) -> CaptchaOcrResult:
    if not image:
        raise ValueError("Captcha image is empty")
    engine = classifier or get_classifier()
    try:
        prediction = engine.classification(image, probability=True)
    except TypeError:
        prediction = engine.classification(image)
    return parse_ocr_prediction(prediction)
