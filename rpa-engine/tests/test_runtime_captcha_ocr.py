from nodeskclaw_rpa_engine.runtime.captcha_ocr import parse_ocr_prediction, recognize_captcha
from nodeskclaw_rpa_engine.runtime.official_srm_login import is_captcha_error


class FakeClassifier:
    def __init__(self, prediction):
        self.prediction = prediction

    def classification(self, image, probability=False):
        self.image = image
        self.probability = probability
        return self.prediction


def test_string_prediction_accepted():
    result = parse_ocr_prediction("Mp3S")
    assert result.text == "mp3s"
    assert result.accepted is True


def test_probability_rows():
    result = parse_ocr_prediction(
        {
            "charsets": ["m", "p", "3", "s", "x"],
            "probability": [
                [0.9, 0.1, 0.0, 0.0, 0.0],
                [0.1, 0.8, 0.1, 0.0, 0.0],
                [0.0, 0.0, 0.95, 0.05, 0.0],
                [0.0, 0.0, 0.0, 0.99, 0.01],
            ],
        }
    )
    assert result.text == "mp3s"
    assert result.accepted is True


def test_rejects_short_text():
    result = parse_ocr_prediction("ab")
    assert result.accepted is False
    assert result.rejection_reason == "OCR_LENGTH_INVALID"


def test_recognize_uses_injected_classifier():
    result = recognize_captcha(b"image", FakeClassifier("Ab12"))
    assert result.text == "ab12"
    assert result.accepted is True


def test_captcha_error_detects_chinese():
    assert is_captcha_error("验证码错误") is True
    assert is_captcha_error("账号或密码错误") is False


def test_ddddocr_v16_dict():
    result = parse_ocr_prediction(
        {
            "text": "Mp3S",
            "confidence": 0.99,
            "charset": ["m", "p"],
            "probabilities": [],
        }
    )
    assert result.text == "mp3s"
    assert result.accepted is True
