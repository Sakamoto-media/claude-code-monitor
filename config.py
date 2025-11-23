"""
設定ファイル
"""
import os
from pathlib import Path

# アプリケーション設定
APP_NAME = "Claude Code Monitor"
WINDOW_WIDTH = 350
WINDOW_HEIGHT = 800
UPDATE_INTERVAL = 1000  # ミリ秒（1秒ごとに更新）

# 音声設定
VOICE_LANGUAGE = "ja-JP"  # 日本語
SUMMARY_MAX_LENGTH = 200  # 要約の最大文字数（10秒で読める程度）
TTS_RATE = 200  # 音声速度（Words per minute）

# Claude Code検出設定
CLAUDE_PROCESS_PATTERNS = [
    "claude",
    "claude-code",
    "node.*claude"
]

# ログディレクトリ
LOG_DIR = Path.home() / ".claude_voice_controller" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Claude API設定（要約機能用）
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

# 音声コマンド設定
VOICE_COMMANDS = {
    "タブ切り替え": ["タブ切り替え", "次のタブ", "ネクスト"],
    "前のタブ": ["前のタブ", "プレビアス", "戻る"],
    "要約": ["要約", "要約して", "読み上げ"],
    "選択1": ["選択1", "1番", "いち"],
    "選択2": ["選択2", "2番", "に"],
    "選択3": ["選択3", "3番", "さん"],
    "選択4": ["選択4", "4番", "よん"],
    "更新": ["更新", "リフレッシュ"],
}

# 色設定
COLORS = {
    "bg": "#1e1e1e",
    "fg": "#ffffff",
    "active": "#4CAF50",
    "waiting": "#FFC107",
    "error": "#F44336",
    "idle": "#9E9E9E",
    "highlight": "#2196F3"
}
