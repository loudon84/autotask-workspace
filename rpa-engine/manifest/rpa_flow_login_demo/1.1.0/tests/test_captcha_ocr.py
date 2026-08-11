import unittest

from captcha_ocr import recognize_captcha


class FakeClassifier:
    def __init__(self, prediction):
        self.prediction = prediction

    def classification(self, image, probability=False):
        self.image = image
        self.probability = probability
        return self.prediction


class RecognizeCaptchaTests(unittest.TestCase):
    def test_normalizes_before_validating_length(self):
        classifier = FakeClassifier({"text": "A-q9!", "confidence": 0.98})

        result = recognize_captcha(b"image", classifier)

        self.assertEqual(result.text, "aq9")
        self.assertFalse(result.accepted)
        self.assertEqual(result.rejection_reason, "OCR_LENGTH_INVALID")
        self.assertTrue(classifier.probability)

    def test_accepts_a_valid_prediction(self):
        result = recognize_captcha(
            b"image", FakeClassifier({"text": "Mp3S", "confidence": 0.99})
        )

        self.assertEqual(result.text, "mp3s")
        self.assertTrue(result.accepted)
        self.assertIsNone(result.rejection_reason)

    def test_rejects_low_confidence(self):
        result = recognize_captcha(
            b"image", FakeClassifier({"text": "mp3s", "confidence": 0.42})
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.rejection_reason, "OCR_CONFIDENCE_LOW")

    def test_rejects_non_dictionary_result(self):
        result = recognize_captcha(b"image", FakeClassifier("mp3s"))

        self.assertFalse(result.accepted)
        self.assertEqual(result.rejection_reason, "OCR_RESULT_INVALID")

    def test_rejects_empty_image(self):
        with self.assertRaisesRegex(ValueError, "Captcha image is empty"):
            recognize_captcha(b"", FakeClassifier({}))


if __name__ == "__main__":
    unittest.main()
