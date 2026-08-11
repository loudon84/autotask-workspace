import unittest

from captcha_adapter import resolve_demo_captcha


class ResolveDemoCaptchaTests(unittest.TestCase):
    def test_resolves_relative_image_path(self):
        self.assertEqual(resolve_demo_captcha("/verify-code/code01.png"), "mp3s")

    def test_resolves_absolute_image_url_with_query(self):
        self.assertEqual(
            resolve_demo_captcha("https://portal.test/code10.png?v=3"), "gqcy"
        )

    def test_rejects_unknown_or_missing_image(self):
        self.assertIsNone(resolve_demo_captcha("/captcha/random.png"))
        self.assertIsNone(resolve_demo_captcha(None))


if __name__ == "__main__":
    unittest.main()
