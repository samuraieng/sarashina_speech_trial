import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import wave
import tempfile

# srcディレクトリをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

os.environ.setdefault("SARASHINA_API_KEY", "dummy_key")

class TestSaraLLMPh1(unittest.TestCase):

    @patch('sara_llmph1.requests.post')
    def test_main_pipeline_ja_with_llm(self, mock_post):
        mock_asr_response = MagicMock()
        mock_asr_response.status_code = 200
        mock_asr_response.text = "こんにちは"

        mock_llm_response = MagicMock()
        mock_llm_response.status_code = 200
        mock_llm_response.json.return_value = {
            "choices": [{"message": {"content": "日本の伝統的な挨拶ですね。"}}]
        }

        mock_tts_response = MagicMock()
        mock_tts_response.status_code = 200
        mock_tts_response.content = b"RIFF....WAVE..."

        mock_post.side_effect = [mock_asr_response, mock_llm_response, mock_tts_response]

        temp_fd, temp_input = tempfile.mkstemp(suffix=".wav")
        os.close(temp_fd)
        temp_fd2, temp_output = tempfile.mkstemp(suffix=".wav")
        os.close(temp_fd2)

        try:
            with wave.open(temp_input, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b'\x00\x00' * 160)

            from sara_llmph1 import main
            test_args = ["sara_llmph1.py", "--input", temp_input, "--output", temp_output, "--lang", "ja", "--llm"]
            with patch.object(sys, 'argv', test_args):
                main()

            self.assertEqual(mock_post.call_count, 3)
        finally:
            if os.path.exists(temp_input):
                os.remove(temp_input)
            if os.path.exists(temp_output):
                os.remove(temp_output)

    @patch('sara_llmph1.requests.post')
    def test_main_pipeline_no_llm(self, mock_post):
        mock_asr_response = MagicMock()
        mock_asr_response.status_code = 200
        mock_asr_response.text = "こんにちは"

        mock_tts_response = MagicMock()
        mock_tts_response.status_code = 200
        mock_tts_response.content = b"RIFF....WAVE..."

        mock_post.side_effect = [mock_asr_response, mock_tts_response]

        temp_fd, temp_input = tempfile.mkstemp(suffix=".wav")
        os.close(temp_fd)
        temp_fd2, temp_output = tempfile.mkstemp(suffix=".wav")
        os.close(temp_fd2)

        try:
            with wave.open(temp_input, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b'\x00\x00' * 160)

            from sara_llmph1 import main
            test_args = ["sara_llmph1.py", "--input", temp_input, "--output", temp_output, "--lang", "ja"]
            with patch.object(sys, 'argv', test_args):
                main()

            self.assertEqual(mock_post.call_count, 2)
        finally:
            if os.path.exists(temp_input):
                os.remove(temp_input)
            if os.path.exists(temp_output):
                os.remove(temp_output)

if __name__ == '__main__':
    unittest.main()
