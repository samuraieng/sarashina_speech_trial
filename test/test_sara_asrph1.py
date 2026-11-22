import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import wave
import tempfile

# srcディレクトリをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

os.environ.setdefault("SARASHINA_API_KEY", "dummy_key")

from sara_asrph1 import main

class TestSaraASRPh1(unittest.TestCase):

    def _create_wav(self, path):
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b'\x00\x00' * 160)

    @patch('sara_asrph1.requests.post')
    def test_main_pipeline(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "こんにちは"
        mock_post.return_value = mock_response

        temp_fd, temp_input = tempfile.mkstemp(suffix=".wav")
        os.close(temp_fd)
        temp_fd2, temp_output = tempfile.mkstemp(suffix=".txt")
        os.close(temp_fd2)

        try:
            self._create_wav(temp_input)

            test_args = ["sara_asrph1.py", "--input", temp_input, "--output", temp_output]
            with patch.object(sys, 'argv', test_args):
                main()

            mock_post.assert_called_once()
            with open(temp_output, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "こんにちは")
        finally:
            if os.path.exists(temp_input):
                os.remove(temp_input)
            if os.path.exists(temp_output):
                os.remove(temp_output)

    @patch('sara_asrph1.requests.post')
    def test_main_pipeline_with_keyword_file(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Sarashina の音声認識です"
        mock_post.return_value = mock_response

        temp_fd, temp_input = tempfile.mkstemp(suffix=".wav")
        os.close(temp_fd)
        temp_fd2, temp_output = tempfile.mkstemp(suffix=".txt")
        os.close(temp_fd2)
        temp_fd3, temp_keyword = tempfile.mkstemp(suffix=".txt")
        os.close(temp_fd3)

        try:
            self._create_wav(temp_input)
            with open(temp_keyword, "w", encoding="utf-8") as f:
                f.write('Sarashina\n音声認識')

            test_args = [
                "sara_asrph1.py",
                "--input", temp_input,
                "--output", temp_output,
                "--keyword", temp_keyword
            ]
            with patch.object(sys, 'argv', test_args):
                main()

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            self.assertIn("data", call_kwargs)
            self.assertEqual(call_kwargs["data"]["keywords"], 'Sarashina\n音声認識')
            with open(temp_output, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "Sarashina の音声認識です")
        finally:
            if os.path.exists(temp_input):
                os.remove(temp_input)
            if os.path.exists(temp_output):
                os.remove(temp_output)
            if os.path.exists(temp_keyword):
                os.remove(temp_keyword)

if __name__ == '__main__':
    unittest.main()
