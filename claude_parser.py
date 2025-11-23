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
            print("API-based summarization will be disabled. Use fallback method.")
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
                    print("API key not configured. Using fallback summarization.")
            else:
                print("Anthropic package not available. Using fallback summarization.")
        except Exception as e:
            print(f"Error loading API config: {e}")
            print("Using fallback summarization.")

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

    def _summarize_with_api(self, text: str, max_length: int = 200) -> str:
        """Claude APIを使ってテキストを要約"""
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
