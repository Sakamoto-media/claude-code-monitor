# Claude Code Monitor - 必要なソフトウェア一覧

## システム要件
- **OS**: macOS 10.14以降
- **Python**: Python 3.8以降

## 必須ソフトウェア

### 1. Python環境
```bash
# Homebrewでインストール（推奨）
brew install python3
```

### 2. Terminal.app
- macOS標準のターミナルアプリケーション
- このアプリはTerminal.appのウィンドウ・タブを監視します

### 3. Claude Code CLI
- Anthropic公式のClaude Code CLIツール
- インストール方法: https://docs.anthropic.com/claude-code

## Pythonパッケージ

### 必須パッケージ
以下のパッケージが必要です：

```bash
pip install tkinter           # GUI（通常Pythonに同梱）
pip install pyaudio           # 音声再生（低遅延）
pip install requests          # VOICEVOX API通信用
```

### パッケージの説明
- **tkinter**: GUIフレームワーク（通常Python標準ライブラリに含まれる）
- **pyaudio**: 低遅延音声再生用（VOICEVOX読み上げの滑らかな再生に必要）
- **requests**: HTTP通信ライブラリ（VOICEVOX Engine API呼び出し用）

## オプションソフトウェア

### VOICEVOX Engine（音声読み上げ機能を使う場合）
- **用途**: ずんだもんによる音声読み上げ
- **インストール方法**:
  1. https://voicevox.hiroshiba.jp/ からダウンロード
  2. アプリケーションを起動（デフォルトポート: 50021）
- **備考**: Apple純正TTS（say コマンド）を使う場合は不要

### Homebrew（パッケージマネージャー）
```bash
# Homebrewのインストール
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

## API設定

### Anthropic API Key
- Claude APIを使用するため、Anthropic API Keyが必要
- 取得方法: https://console.anthropic.com/
- 設定ファイル: `config.json`
  ```json
  {
    "anthropic_api_key": "sk-ant-api03-...",
    "model": "claude-sonnet-4-5-20250929",
    "max_tokens": 200,
    "temperature": 0.7
  }
  ```

## インストール手順

### 1. 基本環境セットアップ
```bash
# Homebrewインストール（未インストールの場合）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python3インストール
brew install python3

# 作業ディレクトリに移動
cd /Users/sakamotoryouken/Desktop/MCP/会話/秘書システム/画面操作
```

### 2. Pythonパッケージインストール
```bash
# 必須パッケージ
pip3 install pyaudio requests

# PyAudioのインストールでエラーが出る場合
brew install portaudio
pip3 install pyaudio
```

### 3. VOICEVOX Engine（オプション）
```bash
# VOICEVOX公式サイトからダウンロード
# https://voicevox.hiroshiba.jp/

# ダウンロード後、アプリケーションを起動
# デフォルトでlocalhost:50021で待ち受け
```

### 4. API設定
```bash
# config.jsonを編集してAnthropic API Keyを設定
nano config.json
```

### 5. アプリケーション起動
```bash
python3 main.py
```

## トラブルシューティング

### PyAudioのインストールエラー
```bash
# portaudioが見つからない場合
brew install portaudio
export LDFLAGS="-L/opt/homebrew/lib"
export CPPFLAGS="-I/opt/homebrew/include"
pip3 install pyaudio
```

### Tkinterが見つからない
```bash
# macOSの場合、通常Pythonに同梱されています
# それでもエラーが出る場合
brew install python-tk@3.11  # バージョンは環境に合わせて調整
```

### VOICEVOX Engineに接続できない
- VOICEVOX Engineアプリケーションが起動しているか確認
- ポート50021が使用中でないか確認:
  ```bash
  lsof -i :50021
  ```

## 動作確認

### システムチェック
```bash
# Pythonバージョン確認
python3 --version  # 3.8以降であること

# パッケージ確認
python3 -c "import tkinter; print('tkinter OK')"
python3 -c "import pyaudio; print('pyaudio OK')"
python3 -c "import requests; print('requests OK')"

# VOICEVOX Engine接続確認（VOICEVOX使用時のみ）
curl http://localhost:50021/version
```

## プロジェクト構成
```
画面操作/
├── main.py                 # メインエントリーポイント
├── gui.py                  # GUI実装
├── terminal_monitor.py     # Terminal.app監視
├── claude_parser.py        # Claude Code出力解析
├── config.py              # 設定定義
├── config.json            # API・GUI設定（要手動編集）
└── REQUIREMENTS.md        # このファイル
```

## 更新履歴
- 2025-01-24: 初版作成
- 2025-01-24: PyAudio追加（低遅延音声再生のため）
