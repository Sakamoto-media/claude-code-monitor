#!/usr/bin/env python3
"""
Claude Code Voice Controller - メインアプリケーション

複数のTerminal.appタブ/ウィンドウでClaude Codeを実行し、
音声で操作できるモニタリングシステム
"""
import sys
import threading
import time
import queue
from typing import List

# 標準出力のバッファリングを無効化（デバッグ用）
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from config import UPDATE_INTERVAL
from terminal_monitor import TerminalMonitor, TerminalSession
from gui import MonitorWindow
from voice_control import VoiceCommandHandler
from claude_parser import ClaudeOutputParser


class ClaudeCodeController:
    """メインコントローラー"""

    def __init__(self):
        self.terminal_monitor = TerminalMonitor()
        self.claude_parser = ClaudeOutputParser()
        self.gui_window = None
        self.voice_handler = None
        self.is_running = False
        self.update_thread = None
        self.update_queue = queue.Queue()  # スレッド間通信用キュー

    def start(self):
        """アプリケーションを起動"""
        print("Starting Claude Code Voice Controller...")

        # 初回のセッション検出
        sessions = self.terminal_monitor.detect_sessions()
        print(f"Found {len(sessions)} terminal sessions")

        # GUIウィンドウを作成
        self.gui_window = MonitorWindow(
            on_session_click=self.on_session_clicked,
            on_voice_command=self.on_voice_command
        )

        # 音声コマンドハンドラー初期化
        self.voice_handler = VoiceCommandHandler(
            self.terminal_monitor,
            self.gui_window
        )

        # 初期セッション表示
        self.gui_window.update_sessions(sessions)

        # バックグラウンド更新スレッド開始
        self.is_running = True
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

        print("Application started. Monitoring sessions...")

        # メインスレッドでキューチェックを定期実行
        self._check_updates()

        # GUIメインループ開始
        try:
            self.gui_window.run()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.stop()

    def stop(self):
        """アプリケーションを停止"""
        self.is_running = False
        if self.voice_handler:
            self.voice_handler.stop()
        print("Application stopped")

    def _check_updates(self):
        """メインスレッドでキューをチェックしてGUI更新（定期実行）"""
        try:
            # キューからデータを取得（ブロックしない）
            while not self.update_queue.empty():
                updated_sessions = self.update_queue.get_nowait()
                print(f"  [MainThread] Processing update from queue: {len(updated_sessions)} sessions")

                if self.gui_window:
                    self.gui_window.update_sessions(updated_sessions)
                    print(f"  [MainThread] GUI updated successfully")
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error in _check_updates: {e}")
            import traceback
            traceback.print_exc()

        # 次回のチェックをスケジュール（メインスレッドで実行）
        if self.is_running and self.gui_window:
            self.gui_window.root.after(100, self._check_updates)  # 100ms後に再実行

    def update_loop(self):
        """定期的にセッション情報を更新するループ"""
        iteration = 0
        while self.is_running:
            try:
                iteration += 1
                print(f"\n[Update {iteration}] Detecting sessions...")

                # セッションを再検出
                sessions = self.terminal_monitor.detect_sessions()
                print(f"  Found {len(sessions)} sessions")

                # 各セッションの詳細を分析
                updated_sessions = []
                for i, session in enumerate(sessions):
                    print(f"  Session {i+1}: {session.display_name} (Claude: {session.is_running_claude})")
                    print(f"    Before analysis - Output length: {len(session.last_output)}")

                    if session.is_running_claude:
                        # Claude Codeセッションは詳細分析
                        print(f"    Analyzing session content...")
                        updated_session = self.terminal_monitor.analyze_session_status(session)
                        print(f"    After analysis - Status: {updated_session.status}, Output length: {len(updated_session.last_output)}")
                        print(f"    Output preview: {updated_session.last_output[:100]!r}")
                        updated_sessions.append(updated_session)
                    else:
                        # 通常のセッションはそのまま
                        updated_sessions.append(session)

                # デバッグ: GUI更新前の最終確認
                print(f"  Passing {len(updated_sessions)} sessions to GUI queue:")
                for i, s in enumerate(updated_sessions):
                    print(f"    [{i+1}] {s.display_name}: output_len={len(s.last_output)}")

                # キューに更新データを投入（スレッドセーフ）
                self.update_queue.put(updated_sessions)
                print("  Data added to update queue")

            except Exception as e:
                print(f"Error in update loop: {e}")
                import traceback
                traceback.print_exc()

            # 次の更新まで待機
            time.sleep(UPDATE_INTERVAL / 1000)

    def on_session_clicked(self, session: TerminalSession):
        """セッションがクリックされたときの処理"""
        print(f"Switching to: {session.display_name}")

        success = self.terminal_monitor.switch_to_session(
            session.window_id,
            session.tab_index
        )

        if success:
            self.gui_window.show_notification(
                f"Switched to {session.display_name}",
                "success"
            )

            # 要約を読み上げ
            if session.is_running_claude and self.voice_handler:
                summary = self.claude_parser.summarize(session.last_output)
                self.voice_handler.voice_controller.speak_async(summary)
        else:
            self.gui_window.show_notification(
                "Failed to switch session",
                "error"
            )

    def on_voice_command(self):
        """音声コマンドが要求されたときの処理"""
        if not self.voice_handler:
            return

        # 音声ハンドラーが既に開始されている場合はスキップ
        if self.voice_handler.voice_controller.is_listening:
            return

        # 音声認識開始
        self.voice_handler.start()


def check_dependencies():
    """必要な依存関係をチェック"""
    missing_deps = []

    try:
        import speech_recognition
    except ImportError:
        missing_deps.append("SpeechRecognition")

    try:
        import pyaudio
    except ImportError:
        missing_deps.append("pyaudio")

    if missing_deps:
        print("警告: 以下の依存関係が不足しています:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nインストール方法:")
        print("  pip install -r requirements.txt")
        print("\n音声認識機能が制限される可能性があります。")
        print("続行しますか? (y/n): ", end="")

        response = input().lower()
        if response != 'y':
            sys.exit(1)


def main():
    """メインエントリーポイント"""
    print("=" * 50)
    print("Claude Code Voice Controller")
    print("=" * 50)
    print()

    # 依存関係チェック
    check_dependencies()

    # コントローラー起動
    controller = ClaudeCodeController()

    try:
        controller.start()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
