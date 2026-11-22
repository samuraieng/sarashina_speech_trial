#!/usr/bin/env python3
import os
import sys
import argparse
import requests
import wave
import audioop
import tempfile

ASR_API_URL = "https://api.sarashina.ai/v1/audio/transcriptions"
LLM_API_URL = "https://api.sarashina.ai/v1/chat/completions"

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
TRANSLATE_API_URL = "https://api.sarashina.ai/v1/translate"
TTS_API_URL = "https://api.sarashina.ai/v1/audio/speech"

def sanitize_for_tts(text):
    """
    TTS APIの仕様に基づき、未対応文字の置換・除去および文字数バリデーションを行う。
    - 下限: 2文字
    """
    if not text:
        return ""

    text = text.replace('—', 'ー').replace('–', '-').replace('＝', '=')
    text = text.replace('…', '...').replace('♪', '').replace('☆', '').replace('※', '')
    text = text.replace('"', '').replace('“', '').replace('”', '').replace('„', '').replace('‟', '')

    char_count = len(text)
    if char_count < 2:
        print(f"Error: Text length ({char_count} characters) is less than the minimum limit of 2 characters.", file=sys.stderr)
        sys.exit(1)

    return text


def split_text_into_chunks(text, target=650, window=10, hard_limit=700):
    """
    テキストを自然な区切り位置でチャンクに分割する。
    - 各区切り文字について、target ± window の範囲で最も後ろにある区切りを探す。
    - 見つからない場合は hard_limit まで遡って強制切断する。
    - 区切り文字自体は次のチャンクに含めない。
    区切り文字の優先順位:
      1. 改行
      2. 句点・ピリオド
      3. 読点・カンマ
      4. 半角・全角スペース
    """
    chunks = []
    separators = ["\n", "。", ".", "、", ",", " ", "　"]
    start = 0
    n = len(text)

    while start < n:
        if n - start <= hard_limit:
            chunks.append(text[start:])
            break

        end = -1
        low = max(start + 2, start + target - window)
        high = min(start + hard_limit, n)

        for sep in separators:
            idx = text.rfind(sep, low, high)
            if idx != -1:
                end = idx
                break

        if end == -1:
            end = min(start + hard_limit, n)

        chunks.append(text[start:end])
        next_start = end
        while next_start < n and text[next_start] in separators:
            next_start += 1
        if next_start == end:
            next_start = end
        start = next_start

    return chunks

