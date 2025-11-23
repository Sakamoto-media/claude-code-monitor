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
        self.session_map = {}  # {(window_id, tab_index): TerminalSession} セッション永続化用

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
                new_sessions = self.terminal_monitor.detect_sessions()
                print(f"  Found {len(new_sessions)} sessions")

                # display_order順にソート（ユーザーがドラッグ&ドロップで並び替えた順序）
                # display_orderが0の新規セッションは末尾に追加
                new_sessions_sorted = sorted(new_sessions, key=lambda s: (s.display_order if s.display_order > 0 else 9999, s.window_id, s.tab_index))
                print(f"  Sorted sessions by display_order:")
                for i, s in enumerate(new_sessions_sorted):
                    print(f"    [{i+1}] display_order={s.display_order}, window_id={s.window_id}, tab_index={s.tab_index}, name={s.display_name}")

                # 各セッションの詳細を分析（Claude Codeセッションのみ）
                updated_sessions = []
                for i, new_session in enumerate(new_sessions_sorted):
                    # Claude Codeセッション以外はスキップ
                    if not new_session.is_running_claude:
                        print(f"  Session {i+1}: {new_session.display_name} (Not Claude, skipping)")
                        continue

                    session_key = (new_session.window_id, new_session.tab_index)

                    # 既存セッションがあれば再利用
                    if session_key in self.session_map:
                        existing_session = self.session_map[session_key]
                        print(f"  Session {i+1}: {new_session.display_name} (Claude: {new_session.is_running_claude}) [Reusing existing]")
                        # 既存セッションの状態を新セッションに引き継ぐ
                        new_session.previous_output = existing_session.previous_output
                        new_session.summary = existing_session.summary
                        new_session.last_trigger_state = existing_session.last_trigger_state
                        new_session.display_order = existing_session.display_order  # 表示順序も引き継ぐ
                    else:
                        print(f"  Session {i+1}: {new_session.display_name} (Claude: {new_session.is_running_claude}) [New session]")

                    print(f"    Before analysis - Output length: {len(new_session.last_output)}")

                    # Claude Codeセッションは詳細分析
                    print(f"    Analyzing session content...")
                    updated_session = self.terminal_monitor.analyze_session_status(new_session)
                    print(f"    After analysis - Status: {updated_session.status}, Output length: {len(updated_session.last_output)}")
                    print(f"    Output preview: {updated_session.last_output[:100]!r}")

                    # 出力の末尾1000文字を比較（スクロール変動を無視）
                    current_tail = updated_session.last_output[-1000:] if len(updated_session.last_output) > 1000 else updated_session.last_output
                    previous_tail = updated_session.previous_output[-1000:] if len(updated_session.previous_output) > 1000 else updated_session.previous_output
                    output_changed = current_tail != previous_tail

                    if output_changed:
                        print(f"    Output changed (prev: {len(updated_session.previous_output)} -> now: {len(updated_session.last_output)})")
                        # 出力を解析して、要約が必要か判定
                        parsed = self.claude_parser.parse(updated_session.last_output)

                        # 回答完了（入力待ち状態）または選択肢がある場合のみ要約
                        if parsed.is_waiting_input or len(parsed.options) > 0:
                            # トリガー状態を文字列化（waiting + 選択肢数の組み合わせ）
                            current_trigger_state = f"waiting={parsed.is_waiting_input},options={len(parsed.options)}"

                            # 前回と同じトリガー状態なら要約不要
                            if current_trigger_state == updated_session.last_trigger_state:
                                print(f"    Trigger state unchanged ({current_trigger_state}), skipping summary")
                            else:
                                print(f"    Trigger detected: waiting_input={parsed.is_waiting_input}, options={len(parsed.options)}")
                                print(f"    Generating summary...")
                                updated_session.summary = self.claude_parser.summarize(updated_session.last_output)
                                print(f"    Summary generated: {updated_session.summary[:50]}...")
                                updated_session.last_trigger_state = current_trigger_state
                        else:
                            print(f"    No trigger detected (still processing), keeping previous summary")

                        # 前回の出力を更新
                        updated_session.previous_output = updated_session.last_output
                    else:
                        print(f"    Output unchanged, no summary update needed")

                    # セッションマップを更新
                    self.session_map[session_key] = updated_session
                    updated_sessions.append(updated_session)

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
        print(f"\n[CLICK] ===== on_session_clicked called =====")
        print(f"  display_name: {session.display_name}")
        print(f"  window_id: {session.window_id}")
        print(f"  tab_index: {session.tab_index}")
        print(f"  tab_name: {session.tab_name}")

        # 現在のウィンドウフォーカス状態をチェック
        if self.gui_window:
            try:
                focus_widget = self.gui_window.root.focus_get()
                print(f"  [FOCUS] Current focus widget: {focus_widget}")
            except Exception as e:
                print(f"  [FOCUS] Could not get focus widget: {e}")

        print(f"[CLICK] Calling switch_to_session...")
        success = self.terminal_monitor.switch_to_session(
            session.window_id,
            session.tab_index
        )
        print(f"[CLICK] switch_to_session returned: {success}")

        # フォーカスチェックのみ（強制的には奪わない）
        if self.gui_window:
            try:
                focus_widget = self.gui_window.root.focus_get()
                print(f"  [FOCUS-AFTER] Focus widget after switch: {focus_widget}")
            except Exception as e:
                print(f"  [FOCUS-AFTER] Could not get focus: {e}")

        if success:
            print(f"[CLICK] Switch successful (background mode - GUI keeps focus)")

            self.gui_window.show_notification(
                f"Switched to {session.display_name}",
                "success"
            )

            # 要約を読み上げ（削除）
            # if session.is_running_claude and self.voice_handler:
            #     summary = self.claude_parser.summarize(session.last_output)
            #     self.voice_handler.voice_controller.speak_async(summary)
        else:
            print(f"[CLICK] Switch FAILED")
            self.gui_window.show_notification(
                "Failed to switch session",
                "error"
            )

        print(f"[CLICK] ===== on_session_clicked done =====\n")

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
