import unittest

from app.services.translation_links import google_translate_language_code


class TranslationLinkLanguageCodeTestCase(unittest.TestCase):
    def test_normalizes_workbook_aliases_for_google_translate(self):
        self.assertEqual(google_translate_language_code("pu"), "pa")
        self.assertEqual(google_translate_language_code("gj"), "gu")
        self.assertEqual(google_translate_language_code("asm"), "as")
        self.assertEqual(google_translate_language_code("od"), "or")

    def test_preserves_supported_codes(self):
        self.assertEqual(google_translate_language_code("hi"), "hi")
        self.assertEqual(google_translate_language_code("ta"), "ta")


if __name__ == "__main__":
    unittest.main()
