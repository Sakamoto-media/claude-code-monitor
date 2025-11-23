# Claude Code Voice Controller

複数のTerminal.appタブ/ウィンドウで実行中のClaude Codeセッションを音声で監視・操作できるmacOS専用アプリケーションです。

## 機能

### 📊 マルチセッション監視
- 複数のTerminal.appウィンドウ・タブを自動検出
- Claude Codeの実行状態をリアルタイムで表示
- タスク進捗（Todo）を可視化
- エラー・警告の自動検出

### 🎤 音声コントロール
- **タブ切り替え**: 「次のタブ」「前のタブ」「タブ3」
- **ウィンドウ切り替え**: 「ウィンドウ1」
- **要約**: 「要約して」で最新の出力を10秒程度で音声読み上げ
- **選択肢入力**: 「選択1」「選択2」など
- **テキスト入力**: その他の音声はそのままテキストとして入力

### 🖥️ GUI
- 縦長のモニタリングウィンドウ
- 各セッションの状態を色分け表示
  - 🟢 緑: 実行中
  - 🟡 黄: 入力待ち
  - 🔴 赤: エラー
  - ⚪ グレー: アイドル
- クリックでセッション切り替え
- 常に最前面表示（オプション）

## システム要件

- macOS 10.14以降
- Python 3.8以降
- Terminal.app
- マイク（音声入力用）
- インターネット接続（音声認識用）

## インストール

### 1. 依存関係のインストール

```bash
cd /Users/sakamotoryouken/Desktop/MCP/会話/秘書システム/画面操作
pip install -r requirements.txt
```

### 2. 追加セットアップ（PyAudioのインストール）

PyAudioはmacOSで別途Homebrewが必要な場合があります：

```bash
# Homebrewでportaudioをインストール
brew install portaudio

# PyAudioをインストール
pip install pyaudio
```

### 3. 権限設定

macOSのセキュリティ設定で以下の権限を許可：

- **マイクへのアクセス**: システム設定 → セキュリティとプライバシー → マイク
- **アクセシビリティ**: システム設定 → セキュリティとプライバシー → アクセシビリティ
  - Terminal.appまたはPythonを許可

### 4. Claude API設定（オプション）

より高度な要約機能を使いたい場合、環境変数を設定：

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

または`.env`ファイルを作成：

```
ANTHROPIC_API_KEY=your-api-key-here
```

## 使い方

### 起動

```bash
python main.py
```

または実行権限を付与して：

```bash
chmod +x main.py
./main.py
```

### 基本操作

1. **アプリケーション起動**: 縦長のモニタリングウィンドウが表示されます
2. **セッション確認**: 各Terminal.appのタブが一覧表示されます
3. **音声入力開始**: 「🎤 音声入力開始」ボタンをクリック
4. **音声コマンド**: マイクに向かって日本語で指示

### 音声コマンド一覧

| コマンド | 動作 |
|---------|------|
| 「次のタブ」「タブ切り替え」 | 次のタブに切り替え |
| 「前のタブ」「戻る」 | 前のタブに切り替え |
| 「タブ3」「タブ1」 | 指定番号のタブに切り替え |
| 「ウィンドウ2」 | 指定番号のウィンドウに切り替え |
| 「要約して」「読み上げ」 | 現在のセッションを要約して読み上げ |
| 「選択1」「1番」 | 選択肢1を選択 |
| 「選択2」「2番」 | 選択肢2を選択 |
| 「更新」 | セッション情報を更新 |
| その他のテキスト | そのままClaude Codeに入力 |

### GUI操作

- **セッションカードをクリック**: そのセッションに切り替え＋要約を読み上げ
- **スクロール**: マウスホイールで上下スクロール
- **最前面表示**: 常に他のウィンドウの上に表示

## アーキテクチャ

```
main.py                    # メインコントローラー
├── terminal_monitor.py    # Terminal.app監視・制御
├── gui.py                 # Tkinter GUI
├── voice_control.py       # 音声認識・合成
├── claude_parser.py       # Claude Code出力解析
└── config.py              # 設定ファイル
```

### 主要モジュール

#### terminal_monitor.py
- AppleScriptでTerminal.appの情報を取得
- タブ/ウィンドウの切り替え
- セッション内容の読み取り
- テキストの送信

#### gui.py
- Tkinterで縦長モニタリングウィンドウを構築
- セッションカードの表示
- リアルタイム更新

#### voice_control.py
- speech_recognitionで音声入力
- macOSの`say`コマンドで音声出力
- 音声コマンドのパース

#### claude_parser.py
- Claude Codeの出力を解析
- 質問・選択肢・エラー検出
- 要約生成（10秒で読める長さ）

## トラブルシューティング

### 音声認識が動かない

1. マイクの権限を確認
2. インターネット接続を確認（Google Speech API使用）
3. PyAudioが正しくインストールされているか確認

```bash
python -c "import pyaudio; print('OK')"
```

### Terminal.appのタブが検出されない

1. Terminal.appが起動しているか確認
2. AppleScriptの権限を確認
3. Terminal.appのタブが実際に開いているか確認

### セッション切り替えができない

1. アクセシビリティ権限を確認
2. Terminal.appが最前面にあるか確認

### 音声読み上げが日本語にならない

macOSの音声設定を確認：

```bash
say -v "?"  # 利用可能な音声を確認
```

Kyokoがインストールされているか確認してください。

## カスタマイズ

### config.pyで設定可能な項目

```python
# ウィンドウサイズ
WINDOW_WIDTH = 350
WINDOW_HEIGHT = 800

# 更新間隔（ミリ秒）
UPDATE_INTERVAL = 2000

# 要約の最大文字数
SUMMARY_MAX_LENGTH = 200

# 音声速度
TTS_RATE = 200  # Words per minute

# 色設定
COLORS = {
    "bg": "#1e1e1e",
    "fg": "#ffffff",
    "active": "#4CAF50",
    "waiting": "#FFC107",
    "error": "#F44336",
    "idle": "#9E9E9E"
}
```

### 音声コマンドの追加

`config.py`の`VOICE_COMMANDS`辞書を編集：

```python
VOICE_COMMANDS = {
    "カスタムコマンド": ["キーワード1", "キーワード2"],
    # ...
}
```

## テスト

各モジュールは個別にテスト実行可能：

```bash
# Terminal監視のテスト
python terminal_monitor.py

# GUIのテスト
python gui.py

# Claude出力解析のテスト
python claude_parser.py

# 音声認識のテスト
python voice_control.py
```

## 制限事項

- macOS専用（Terminal.app、AppleScript依存）
- 音声認識はインターネット接続が必要（Google Speech API）
- 複数のClaude Codeプロセスを同時に監視する場合、パフォーマンスが低下する可能性
- Terminal.app以外のターミナルエミュレータ（iTerm2など）には非対応

## 今後の改善予定

- [ ] iTerm2対応
- [ ] オフライン音声認識（Vosk等）
- [ ] Claude API統合での高度な要約
- [ ] セッション履歴の保存
- [ ] カスタマイズ可能なキーボードショートカット
- [ ] ダークモード/ライトモードの切り替え

## ライセンス

MIT License

## 貢献

Issue、Pull Requestを歓迎します。

## サポート

問題が発生した場合は、以下の情報を含めてIssueを作成してください：

- macOSのバージョン
- Pythonのバージョン
- エラーメッセージ
- 実行ログ