def main():
    parser = argparse.ArgumentParser(description="Sarashina S2S-LLM pipeline (Phase 1)")
    parser.add_argument(
        "--input",
        type=str,
        default="speech.wav",
        help="Input Japanese audio file path (WAV format)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output.wav",
        help="Output audio file path (WAV or MP3)"
    )
    parser.add_argument(
        "--lang",
        type=str,
        choices=["ja", "en"],
        default="ja",
        help="Output language (ja or en)"
    )
    parser.add_argument(
        "--voice",
        type=str,
        default="ja_m_1",
        help="TTS voice type (ja_f_1, ja_f_2, ja_m_1)"
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Enable LLM processing (default: False, use ASR text directly)"
    )

    args = parser.parse_args()

    # 入力ファイル確認
    if not os.path.exists(args.input):
        print(f"Error: Input audio file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # APIキー確認
    api_key = os.getenv("SARASHINA_API_KEY")
    if not api_key:
        print("Error: SARASHINA_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 1. ASR (音声認識) 処理（16kHz変換を含む）
    target_input, temp_file_to_clean = ensure_16khz_wav(args.input)

    print(f"Running ASR on {target_input}...")
    try:
        with open(target_input, "rb") as audio_file:
            files = {"file": (os.path.basename(target_input), audio_file, "audio/wav")}
            data = {
                "model": "sarashina3.2-asr",
                "response_format": "text"
            }
            asr_headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.post(ASR_API_URL, headers=asr_headers, files=files, data=data, timeout=30)
            
            if response.status_code != 200:
                print(f"ASR API Error [{response.status_code}]: {response.text}", file=sys.stderr)
                sys.exit(1)
            
            # response_format=textの場合、レスポンスはプレーンテキスト
            recognized_text = response.text.strip()
            print(f"Recognized text (ASR): {recognized_text}")
    except Exception as e:
        print(f"Error calling ASR API: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # 一時ファイルのクリーンアップ
        if temp_file_to_clean and os.path.exists(temp_file_to_clean):
            try:
                os.remove(temp_file_to_clean)
            except Exception:
                pass

    if not recognized_text:
        print("Error: Recognized text is empty.", file=sys.stderr)
        sys.exit(1)

    # 2. LLM (思考・回答生成) 処理 (フラグ指定時のみ)
    answer_text = recognized_text
    if args.llm:
        print(f"Sending text to Sarashina LLM (sarashina3-nano)...")
        system_prompt = (
            "あなたは日本文化に長けています。入力されたことを、日本文化で解釈して、回答を用意してください。\n"
            "読みや補足が必要な漢字は、ひらがなやカタカナ表示でよい。\n"
            "読み上げ原稿として出力すること:\n"
            "- 「」や()は、重要ではない。\n"
            "- 補足なら、つまり、など接続語を用意して、繰り返すことは問題ない。\n"
            "- 意味がスムーズに通る構成にするほうが重要"
        )
        llm_payload = {
            "model": "sarashina3-nano",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": recognized_text}
            ]
        }

        try:
            llm_response = requests.post(LLM_API_URL, headers=headers, json=llm_payload, timeout=60)
            if llm_response.status_code != 200:
                print(f"LLM API Error [{llm_response.status_code}]: {llm_response.text}", file=sys.stderr)
                sys.exit(1)

            llm_json = llm_response.json()
            answer_text = llm_json["choices"][0]["message"]["content"].strip()
            print(f"LLM response text: {answer_text}")
        except Exception as e:
            print(f"Error calling LLM API: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("LLM flag not set. Using ASR text directly.")

    # 3. 翻訳処理 (lang == "en" の場合)
    final_text = answer_text
    if args.lang == "en":
        print("Translating response to English...")
        translate_payload = {
            "text": answer_text,
            "source_lang": "ja",
            "target_lang": "en",
            "style": "auto"
        }
        try:
            trans_response = requests.post(TRANSLATE_API_URL, headers=headers, json=translate_payload, timeout=30)
            if trans_response.status_code != 200:
                print(f"Translate API Error [{trans_response.status_code}]: {trans_response.text}", file=sys.stderr)
                sys.exit(1)
            trans_json = trans_response.json()
            # Translate APIのレスポンス構造に合わせて調整（通常 "translated_text" または "text" 等）
            final_text = trans_json.get("translated_text", trans_json.get("text", answer_text)).strip()
            print(f"Translated text (EN): {final_text}")
        except Exception as e:
            print(f"Error calling Translate API: {e}", file=sys.stderr)
            sys.exit(1)

    # 4. TTS (音声合成) 処理
    _, output_ext = os.path.splitext(args.output)
    response_format = "wav" if output_ext.lower() == ".wav" else "mp3"

    # TTS用に特殊文字等をサニタイジング
    final_text = sanitize_for_tts(final_text)

    # 700文字超過時は自然な区切りでチャンク分割
    text_chunks = split_text_into_chunks(final_text)
    print(f"Text split into {len(text_chunks)} chunk(s).")

    audio_segments = []
    for i, chunk in enumerate(text_chunks):
        tts_payload = {
            "model": "sarashina3.2-tts",
            "input": chunk,
            "voice": args.voice,
            "response_format": response_format
        }

        print(f"Sending request to Sarashina TTS API (chunk={i+1}/{len(text_chunks)}, voice={args.voice}, format={response_format})...")
        try:
            tts_response = requests.post(TTS_API_URL, json=tts_payload, headers=headers, timeout=60)
            if tts_response.status_code != 200:
                print(f"TTS API Error [{tts_response.status_code}]: {tts_response.text}", file=sys.stderr)
                sys.exit(1)

            audio_segments.append(tts_response.content)
        except Exception as e:
            print(f"Error calling TTS API: {e}", file=sys.stderr)
            sys.exit(1)

    # ファイル保存（複数チャンクは連結）
    with open(args.output, "wb") as f:
        for segment in audio_segments:
            f.write(segment)
    print(f"Successfully generated speech output: {args.output}")

if __name__ == "__main__":
    main()
