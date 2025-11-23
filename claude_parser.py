"""
Claude Codeの出力を解析するモジュール
"""
import re
import json
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("Warning: anthropic package not available. API-based summarization will be disabled.")


@dataclass
class ClaudeResponse:
    """Claude Codeの応答を表すクラス"""
    text: str
    has_question: bool
    options: List[str]
    todo_status: Optional[Dict[str, int]]  # {"completed": 3, "total": 5}
    error_detected: bool
    is_waiting_input: bool


class ClaudeOutputParser:
    """Claude Codeの出力を解析"""

    # パターン定義
    QUESTION_PATTERNS = [
        r'\?[^\n]*$',  # 末尾に?
        r'(選択してください|選んでください|選択肢|どちらにしますか)',
        r'(yes/no|y/n)',
        r'\[.*\]\s*:?\s*$'  # [オプション] で終わる
    ]

    TODO_PATTERN = r'(\d+)/(\d+)\s*(completed|tasks?|done)'

    OPTION_PATTERNS = [
        r'^\s*([0-9]+)[\.\)]\s+(.+)$',  # 1. オプション or 1) オプション
        r'^\s*\[([A-Za-z0-9])\]\s+(.+)$',  # [A] オプション
        r'^\s*-\s+(.+)$'  # - オプション
    ]

    ERROR_KEYWORDS = [
        'error', 'failed', 'exception', 'cannot', 'unable to',
        'エラー', '失敗', '例外', 'できません'
    ]

    def __init__(self):
        """初期化"""
        self.api_client = None
        self.api_config = None
        self._load_api_config()

    def _load_api_config(self):
        """API設定を読み込み"""
        config_path = Path(__file__).parent / "api_config.json"

        if not config_path.exists():
            print(f"API config file not found: {config_path}")
            print("Creating default api_config.json...")
            self._create_default_config(config_path)
            print("\n" + "="*60)
            print("IMPORTANT: Claude API Key is required for summarization!")
            print("="*60)
            print(f"Please edit {config_path}")
            print("and set your Claude API key in 'anthropic_api_key' field.")
            print("\nYou can get your API key from:")
            print("https://console.anthropic.com/")
            print("\nUsing fallback summarization until API key is configured.")
            print("="*60 + "\n")
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.api_config = json.load(f)

            if ANTHROPIC_AVAILABLE and self.api_config.get('anthropic_api_key'):
                api_key = self.api_config['anthropic_api_key']
                if api_key and api_key != "your-api-key-here":
                    self.api_client = Anthropic(api_key=api_key)
                    print("Claude API client initialized successfully")
                else:
                    print("\n" + "="*60)
                    print("IMPORTANT: Claude API Key is not configured!")
                    print("="*60)
                    print(f"Please edit {config_path}")
                    print("and set your Claude API key in 'anthropic_api_key' field.")
                    print("\nYou can get your API key from:")
                    print("https://console.anthropic.com/")
                    print("\nUsing fallback summarization until API key is configured.")
                    print("="*60 + "\n")
            else:
                print("Anthropic package not available. Using fallback summarization.")
        except Exception as e:
            print(f"Error loading API config: {e}")
            print("Using fallback summarization.")

    def _create_default_config(self, config_path: Path):
        """デフォルトのAPI設定ファイルを作成"""
        default_config = {
            "anthropic_api_key": "your-api-key-here",
            "model": "claude-sonnet-4-5-20250929",
            "max_tokens": 200,
            "temperature": 0.7,
            "summary_instructions": "以下のClaude Codeセッションの出力を、10秒で読める程度（約150文字）に要約してください。要約の時には本文以外のタイトルなど余分なものは入れないでください"
        }

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            print(f"Created default config file: {config_path}")
        except Exception as e:
            print(f"Error creating default config file: {e}")

    def parse(self, text: str) -> ClaudeResponse:
        """テキストを解析してClaudeResponseを返す"""
        if not text:
            return ClaudeResponse(
                text="",
                has_question=False,
                options=[],
                todo_status=None,
                error_detected=False,
                is_waiting_input=False
            )

        # 質問検出
        has_question = self._detect_question(text)

        # 選択肢抽出
        options = self._extract_options(text)

        # Todo状態抽出
        todo_status = self._extract_todo_status(text)

        # エラー検出
        error_detected = self._detect_error(text)

        # 入力待ち検出
        is_waiting = has_question or len(options) > 0 or text.strip().endswith(':')

        return ClaudeResponse(
            text=text,
            has_question=has_question,
            options=options,
            todo_status=todo_status,
            error_detected=error_detected,
            is_waiting_input=is_waiting
        )

    def _detect_question(self, text: str) -> bool:
        """質問が含まれているか検出"""
        # 最後の数行をチェック
        lines = text.strip().split('\n')
        last_lines = '\n'.join(lines[-5:])

        for pattern in self.QUESTION_PATTERNS:
            if re.search(pattern, last_lines, re.IGNORECASE):
                return True
        return False

    def _extract_options(self, text: str) -> List[str]:
        """選択肢を抽出"""
        lines = text.strip().split('\n')
        options = []

        # 最後の20行程度をチェック
        for line in lines[-20:]:
            for pattern in self.OPTION_PATTERNS:
                match = re.match(pattern, line.strip())
                if match:
                    # オプションテキストを取得
                    if len(match.groups()) == 2:
                        option_text = match.group(2)
                    else:
                        option_text = match.group(1)

                    options.append(option_text.strip())

        return options

    def _extract_todo_status(self, text: str) -> Optional[Dict[str, int]]:
        """Todo進捗を抽出"""
        match = re.search(self.TODO_PATTERN, text, re.IGNORECASE)
        if match:
            completed = int(match.group(1))
            total = int(match.group(2))
            return {"completed": completed, "total": total}
        return None

    def _detect_error(self, text: str) -> bool:
        """エラーが含まれているか検出"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.ERROR_KEYWORDS)

    def summarize(self, text: str, max_length: int = 200) -> str:
        """
        テキストを要約（音声読み上げ用）
        max_length: 最大文字数（10秒で読める程度）
        """
        if not text:
            return "出力がありません"

        # Claude APIが利用可能な場合はAPIで要約
        if self.api_client and self.api_config:
            try:
                return self._summarize_with_api(text, max_length)
            except Exception as e:
                print(f"API summarization failed: {e}, falling back to simple method")
                # フォールバック: シンプルな要約方法を使用

        # 最新の内容を優先
        lines = text.strip().split('\n')

        # 空行を除去
        lines = [line for line in lines if line.strip()]

        if not lines:
            return "出力がありません"

        # 重要な情報を抽出
        summary_parts = []

        # エラーチェック
        if self._detect_error(text):
            summary_parts.append("エラーが発生しています。")

        # Todo状態
        todo = self._extract_todo_status(text)
        if todo:
            summary_parts.append(
                f"タスク進捗: {todo['completed']}個中{todo['total']}個完了。"
            )

        # 質問があるか
        if self._detect_question(text):
            summary_parts.append("入力を待っています。")

        # 最新の実質的な出力（最後の数行）
        relevant_lines = []
        for line in reversed(lines):
            # プロンプトや空行をスキップ
            if line.strip() and not line.startswith('$') and not line.startswith('>'):
                relevant_lines.insert(0, line)
                if len(' '.join(relevant_lines)) > max_length // 2:
                    break

        if relevant_lines:
            main_content = ' '.join(relevant_lines)
            # 長すぎる場合は切り詰め
            if len(main_content) > max_length - sum(len(p) for p in summary_parts):
                main_content = main_content[:max_length - sum(len(p) for p in summary_parts)] + "..."

            summary_parts.append(main_content)

        summary = ' '.join(summary_parts)

        # 最終的な長さ調整
        if len(summary) > max_length:
            summary = summary[:max_length - 3] + "..."

        return summary if summary else "処理中です。"

    def _remove_current_user_input_area(self, text: str) -> str:
        """
        現在のユーザー入力エリア（─────で囲まれた範囲）を除外

        パターン:
        ─────────────────────────────────────────────────────────────────
        > ユーザーの入力がここに来る
        ─────────────────────────────────────────────────────────────────
        """
        lines = text.split('\n')

        # 下から走査して、─────のペアを見つける
        separator_indices = []
        for i, line in enumerate(lines):
            if '─' * 10 in line:  # 10文字以上の─────があれば区切り線と判定
                separator_indices.append(i)

        if len(separator_indices) >= 2:
            # 最後から2番目の区切り線より前までを使用（最後のユーザー入力ブロックを除外）
            last_separator = separator_indices[-2]
            filtered_lines = lines[:last_separator]
            return '\n'.join(filtered_lines)

        # 区切り線が見つからない場合は元のまま返す
        return text

    def _remove_previous_user_input(self, text: str) -> str:
        """
        前回のユーザー指示内容を除外（'>'で始まる段落を最後から検索して削除）

        注意: 現在のユーザー入力エリアを削除してから検索すること

        パターン:
        > ユーザーの前回の指示
        複数行続く場合もある

        空行

        Claudeの応答...  ← この部分のみを要約対象にする
        """
        # まず現在のユーザー入力エリアを削除
        text = self._remove_current_user_input_area(text)

        lines = text.split('\n')

        # 下から走査して、'>'で始まる行を探す
        last_user_input_start = -1
        for i in range(len(lines) - 1, -1, -1):
            stripped = lines[i].strip()
            if stripped.startswith('>'):
                last_user_input_start = i
                break

        if last_user_input_start == -1:
            # '>'で始まる行が見つからない場合は元のまま返す
            return text

        # '>'で始まる行より後ろから、最初の空行より後ろを使用
        remaining_lines = lines[last_user_input_start + 1:]

        # 最初の空行を探す
        first_empty_line = -1
        for i, line in enumerate(remaining_lines):
            if not line.strip():
                first_empty_line = i
                break

        if first_empty_line != -1:
            # 空行より後ろを返す
            filtered_lines = remaining_lines[first_empty_line + 1:]
            return '\n'.join(filtered_lines)
        else:
            # 空行が見つからない場合は'>'の行より後ろ全てを返す
            return '\n'.join(remaining_lines)

    def _summarize_with_api(self, text: str, max_length: int = 200) -> str:
        """Claude APIを使ってテキストを要約"""
        # 前回のユーザー指示内容を除外
        text = self._remove_previous_user_input(text)

        # 入力テキストが長すぎる場合は最新部分のみを使用
        if len(text) > 10000:
            text = text[-10000:]

        # APIリクエスト
        instructions = self.api_config.get('summary_instructions',
            "以下のClaude Codeセッションの出力を、10秒で読める程度（約150文字）に要約してください。重要なポイント、エラー、進捗状況を含めてください。")

        message = self.api_client.messages.create(
            model=self.api_config.get('model', 'claude-sonnet-4-5-20250929'),
            max_tokens=self.api_config.get('max_tokens', 200),
            temperature=self.api_config.get('temperature', 0.7),
            messages=[{
                "role": "user",
                "content": f"{instructions}\n\n出力:\n{text}"
            }]
        )

        # レスポンスから要約を抽出
        if message.content and len(message.content) > 0:
            summary = message.content[0].text.strip()

            # 長さ調整
            if len(summary) > max_length:
                summary = summary[:max_length - 3] + "..."

            return summary
        else:
            return "要約の生成に失敗しました"


if __name__ == "__main__":
    # テスト
    parser = ClaudeOutputParser()

    # テストケース1: 質問あり
    test1 = """
I've found 3 potential approaches:

1. Use React hooks
2. Use class components
3. Use functional components

Which approach would you like to use?
    """

    result1 = parser.parse(test1)
    print("Test 1 - Question detection:")
    print(f"  Has question: {result1.has_question}")
    print(f"  Options: {result1.options}")
    print(f"  Summary: {parser.summarize(test1)}")
    print()

    # テストケース2: Todo進捗
    test2 = """
Running tests...
✓ Test 1 passed
✓ Test 2 passed
✗ Test 3 failed

Progress: 5/10 tasks completed
    """

    result2 = parser.parse(test2)
    print("Test 2 - Todo detection:")
    print(f"  Todo status: {result2.todo_status}")
    print(f"  Error detected: {result2.error_detected}")
    print(f"  Summary: {parser.summarize(test2)}")
    print()

    # テストケース3: エラー
    test3 = """
Error: Failed to compile TypeScript
Cannot find module '@types/node'
    """

    result3 = parser.parse(test3)
    print("Test 3 - Error detection:")
    print(f"  Error detected: {result3.error_detected}")
    print(f"  Summary: {parser.summarize(test3)}")
