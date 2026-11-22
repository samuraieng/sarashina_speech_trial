import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# srcディレクトリをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from sara_ttsph1 import extract_text_from_url, is_japanese, sanitize_for_tts

class TestSaraTTSPh1(unittest.TestCase):

    def test_sanitize_for_tts(self):
        text = 'こんにちは"世界" “テスト”'
        sanitized = sanitize_for_tts(text)
        self.assertNotIn('"', sanitized)
        self.assertNotIn('“', sanitized)
        self.assertNotIn('”', sanitized)
        self.assertEqual(sanitized, 'こんにちは世界 テスト')

    def test_is_japanese(self):
        self.assertTrue(is_japanese("こんにちは、世界"))
        self.assertTrue(is_japanese("おはようございます。7時です。"))
        self.assertFalse(is_japanese("Hello, world! Good morning."))
        self.assertFalse(is_japanese("1234567890"))

    @patch('sara_ttsph1.requests.get')
    def test_extract_text_from_url(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "<html><body><script>var x = 1;</script><p>Hello Sarashina TTS</p><footer>Footer info</footer></body></html>"
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        text = extract_text_from_url("https://example.com")
        self.assertIn("Hello Sarashina TTS", text)
        self.assertNotIn("var x = 1", text)
        self.assertNotIn("Footer info", text)

if __name__ == '__main__':
    unittest.main()
