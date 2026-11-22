#!/usr/bin/env python3
import os
import sys
import argparse
import requests
import wave
import audioop
import tempfile

ASR_API_URL = "https://api.sarashina.ai/v1/audio/transcriptions"

def ensure_16khz_wav(input_path):
    """
    input_pathのWAVファイルのサンプリングレートをチェックし、
    16000Hzでない場合は16000Hzにリサンプリングした一時ファイルを生成して返す。
    16000Hzの場合は元のパスをそのまま返す。
    """
    try:
        with wave.open(input_path, 'rb') as wf:
            framerate = wf.getframerate()
            nchannels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            nframes = wf.getnframes()
            frames = wf.readframes(nframes)
    except Exception as e:
        print(f"Error reading WAV file {input_path}: {e}", file=sys.stderr)
        sys.exit(1)

    if framerate == 16000:
        return input_path, None

    print(f"Input audio sample rate is {framerate}Hz. Converting to 16000Hz...")
    try:
        converted_frames, _ = audioop.ratecv(frames, sampwidth, nchannels, framerate, 16000, None)
    except Exception as e:
        print(f"Error during audio resampling: {e}", file=sys.stderr)
        sys.exit(1)

    temp_fd, temp_path = tempfile.mkstemp(suffix=".wav")
    os.close(temp_fd)

    with wave.open(temp_path, 'wb') as wf:
        wf.setnchannels(nchannels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(16000)
        wf.writeframes(converted_frames)

    return temp_path, temp_path

def main():
    parser = argparse.ArgumentParser(description="Sarashina ASR API client (Phase 1)")
    parser.add_argument(
        "--input",
        type=str,
        default="speech.wav",
        help="Input audio file path (WAV format)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="speech.txt",
        help="Output text file path"
    )
    parser.add_argument(
        "--keyword",
        type=str,
        default=None,
        help="Keyword / rule file path (optional). Contents are sent as the API 'keywords' parameter."
    )

    args = parser.parse_args()

    # 入力ファイルが存在するか確認
    if not os.path.exists(args.input):
        print(f"Error: Input audio file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # APIキーの確認
    api_key = os.getenv("SARASHINA_API_KEY")
    if not api_key:
        print("Error: SARASHINA_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    # サンプリングレート確認と16kHzへの変換
    target_input, temp_file_to_clean = ensure_16khz_wav(args.input)

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    print(f"Sending request to Sarashina ASR API (file={target_input}, model=sarashina3.2-asr)...")
    try:
        with open(target_input, "rb") as audio_file:
            files = {"file": (os.path.basename(target_input), audio_file, "audio/wav")}
            
            data = {
                "model": "sarashina3.2-asr",
                "response_format": "text"
            }
            if args.keyword:
                try:
                    with open(args.keyword, "r", encoding="utf-8") as kf:
                        keywords_content = kf.read().strip()
                    if keywords_content:
                        data["keywords"] = keywords_content
                except FileNotFoundError:
                    print(f"Error: Keyword file not found: {args.keyword}", file=sys.stderr)
                    sys.exit(1)
                except Exception as e:
                    print(f"Error reading keyword file {args.keyword}: {e}", file=sys.stderr)
                    sys.exit(1)

            response = requests.post(ASR_API_URL, headers=headers, files=files, data=data, timeout=60)

        if response.status_code != 200:
            print(f"ASR API Error [{response.status_code}]: {response.text}", file=sys.stderr)
            sys.exit(1)

        # テキスト結果の保存
        transcript = response.text
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(transcript)

        print(f"Successfully transcribed audio to text: {args.output}")

    except requests.exceptions.RequestException as e:
        print(f"Network error during ASR API request: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # 一時ファイルのクリーンアップ
        if temp_file_to_clean and os.path.exists(temp_file_to_clean):
            try:
                os.remove(temp_file_to_clean)
            except Exception:
                pass

if __name__ == "__main__":
    main()
