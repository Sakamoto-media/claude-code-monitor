"""
音声認識と音声合成を統合したモジュール
"""
import subprocess
import threading
from typing import Optional, Callable, List
from datetime import datetime
import queue

try:
    import speech_recognition as sr
except ImportError:
    print("Warning: speech_recognition not installed. Voice input will not work.")
    sr = None

from config import VOICE_LANGUAGE, VOICE_COMMANDS


class VoiceController:
    """音声入力・出力を制御するクラス"""

    def __init__(self):
        self.recognizer = sr.Recognizer() if sr else None
        self.microphone = sr.Microphone() if sr else None
        self.is_listening = False
        self.command_queue = queue.Queue()

        # マイクの調整
        if self.recognizer and self.microphone:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)

    def start_listening(self, callback: Callable[[str], None]):
        """音声入力を開始（バックグラウンド）"""
        if not self.recognizer or not self.microphone:
            print("Error: Speech recognition not available")
            return

        self.is_listening = True

        def listen_loop():
            while self.is_listening:
                try:
                    with self.microphone as source:
                        print("Listening...")
                        audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)

                    try:
                        # Google Speech RecognitionAPIを使用（オフラインの場合はsphinxも可能）
                        text = self.recognizer.recognize_google(audio, language=VOICE_LANGUAGE)
                        print(f"Recognized: {text}")

                        # コールバックを実行
                        callback(text)

                    except sr.UnknownValueError:
                        print("Could not understand audio")
                    except sr.RequestError as e:
                        print(f"Recognition error: {e}")

                except Exception as e:
                    print(f"Listening error: {e}")

        # バックグラウンドスレッドで実行
        thread = threading.Thread(target=listen_loop, daemon=True)
        thread.start()

    def stop_listening(self):
        """音声入力を停止"""
        self.is_listening = False

    def parse_command(self, text: str) -> Optional[dict]:
        """
        音声テキストからコマンドを解析
        戻り値: {"type": "switch_tab", "direction": "next"} など
        """
        text = text.lower()

        # タブ切り替え
        if any(keyword in text for keyword in VOICE_COMMANDS["タブ切り替え"]):
            return {"type": "switch_tab", "direction": "next"}

        if any(keyword in text for keyword in VOICE_COMMANDS["前のタブ"]):
            return {"type": "switch_tab", "direction": "prev"}

        # 要約・読み上げ
        if any(keyword in text for keyword in VOICE_COMMANDS["要約"]):
            return {"type": "summarize"}

        # 選択肢
        for i in range(1, 5):
            if any(keyword in text for keyword in VOICE_COMMANDS[f"選択{i}"]):
                return {"type": "select_option", "option": i}

        # 更新
        if any(keyword in text for keyword in VOICE_COMMANDS["更新"]):
            return {"type": "refresh"}

        # 特定のタブ番号
        import re
        tab_match = re.search(r'タブ\s*(\d+)', text)
        if tab_match:
            tab_num = int(tab_match.group(1))
            return {"type": "switch_to_tab", "tab_number": tab_num}

        # ウィンドウ番号
        window_match = re.search(r'ウィンドウ\s*(\d+)', text)
        if window_match:
            window_num = int(window_match.group(1))
            return {"type": "switch_to_window", "window_number": window_num}

        # コマンドとして認識できない場合は、そのままテキストとして返す
        return {"type": "text_input", "text": text}

    def speak(self, text: str, rate: int = 200):
        """
        テキストを音声で読み上げ（macOSの`say`コマンドを使用）

        Args:
            text: 読み上げるテキスト
            rate: 読み上げ速度（デフォルト: 200 wpm）
        """
        try:
            # macOSの`say`コマンドを使用
            # -v: 音声（日本語はKyoko）
            # -r: 速度（words per minute）
            subprocess.Popen(
                ['say', '-v', 'Kyoko', '-r', str(rate), text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"TTS error: {e}")

    def speak_async(self, text: str, rate: int = 200):
        """非同期で音声読み上げ"""
        thread = threading.Thread(target=self.speak, args=(text, rate), daemon=True)
        thread.start()


class VoiceCommandHandler:
    """音声コマンドを処理するハンドラー"""

    def __init__(self, terminal_monitor, gui_window):
        self.terminal_monitor = terminal_monitor
        self.gui_window = gui_window
        self.voice_controller = VoiceController()
        self.current_session_index = 0

    def start(self):
        """音声コマンド処理を開始"""
        self.voice_controller.start_listening(self.on_voice_input)

    def stop(self):
        """音声コマンド処理を停止"""
        self.voice_controller.stop_listening()

    def on_voice_input(self, text: str):
        """音声入力を受け取ったときの処理"""
        command = self.voice_controller.parse_command(text)

        if not command:
            return

        command_type = command.get("type")

        if command_type == "switch_tab":
            self._handle_switch_tab(command["direction"])

        elif command_type == "switch_to_tab":
            self._handle_switch_to_tab(command["tab_number"])

        elif command_type == "switch_to_window":
            self._handle_switch_to_window(command["window_number"])

        elif command_type == "summarize":
            self._handle_summarize()

        elif command_type == "select_option":
            self._handle_select_option(command["option"])

        elif command_type == "refresh":
            self._handle_refresh()

        elif command_type == "text_input":
            self._handle_text_input(command["text"])

    def _handle_switch_tab(self, direction: str):
        """タブ切り替え"""
        sessions = self.terminal_monitor.sessions

        if not sessions:
            self.voice_controller.speak_async("セッションがありません")
            return

        if direction == "next":
            self.current_session_index = (self.current_session_index + 1) % len(sessions)
        else:  # prev
            self.current_session_index = (self.current_session_index - 1) % len(sessions)

        session = sessions[self.current_session_index]
        success = self.terminal_monitor.switch_to_session(
            session.window_id,
            session.tab_index
        )

        if success:
            self.voice_controller.speak_async(f"タブ{self.current_session_index + 1}に切り替えました")
            self.gui_window.show_notification(f"Switched to {session.display_name}", "success")

    def _handle_switch_to_tab(self, tab_number: int):
        """指定されたタブ番号に切り替え"""
        sessions = self.terminal_monitor.sessions

        if tab_number < 1 or tab_number > len(sessions):
            self.voice_controller.speak_async("無効なタブ番号です")
            return

        self.current_session_index = tab_number - 1
        session = sessions[self.current_session_index]

        success = self.terminal_monitor.switch_to_session(
            session.window_id,
            session.tab_index
        )

        if success:
            self.voice_controller.speak_async(f"タブ{tab_number}に切り替えました")
            self.gui_window.show_notification(f"Switched to {session.display_name}", "success")

    def _handle_switch_to_window(self, window_number: int):
        """指定されたウィンドウに切り替え"""
        # ウィンドウ番号でフィルタ
        sessions = [s for s in self.terminal_monitor.sessions if s.window_id == window_number]

        if not sessions:
            self.voice_controller.speak_async(f"ウィンドウ{window_number}が見つかりません")
            return

        # 最初のタブに切り替え
        session = sessions[0]
        success = self.terminal_monitor.switch_to_session(
            session.window_id,
            session.tab_index
        )

        if success:
            self.voice_controller.speak_async(f"ウィンドウ{window_number}に切り替えました")
            self.gui_window.show_notification(f"Switched to Window {window_number}", "success")

    def _handle_summarize(self):
        """現在のセッションを要約して読み上げ"""
        sessions = self.terminal_monitor.sessions

        if not sessions or self.current_session_index >= len(sessions):
            self.voice_controller.speak_async("セッションがありません")
            return

        session = sessions[self.current_session_index]

        # 最新の出力を取得
        from claude_parser import ClaudeOutputParser
        parser = ClaudeOutputParser()

        summary = parser.summarize(session.last_output, max_length=200)
        self.voice_controller.speak_async(summary)

        self.gui_window.show_notification("Reading summary...", "info")

    def _handle_select_option(self, option_number: int):
        """選択肢を選択"""
        sessions = self.terminal_monitor.sessions

        if not sessions or self.current_session_index >= len(sessions):
            self.voice_controller.speak_async("セッションがありません")
            return

        session = sessions[self.current_session_index]

        # 選択肢番号を送信
        success = self.terminal_monitor.send_text_to_tab(
            session.window_id,
            session.tab_index,
            str(option_number)
        )

        if success:
            self.voice_controller.speak_async(f"選択肢{option_number}を選びました")
            self.gui_window.show_notification(f"Selected option {option_number}", "success")

    def _handle_refresh(self):
        """セッションリストを更新"""
        self.voice_controller.speak_async("更新中です")
        # 更新はメインループで自動的に行われる
        self.gui_window.show_notification("Refreshing...", "info")

    def _handle_text_input(self, text: str):
        """テキストを現在のセッションに入力"""
        sessions = self.terminal_monitor.sessions

        if not sessions or self.current_session_index >= len(sessions):
            self.voice_controller.speak_async("セッションがありません")
            return

        session = sessions[self.current_session_index]

        success = self.terminal_monitor.send_text_to_tab(
            session.window_id,
            session.tab_index,
            text
        )

        if success:
            self.voice_controller.speak_async("送信しました")
            self.gui_window.show_notification(f"Sent: {text}", "success")


if __name__ == "__main__":
    # テスト
    controller = VoiceController()

    def on_voice(text):
        print(f"Voice input: {text}")
        command = controller.parse_command(text)
        print(f"Parsed command: {command}")

    print("Starting voice recognition test... (Speak in Japanese)")
    controller.start_listening(on_voice)

    # 10秒間待機
    import time
    time.sleep(10)

    controller.stop_listening()
    print("Test completed")
