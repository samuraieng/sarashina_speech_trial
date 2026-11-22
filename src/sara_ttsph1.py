#!/usr/bin/env python3
import os
import sys
import argparse
import re
import requests
from bs4 import BeautifulSoup

TTS_API_URL = "https://api.sarashina.ai/v1/audio/speech"
TRANSLATE_API_URL = "https://api.sarashina.ai/v1/translate"

def extract_text_from_url(url: str) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 不要なタグを除去
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
            
        # 本文テキストを抽出
        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned_text = " ".join(lines)
        return cleaned_text
    except Exception as e:
        print(f"Error fetching URL {url}: {e}", file=sys.stderr)
        sys.exit(1)

def is_japanese(text: str) -> bool:
    # ひらがな、カタカナ、漢字のいずれかが含まれていれば日本語と判定
    jp_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]')
    return bool(jp_pattern.search(text))

def translate_to_japanese(text: str, api_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "source_lang": "en",
        "target_lang": "ja",
        "style": "auto"
    }
    try:
        print(f"Translating non-Japanese text to Japanese...")
        response = requests.post(TRANSLATE_API_URL, json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f"Translate API Error [{response.status_code}]: {response.text}", file=sys.stderr)
            sys.exit(1)
        
        data = response.json()
        if isinstance(data, dict):
            translated = data.get("translated_text") or data.get("text") or data.get("result")
            if translated:
                return translated
        return str(data)
    except Exception as e:
        print(f"Error during translation: {e}", file=sys.stderr)
        sys.exit(1)

def sanitize_for_tts(text):
    """
    TTS APIの仕様に基づき、未対応文字の置換・除去および文字数バリデーションを行う。
    - 下限: 2文字
    """
    if not text:
        return ""

    # 一般的な置換
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
        # target ± window の範囲を探索
        low = max(start + 2, start + target - window)
        high = min(start + hard_limit, n)

        for sep in separators:
            # 区切り文字を優先順位に従って、high から low まで逆順に探す
            idx = text.rfind(sep, low, high)
            if idx != -1:
                end = idx
                break

        if end == -1:
            # 区切りが見つからなければ hard_limit で強制切断
            end = min(start + hard_limit, n)

        chunks.append(text[start:end])
        # 区切り文字をスキップ（複数の連続する区切り文字にも対応）
        next_start = end
        while next_start < n and text[next_start] in separators:
            next_start += 1
        if next_start == end:
            next_start = end
        start = next_start

    return chunks

def main():
    parser = argparse.ArgumentParser(description="Sarashina TTS & Translate client (Phase 1)")
    parser.add_argument(
        "--input",
        type=str,
        default="おはようございます。七時になりました。いかがおすごしでしょうか",
        help="Text to speech, URL, or text file (.txt)"
    )
    parser.add_argument(
        "--voice",
        type=str,
        default="ja_m_1",
        choices=["ja_f_1", "ja_f_2", "ja_m_1"],
        help="Voice type"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="speech.mp3",
        help="Output file path (allowed extensions: mp3, wav)"
    )

    args = parser.parse_args()

    # 出力ファイルの拡張子チェック
    ext = os.path.splitext(args.output)[1].lower()
    if ext not in [".mp3", ".wav"]:
        print(f"Error: Unsupported output file extension '{ext}'. Allowed extensions are .mp3 and .wav", file=sys.stderr)
        sys.exit(1)
    response_format = ext.lstrip(".")

    # APIキーの確認
    api_key = os.getenv("SARASHINA_API_KEY")
    if not api_key:
        print("Error: SARASHINA_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    # 入力がURLか、テキストファイルか、文字列か判定
    input_text = args.input
    if input_text.startswith("http://") or input_text.startswith("https://"):
        print(f"Fetching text from URL: {input_text}...")
        input_text = extract_text_from_url(input_text)
        print(f"Extracted text length: {len(input_text)} characters")
    elif os.path.exists(input_text) and input_text.lower().endswith(".txt"):
        print(f"Reading text from file: {input_text}...")
        try:
            with open(input_text, "r", encoding="utf-8") as f:
                input_text = f.read().strip()
            print(f"Read text length: {len(input_text)} characters")
        except Exception as e:
            print(f"Error reading file {input_text}: {e}", file=sys.stderr)
            sys.exit(1)

    # 非日本語の場合、翻訳を実行
    if not is_japanese(input_text):
        print(f"Input is detected as non-Japanese. Translating...")
        input_text = translate_to_japanese(input_text, api_key)
        print(f"Translated text: {input_text}")

    # サニタイジング適用
    input_text = sanitize_for_tts(input_text)

    # 700文字超過時は自然な区切りでチャンク分割
    text_chunks = split_text_into_chunks(input_text)
    print(f"Text split into {len(text_chunks)} chunk(s).")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    audio_segments = []
    for i, chunk in enumerate(text_chunks):
        # APIリクエストペイロード (TTS)
        payload = {
            "model": "sarashina3.2-tts",
            "input": chunk,
            "voice": args.voice,
            "response_format": response_format
        }

        print(f"Sending request to Sarashina TTS API (chunk={i+1}/{len(text_chunks)}, voice={args.voice}, model=sarashina3.2-tts, format={response_format})...")
        try:
            response = requests.post(TTS_API_URL, json=payload, headers=headers, timeout=30)

            if response.status_code != 200:
                print(f"API Error [{response.status_code}]: {response.text}", file=sys.stderr)
                sys.exit(1)

            audio_segments.append(response.content)

        except requests.exceptions.RequestException as e:
            print(f"Network error during API request: {e}", file=sys.stderr)
            sys.exit(1)

    # ファイル保存（複数チャンクは連結）
    with open(args.output, "wb") as f:
        for segment in audio_segments:
            f.write(segment)

    print(f"Successfully generated speech audio: {args.output}")

if __name__ == "__main__":
    main()
