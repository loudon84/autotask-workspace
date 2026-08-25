"""Benchmark local OCR on demo portal captcha PNGs. Does not use filename mapping."""

from __future__ import annotations

import json
from pathlib import Path

from nodeskclaw_rpa_engine.runtime.captcha_ocr import get_classifier, parse_ocr_prediction, recognize_captcha

ROOT = Path(r"d:\work_space260811\autotask-workspace\rpa-engine\runtime-cache\demo-captcha")
EXPECTED = {
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


def main() -> None:
    classifier = get_classifier()
    sample = (ROOT / "code01.png").read_bytes()
    raw = classifier.classification(sample, probability=True)
    print("raw_type", type(raw).__name__)
    if isinstance(raw, dict):
        print("raw_keys", sorted(raw.keys()))
        preview = {key: (type(value).__name__, str(value)[:80]) for key, value in raw.items()}
        print("raw_preview", json.dumps(preview, ensure_ascii=False))
    else:
        print("raw_str_len", len(str(raw)))

    hits = 0
    rows = []
    for stem, expected in EXPECTED.items():
        image = (ROOT / f"{stem}.png").read_bytes()
        as_str = parse_ocr_prediction(classifier.classification(image))
        as_prob = recognize_captcha(image, classifier)
        match = as_str.text == expected
        hits += int(match)
        rows.append(
            {
                "file": stem,
                "expected": expected,
                "ocr_str": as_str.text,
                "ocr_prob": as_prob.text,
                "accepted": as_prob.accepted,
                "reason": as_prob.rejection_reason,
                "match": match,
            }
        )
        print(
            stem,
            "expected",
            expected,
            "ocr",
            as_str.text,
            "prob",
            as_prob.text,
            "ok" if match else "MISS",
        )
    print(f"exact {hits}/10")


if __name__ == "__main__":
    main()
