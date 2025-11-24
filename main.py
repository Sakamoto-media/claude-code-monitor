#!/usr/bin/env python3
"""
Claude Code Monitor - メインアプリケーション

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

# 起動時チェックを実行
from startup_check import run_startup_check
startup_checker = run_startup_check()

from config import UPDATE_INTERVAL
from terminal_monitor import TerminalMonitor, TerminalSession
from gui import MonitorWindow
from claude_parser import ClaudeOutputParser


class ClaudeCodeController:
    """メインコントローラー"""

    def __init__(self):
        self.terminal_monitor = TerminalMonitor()
        self.claude_parser = ClaudeOutputParser()
        self.gui_window = None
        self.is_running = False
        self.update_thread = None
        self.update_queue = queue.Queue()  # スレッド間通信用キュー
        self.session_map = {}  # {(window_id, tab_index): TerminalSession} セッション永続化用
        self.next_display_order = 1  # 次に割り当てるdisplay_order
        self.force_update_flag = False  # 強制更新フラグ

    def start(self):
        """アプリケーションを起動"""
        print("Starting Claude Code Monitor...")

        # 初回のセッション検出
        sessions = self.terminal_monitor.detect_sessions()
        print(f"Found {len(sessions)} terminal sessions")

        # Claude Codeセッションのみ抽出してID順にソート
        claude_sessions = [s for s in sessions if s.is_running_claude]
        claude_sessions_sorted = sorted(claude_sessions, key=lambda s: s.window_id)
        print(f"Claude Code sessions: {len(claude_sessions_sorted)}")

        # 初回のdisplay_orderを割り当て、かつ詳細情報を取得
        for i, session in enumerate(claude_sessions_sorted, start=1):
            session.display_order = i

            # analyze_session_statusを呼び出して実際の出力を取得
            analyzed_session = self.terminal_monitor.analyze_session_status(session)

            # 起動時は要約を生成せず、"~要約中~"と表示
            if analyzed_session.last_output:
                analyzed_session.summary = "~要約中~"
                print(f"  Initial session marked for summarization")

            session_key = (analyzed_session.window_id, analyzed_session.tab_index)
            self.session_map[session_key] = analyzed_session
            print(f"  Initial session [{i}]: window_id={analyzed_session.window_id}, display_order={analyzed_session.display_order}, output_len={len(analyzed_session.last_output)}")

            # ソート済みリストも更新
            claude_sessions_sorted[i-1] = analyzed_session

        self.next_display_order = len(claude_sessions_sorted) + 1

        # API設定状態を確認
        api_key_configured = self.claude_parser.api_client is not None

        # GUIウィンドウを作成
        self.gui_window = MonitorWindow(
            on_session_click=self.on_session_clicked,
            on_reorder_complete=self.on_reorder_complete,
            on_force_update=self.on_force_update,
            api_key_configured=api_key_configured,
            missing_packages=startup_checker.missing_packages if startup_checker else []
        )

        # 初期セッション表示（要約なしで即座に表示）
        self.gui_window.update_sessions(claude_sessions_sorted)

        # 起動フラグ（最初の1回は必ず要約を生成）
        self.is_first_update = True

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
                # 強制更新フラグがセットされている場合は即座に実行
                if self.force_update_flag:
                    print(f"\n[FORCE UPDATE] Executing forced update...")
                    self.force_update_flag = False
                else:
                    # 通常は1秒待機
                    time.sleep(UPDATE_INTERVAL / 1000)

                iteration += 1
                print(f"\n[Update {iteration}] Detecting sessions...")

                # セッションを再検出
                new_sessions = self.terminal_monitor.detect_sessions()
                print(f"  Found {len(new_sessions)} sessions")

                # Claude Codeセッションのみを抽出
                claude_sessions = [s for s in new_sessions if s.is_running_claude]
                print(f"  Claude Code sessions: {len(claude_sessions)}")

                # 各セッションの詳細を分析
                updated_sessions = []
                for new_session in claude_sessions:
                    session_key = (new_session.window_id, new_session.tab_index)

                    # 既存セッションがあれば再利用
                    if session_key in self.session_map:
                        existing_session = self.session_map[session_key]
                        print(f"  Session: {new_session.display_name} (window_id={new_session.window_id}) [Reusing existing]")
                        # 既存セッションの状態を新セッションに引き継ぐ
                        new_session.previous_output = existing_session.previous_output
                        new_session.summary = existing_session.summary
                        new_session.last_trigger_state = existing_session.last_trigger_state
                        new_session.display_order = existing_session.display_order  # 表示順序も引き継ぐ
                    else:
                        # 新規セッション: display_orderを割り当てて末尾に追加
                        new_session.display_order = self.next_display_order
                        self.next_display_order += 1
                        print(f"  Session: {new_session.display_name} (window_id={new_session.window_id}) [New session, display_order={new_session.display_order}]")

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

                    # 前回のセッション状態を取得（新規セッションの判定にも使用）
                    is_new_session = session_key not in self.session_map
                    if not is_new_session:
                        previous_status = self.session_map[session_key].status
                    else:
                        previous_status = None
                        print(f"    [NEW SESSION] Detected new session, will not trigger speech")

                    current_status = updated_session.status

                    # 起動時は必ず要約を生成、それ以外は状態がidleまたはwaitingに切り替わった時のみ
                    status_changed_to_idle_or_waiting = (
                        previous_status is not None and
                        previous_status != current_status and
                        (current_status == "idle" or current_status == "waiting")
                    )

                    if output_changed:
                        print(f"    Output changed (prev: {len(updated_session.previous_output)} -> now: {len(updated_session.last_output)})")

                        # 起動時は必ず要約生成、それ以外は状態変化時のみ
                        if self.is_first_update or status_changed_to_idle_or_waiting:
                            if self.is_first_update:
                                print(f"    Initial startup: generating summary...")
                            else:
                                print(f"    Status changed: {previous_status} -> {current_status}, generating summary...")

                            # 要約を生成
                            updated_session.summary = self.claude_parser.summarize(updated_session.last_output)
                            print(f"    Summary generated: {updated_session.summary[:50]}...")
                            updated_session.last_trigger_state = current_status

                            # 要約生成完了後に読み上げ（起動時以外、かつ新規セッションでない場合のみ）
                            if not self.is_first_update:
                                if self.gui_window and previous_status and not is_new_session:
                                    print(f"    [TTS] Triggering speech for status change (after summary)")
                                    self.gui_window.speak_status_change(updated_session, previous_status)
                                elif is_new_session:
                                    print(f"    [TTS] Skipping speech - new session detected")
                        else:
                            print(f"    Status: {current_status} (no state change to idle/waiting), keeping previous summary")

                        # 前回の出力を更新
                        updated_session.previous_output = updated_session.last_output
                    else:
                        print(f"    Output unchanged, no summary update needed")

                    # セッションマップを更新
                    self.session_map[session_key] = updated_session
                    updated_sessions.append(updated_session)

                # display_order順にソート
                updated_sessions_sorted = sorted(updated_sessions, key=lambda s: s.display_order)

                # デバッグ: GUI更新前の最終確認
                print(f"  Passing {len(updated_sessions_sorted)} sessions to GUI queue (sorted by display_order):")
                for i, s in enumerate(updated_sessions_sorted):
                    print(f"    [{i+1}] display_order={s.display_order}, {s.display_name}: output_len={len(s.last_output)}")

                # キューに更新データを投入（スレッドセーフ）
                self.update_queue.put(updated_sessions_sorted)
                print("  Data added to update queue")

                # 起動時フラグをクリア
                if self.is_first_update:
                    self.is_first_update = False
                    print("  [STARTUP] First update completed, initial summaries generated")

            except Exception as e:
                print(f"Error in update loop: {e}")
                import traceback
                traceback.print_exc()
                # エラー時も待機を継続
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
        else:
            print(f"[CLICK] Switch FAILED")
            self.gui_window.show_notification(
                "Failed to switch session",
                "error"
            )

        print(f"[CLICK] ===== on_session_clicked done =====\n")

    def on_reorder_complete(self, sessions: List[TerminalSession]):
        """GUIでカードの並び替えが完了したときの処理"""
        print(f"\n[REORDER] ===== on_reorder_complete called =====")
        # session_mapのdisplay_orderを更新
        for session in sessions:
            session_key = (session.window_id, session.tab_index)
            if session_key in self.session_map:
                self.session_map[session_key].display_order = session.display_order
                print(f"  Updated session_map: {session.display_name}, display_order={session.display_order}")
        print(f"[REORDER] ===== on_reorder_complete done =====\n")

    def on_force_update(self):
        """GUIから強制更新を要求されたときの処理"""
        print(f"\n[FORCE UPDATE] Force update requested")
        self.force_update_flag = True


def check_dependencies():
    """必要な依存関係をチェック"""
    # 現在は特別な依存関係チェックは不要
    # tkinterはPython標準ライブラリ
    # anthropicはclaudeParserで任意
    pass


def main():
    """メインエントリーポイント"""
    print("=" * 50)
    print("Claude Code Monitor")
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
