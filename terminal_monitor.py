"""
Terminal.appのウィンドウとタブを監視・制御するモジュール
"""
import subprocess
import re
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TerminalSession:
    """Terminal.appのセッション情報"""
    window_id: int
    tab_index: int
    tab_name: str
    is_running_claude: bool
    last_output: str
    status: str  # "active", "waiting", "idle", "error"
    todo_progress: Optional[str]  # "3/5 completed"
    last_updated: datetime
    summary: str = ""  # Claude APIによる要約
    previous_output: str = ""  # 前回の出力（変更検知用）
    needs_summary: bool = False  # 要約が必要かどうか
    last_trigger_state: str = ""  # 前回のトリガー状態（重複要約防止用）
    display_order: int = 0  # ユーザー定義の表示順序（ドラッグ&ドロップ用）
    idle_check_count: int = 0  # アイドル判定の連続カウント（activeからidleへの変化を2回チェック）

    @property
    def display_name(self) -> str:
        """表示用の名前（Claude Codeセッション用）"""
        # シンプルにタブ名のみを表示
        # 番号付けはGUI側で行う（Claude Codeセッションのみをカウント）
        return self.tab_name


class TerminalMonitor:
    """Terminal.appを監視・制御するクラス"""

    def __init__(self):
        self.sessions: List[TerminalSession] = []

    def detect_sessions(self) -> List[TerminalSession]:
        """
        Terminal.appの全ウィンドウ・タブを検出し、Claude Codeセッションを識別
        """
        sessions = []

        # AppleScriptでTerminal.appの情報を取得
        script = '''
        tell application "Terminal"
            set output to ""
            repeat with w from 1 to count of windows
                set win_id to id of window w
                repeat with t from 1 to count of tabs of window w
                    set tab_info to ""
                    set tab_info to tab_info & "WINDOW_ID:" & win_id & "|"
                    set tab_info to tab_info & "WINDOW_INDEX:" & w & "|"
                    set tab_info to tab_info & "TAB:" & t & "|"

                    try
                        -- タブ名を複数の方法で取得
                        set tab_name to ""

                        -- カスタムタイトルを試す
                        try
                            set tab_name to custom title of tab t of window w
                        end try

                        -- カスタムタイトルがない場合は、プロセス一覧を取得
                        if tab_name is "" then
                            try
                                set proc_list to processes of tab t of window w
                                -- プロセスリストをカンマ区切りの文字列に変換
                                set AppleScript's text item delimiters to ", "
                                set tab_name to proc_list as string
                                set AppleScript's text item delimiters to ""
                            end try
                        end if

                        if tab_name is "" then
                            set tab_name to "Unknown"
                        end if

                        set tab_info to tab_info & "NAME:" & tab_name & "|"

                        -- プロセスリストも別途取得
                        try
                            set proc_list to processes of tab t of window w
                            set AppleScript's text item delimiters to ","
                            set proc_str to proc_list as string
                            set AppleScript's text item delimiters to ""
                            set tab_info to tab_info & "PROCESSES:" & proc_str & "|"
                        end try
                    on error errMsg
                        set tab_info to tab_info & "NAME:Unknown|"
                    end try

                    try
                        set current_tab to (selected tab of window w) is (tab t of window w)
                        if current_tab then
                            set tab_info to tab_info & "ACTIVE:true|"
                        else
                            set tab_info to tab_info & "ACTIVE:false|"
                        end if
                    on error
                        set tab_info to tab_info & "ACTIVE:false|"
                    end try

                    set output to output & tab_info & "\\n"
                end repeat
            end repeat
            return output
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                sessions = self._parse_terminal_info(result.stdout)
        except subprocess.TimeoutExpired:
            print("Warning: Terminal detection timeout")
        except Exception as e:
            print(f"Error detecting sessions: {e}")

        self.sessions = sessions
        return sessions

    def _parse_terminal_info(self, output: str) -> List[TerminalSession]:
        """AppleScriptの出力をパース"""
        sessions = []

        for line in output.strip().split('\n'):
            if not line:
                continue

            parts = {}
            for part in line.split('|'):
                if ':' in part:
                    key, value = part.split(':', 1)
                    parts[key] = value

            if 'WINDOW_ID' in parts and 'TAB' in parts:
                window_id = int(parts['WINDOW_ID'])  # 固有ID（z-orderに依存しない）
                window_index = int(parts['WINDOW_INDEX'])  # 現在のz-order位置
                tab_index = int(parts['TAB']) - 1  # 0始まりに変換
                tab_name = parts.get('NAME', 'Unknown')
                processes = parts.get('PROCESSES', '')

                # デバッグ: AppleScriptから取得した情報を詳細にログ出力
                print(f"[TERMINAL-PARSE] Raw: WINDOW_ID={parts['WINDOW_ID']}, WINDOW_INDEX={parts['WINDOW_INDEX']}, TAB={parts['TAB']}, NAME={tab_name}")
                print(f"[TERMINAL-PARSE] Parsed: window_id={window_id} (fixed ID), window_index={window_index} (z-order), tab_index={tab_index}")

                # Claude Codeが動いているか簡易チェック（タブ名とプロセスの両方で判定）
                is_claude = self._check_if_claude_running(tab_name) or self._check_if_claude_running(processes)

                session = TerminalSession(
                    window_id=window_id,
                    tab_index=tab_index,
                    tab_name=tab_name,
                    is_running_claude=is_claude,
                    last_output="",
                    status="idle",
                    todo_progress=None,
                    last_updated=datetime.now()
                )
                sessions.append(session)
                print(f"[TERMINAL-PARSE] Created session: {session.display_name} (window_id={window_id}, tab_index={tab_index}, is_claude={is_claude})")

        return sessions

    def _check_if_claude_running(self, tab_name: str) -> bool:
        """タブ名からClaude Codeが実行中か判定"""
        claude_keywords = ['claude', 'claude-code', 'npx claude']
        return any(keyword in tab_name.lower() for keyword in claude_keywords)

    def switch_to_session(self, window_id: int, tab_index: int) -> bool:
        """指定されたウィンドウ・タブに切り替え（バックグラウンドで実行）"""
        print(f"[DEBUG] switch_to_session called: window_id={window_id} (fixed ID), tab_index={tab_index}")

        # window_idは固有IDなので、idで検索してからindexを1に設定
        # activate と set frontmost を削除してバックグラウンドで実行
        # これによりTkinterウィンドウのフォーカスを維持
        script = f'''
        tell application "Terminal"
            -- 固有IDでウィンドウを検索
            set targetWindow to first window whose id is {window_id}

            -- ウィンドウを前面に（Terminal内での順序のみ）
            log "Switching to window with ID " & {window_id}
            set index of targetWindow to 1

            -- タブを選択（1始まり）
            log "Selecting tab " & {tab_index + 1} & " of target window"
            set selected of tab {tab_index + 1} of targetWindow to true

            return "success"
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5
            )
            print(f"[DEBUG] AppleScript result:")
            print(f"  returncode: {result.returncode}")
            print(f"  stdout: {result.stdout!r}")
            print(f"  stderr: {result.stderr!r}")

            success = result.returncode == 0
            print(f"[DEBUG] switch_to_session returning: {success}")
            return success
        except Exception as e:
            print(f"[ERROR] Exception in switch_to_session: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_tab_content(self, window_id: int, tab_index: int, line_count: int = 50) -> str:
        """指定されたタブの内容を取得（最新N行）"""
        script = f'''
        tell application "Terminal"
            try
                set targetWindow to first window whose id is {window_id}
                set tab_contents to contents of tab {tab_index + 1} of targetWindow
                return tab_contents
            on error errMsg
                return "ERROR: " & errMsg
            end try
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout:
                output = result.stdout.strip()

                # エラーメッセージをログ出力
                if output.startswith("ERROR:"):
                    print(f"AppleScript error for window {window_id} tab {tab_index + 1}: {output}")
                    return ""

                lines = output.split('\n')
                return '\n'.join(lines[-line_count:])
            else:
                if result.stderr:
                    print(f"stderr: {result.stderr}")
                return ""
        except Exception as e:
            print(f"Error getting tab content: {e}")
            return ""

    def send_text_to_tab(self, window_id: int, tab_index: int, text: str) -> bool:
        """指定されたタブにテキストを送信"""
        # まず選択
        if not self.switch_to_session(window_id, tab_index):
            return False

        # テキストを送信（エスケープ処理）
        escaped_text = text.replace('\\', '\\\\').replace('"', '\\"')

        script = f'''
        tell application "Terminal"
            do script "{escaped_text}" in tab {tab_index + 1} of window {window_id}
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error sending text: {e}")
            return False

    def analyze_session_status(self, session: TerminalSession) -> TerminalSession:
        """セッションの状態を分析して更新"""
        content = self.get_tab_content(session.window_id, session.tab_index, 1000)

        session.last_output = content[-20000:] if content else ""  # 最新20000文字
        session.last_updated = datetime.now()

        if not content:
            session.status = "idle"
            print(f"[DEBUG] analyze_session_status: {session.display_name} -> idle (no content)")
            return session

        # 選択肢チェック: ユーザー入力エリアの下部（削除される部分）に選択肢があるかチェック
        has_options = self._check_for_options(content)

        # ユーザー入力エリア（─────で囲まれた範囲）を除外
        content_for_analysis = self._remove_user_input_area(content)

        # 判定には最下部10行のみを使用
        lines = content_for_analysis.split('\n')
        last_10_lines = lines[-10:] if len(lines) >= 10 else lines

        # 全文を使用（先頭15文字の制限なし）
        analysis_text = '\n'.join(last_10_lines)

        print(f"[DEBUG] analyze_session_status: {session.display_name}")
        print(f"  Last 10 lines: {analysis_text!r}")

        # 実行中を示す文言のチェック
        has_active_keyword = '(esc to interrupt' in analysis_text

        # 状態判定（activeからidleへの変化時のみ2周期チェック）
        # 緑（active）: "(esc to interrupt" が存在
        # 黄（waiting）: 選択肢が存在
        # グレー（idle）: それ以外（ただしactiveからの変化は2回確認）

        # 選択肢がある場合は優先的にwaiting判定（即座に判定）
        if has_options:
            session.status = "waiting"  # 選択肢あり
            session.idle_check_count = 0  # カウントリセット
            print(f"  -> waiting (found options in input area)")
        elif has_active_keyword:
            # activeキーワードが見つかった場合、即座にactive判定
            session.status = "active"  # 実行中
            session.idle_check_count = 0  # カウントリセット
            print(f"  -> active (found active keyword)")
        else:
            # activeキーワードがない場合
            # 現在activeの場合のみ、2回チェックを行う
            if session.status == "active":
                session.idle_check_count += 1
                print(f"  -> idle keyword found (count: {session.idle_check_count}/2)")

                # 2回連続でactiveキーワードがない場合のみidle判定
                if session.idle_check_count >= 2:
                    session.status = "idle"
                    print(f"  -> idle (confirmed after 2 checks)")
                else:
                    # 1回目はまだactive状態を維持
                    print(f"  -> keeping active status (waiting for 2nd check)")
            else:
                # 元々active以外の場合は即座にidle判定
                session.idle_check_count = 0
                session.status = "idle"
                print(f"  -> idle (no indicators)")

        return session

    def _check_for_options(self, content: str) -> bool:
        """
        最後の区切り線（─────）の直後に選択肢（1. 2. など）があるかチェック

        "1. "と"2. "の両方が含まれている場合のみTrueを返す

        構造（選択肢状態ではユーザー入力エリアの2本目の区切り線が消える）:
        ─────────────────────  ← 最後の区切り線
        選択肢:                 ← この部分全体をチェック
         1. Yes
         2. No

        Returns:
            True: "1. "と"2. "の両方が見つかった
            False: 選択肢が見つからなかった、または片方のみ
        """
        lines = content.split('\n')

        # 下から走査して、─────を見つける
        separator_indices = []
        for i, line in enumerate(lines):
            if '─' * 10 in line:  # 10文字以上の─────があれば区切り線と判定
                separator_indices.append(i)

        if len(separator_indices) >= 1:
            # 最後の区切り線より後の全てを取得
            last_separator_end = separator_indices[-1]
            options_area_lines = lines[last_separator_end + 1:]

            # 選択肢エリア全体を1つの文字列に結合
            options_text = '\n'.join(options_area_lines)

            # "1. "と"2. "の両方が含まれているかチェック
            has_option_1 = '1. ' in options_text
            has_option_2 = '2. ' in options_text

            return has_option_1 and has_option_2

        return False

    def _remove_user_input_area(self, content: str) -> str:
        """
        一番下からユーザー入力エリア（─────で囲まれた範囲）を除外

        パターン:
        ─────────────────────────────────────────────────────────────────
        > ユーザーの入力がここに来る
        ─────────────────────────────────────────────────────────────────
        """
        # 一番下から最初の─────ブロックを見つけて、それ以降を除外
        lines = content.split('\n')

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
        return content


if __name__ == "__main__":
    # テスト実行
    monitor = TerminalMonitor()
    sessions = monitor.detect_sessions()

    print(f"Found {len(sessions)} terminal sessions:")
    for session in sessions:
        print(f"  - {session.display_name} (Claude: {session.is_running_claude})")

        # 詳細分析
        monitor.analyze_session_status(session)
        print(f"    Status: {session.status}")
        print(f"    Last output: {session.last_output[:100]}...")
