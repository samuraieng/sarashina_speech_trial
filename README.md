# Sarashina Speech-to-Speech Project

[Sarashina サービス API](https://sarashina.ai/) を利用して、ASR（音声認識）、TTS（音声合成）、S2S-LLM（Speech-to-Speech with LLM）の各種機能を検証・構築するプロジェクトです。

## フォルダ構成

- `src/`: 実行可能な Python スクリプト
  - `sara_ttsph1.py`: テキスト・URL・`.txt` ファイルから音声を合成する TTS スクリプト
  - `sara_asrph1.py`: 音声ファイル（WAV）をテキストに変換する ASR スクリプト
  - `sara_llmph1.py`: 音声入力を LLM で処理し、日本語または英語の音声で応答する S2S-LLM パイプライン
- `test/`: 各スクリプトのユニットテスト
  - `test_sara_ttsph1.py`: TTS のテスト
  - `test_sara_asrph1.py`: ASR のテスト
  - `test_sara_llmph1.py`: S2S-LLM のテスト
- `requirements.txt`: 依存 Python パッケージ一覧
- `LICENSE`: ライセンス

## 前提条件

- Python 3.11 以上（開発・検証環境は Python 3.11）
- Sarashina API キー（`SARASHINA_API_KEY` 環境変数に設定）

## 環境構築

1. 仮想環境の作成と有効化

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. 依存パッケージのインストール

   ```bash
   pip install -r requirements.txt
   ```

3. API キーの設定

   ```bash
   export SARASHINA_API_KEY="your-api-key"
   ```

---

## 各サブプロジェクトの使い方

### 1. TTS（音声合成）: `sara_ttsph1.py`

指定したテキスト、URL、または `.txt` ファイルの内容を音声ファイル（WAV/MP3）に変換します。

```bash
python3 src/sara_ttsph1.py \
  --input "おはようございます" \
  --voice ja_m_1 \
  --output speech.wav
```

- `--input`: 読み上げたいテキスト、URL、または `.txt` ファイルのパス
- `--voice`: 音声種別（`ja_f_1`, `ja_f_2`, `ja_m_1`）
- `--output`: 出力ファイルパス（`.wav` または `.mp3`）

### 2. ASR（音声認識）: `sara_asrph1.py`

音声ファイル（WAV）をテキストに変換します。サンプリングレートが 16,000 Hz でない場合は自動的にリサンプリングされます。

```bash
python3 src/sara_asrph1.py --input speech.wav
```

- `--input`: 認識対象の WAV ファイルパス

### 3. S2S-LLM: `sara_llmph1.py`

音声ファイルを入力として、**ASR → LLM → （翻訳） → TTS** のパイプラインを実行し、応答音声を生成します。  
LLM は日本文化の観点から読み上げ原稿を生成し、`--lang en` を指定すると日本語の認識結果を英語に翻訳してから音声合成します。

#### 日本語入力 → 日本語音声応答

```bash
python3 src/sara_llmph1.py \
  --input speech.wav \
  --output response_ja.wav \
  --lang ja \
  --voice ja_m_1
```

#### 日本語入力 → 英語音声応答

```bash
python3 src/sara_llmph1.py \
  --input speech.wav \
  --output response_en.wav \
  --lang en \
  --voice ja_m_1
```

- `--input`: 入力音声ファイルパス（WAV形式、デフォルト: `speech.wav`）
- `--output`: 出力音声ファイルパス（デフォルト: `output.wav`）
- `--lang`: 出力言語（`ja` または `en`、デフォルト: `ja`）
- `--voice`: 音声種別（`ja_f_1`, `ja_f_2`, `ja_m_1`、デフォルト: `ja_m_1`）

---

## テストの実行

仮想環境上で以下を実行してください。

```bash
python3 -m unittest discover -s test
```

すべてのテストが `OK` になれば正常です。
