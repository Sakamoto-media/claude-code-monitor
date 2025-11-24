"""
縦長モニタリングウィンドウのGUI
"""
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import List, Callable, Optional
from datetime import datetime
import threading
import subprocess
import os
import json

from config import COLORS, WINDOW_WIDTH, WINDOW_HEIGHT, UPDATE_INTERVAL, APP_NAME
from terminal_monitor import TerminalSession


class SessionCard(tk.Frame):
    """各セッションを表示するカード"""

    def __init__(self, parent, session: TerminalSession, on_click: Callable, on_reorder: Callable = None, monitor_window=None):
        # 外側フレーム = 枠の色（ネストフレーム方式）
        super().__init__(parent, bg="#3a3a3a", bd=0, relief=tk.FLAT)
        self.session = session
        self.on_click = on_click
        self.on_reorder = on_reorder  # ドラッグ&ドロップによる並び替えコールバック
        self.monitor_window = monitor_window  # MonitorWindowへの参照
        self.border_frame = self  # 外側フレーム（枠の色用）
        self.drag_start_y = 0  # ドラッグ開始位置
        self.is_dragging = False  # ドラッグ中フラグ

        print(f"[DEBUG] SessionCard.__init__: {session.display_name}, status={session.status}")

        # 内側フレーム = コンテンツ（padding 3pxで枠を作る）
        self.content_frame = tk.Frame(self, bg=COLORS["bg"])
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

        # 状態に応じた枠の色を設定
        self._update_border_color()

        self._build_ui()
        self._bind_click_events()
        self._bind_drag_events()

    def _build_ui(self):
        """UIを構築"""
        # ヘッダー部分（content_frameに配置）
        header_frame = tk.Frame(self.content_frame, bg=COLORS["bg"])
        header_frame.pack(fill=tk.X, padx=10, pady=5)

        # セッション名（タブ名 + ウィンドウID）
        display_text = f"{self.session.display_name} [{self.session.window_id}]"
        self.name_label = tk.Label(
            header_frame,
            text=display_text,
            font=("Arial", 10, "bold"),
            fg=COLORS["fg"],
            bg=COLORS["bg"],
            anchor="w"
        )
        self.name_label.pack(side=tk.LEFT)

        # 状態表示（右上）
        status_text = f"Status: {self.session.status}"
        self.time_label = tk.Label(
            header_frame,
            text=status_text,
            font=("Arial", 8),
            fg="#888888",
            bg=COLORS["bg"],
            anchor="e"
        )
        self.time_label.pack(side=tk.RIGHT)

        # 進捗情報
        if self.session.todo_progress:
            progress_frame = tk.Frame(self.content_frame, bg=COLORS["bg"])
            progress_frame.pack(fill=tk.X, padx=10, pady=2)

            progress_label = tk.Label(
                progress_frame,
                text=f"📋 {self.session.todo_progress}",
                font=("Arial", 10),
                fg=COLORS["fg"],
                bg=COLORS["bg"],
                anchor="w"
            )
            progress_label.pack(side=tk.LEFT)

        # 最新出力プレビュー（スクロールなし）
        # MonitorWindowから初期高さを取得
        initial_height = self.monitor_window.summary_area_height if self.monitor_window else 120
        self.output_frame = tk.Frame(self.content_frame, bg=COLORS["bg"], height=initial_height)
        self.output_frame.pack(fill=tk.X, padx=10, pady=5)
        self.output_frame.pack_propagate(False)  # 子要素によるサイズ変更を防止

        self.output_text = tk.Text(
            self.output_frame,
            font=("Courier", 8),
            fg="#cccccc",
            bg="#2a2a2a",
            wrap=tk.WORD,
            relief=tk.FLAT,
            borderwidth=0,
            state=tk.DISABLED,  # フォーカスを受け取らない、編集不可
            takefocus=0  # タブキーでもフォーカスされない
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)

        # 初期テキストを挿入（表示モードに応じて）
        self._update_output_display()
        print(f"    SessionCard created for {self.session.display_name}")

    def _bind_click_events(self):
        """クリックイベントを全ての子ウィジェットにバインド"""
        # クリックイベントは_bind_drag_eventsで統合処理するため、ここでは何もしない
        pass

    def _bind_drag_events(self):
        """ドラッグ&ドロップとクリックイベントを統合バインド"""
        def on_press(event):
            self.drag_start_y = event.y_root
            self.is_dragging = False
            print(f"[INPUT] Button press on {self.session.display_name} at y={event.y_root}")

        def on_motion(event):
            delta_y = event.y_root - self.drag_start_y
            if abs(delta_y) > 5:  # 5ピクセル以上移動したらドラッグ開始
                if not self.is_dragging:
                    self.is_dragging = True
                    if self.monitor_window:
                        self.monitor_window.is_any_card_dragging = True
                    print(f"[DRAG] Start dragging {self.session.display_name}, update paused")
                self.config(cursor="hand2")

        def on_release(event):
            delta_y = event.y_root - self.drag_start_y
            print(f"[INPUT] Button release on {self.session.display_name}, delta_y={delta_y}, is_dragging={self.is_dragging}")

            if self.is_dragging:
                # ドラッグ処理
                self.config(cursor="")
                if abs(delta_y) > 20 and self.on_reorder:
                    direction = "up" if delta_y < 0 else "down"
                    print(f"[DRAG] Reordering {direction}")
                    self.on_reorder(self.session, direction)
                self.is_dragging = False
                if self.monitor_window:
                    self.monitor_window.is_any_card_dragging = False
                    print(f"[DRAG] End dragging, update resumed")
            else:
                # クリック処理（移動距離が小さい場合）
                print(f"[CLICK] Detected click on {self.session.display_name}")
                try:
                    self.on_click(self.session)
                    print(f"[CLICK] on_click callback completed")
                except Exception as ex:
                    print(f"[CLICK] ERROR in on_click: {ex}")
                    import traceback
                    traceback.print_exc()

        # 再帰的に全てのウィジェットにイベントをバインド
        def bind_recursive(widget):
            widget_class = widget.__class__.__name__

            # Scrollbarのみスキップ（スクロール操作のため）
            # ScrolledTextにはバインドして、クリック＆ドラッグを有効にする
            if widget_class == "Scrollbar":
                return

            widget.bind("<ButtonPress-1>", on_press)
            widget.bind("<B1-Motion>", on_motion)
            widget.bind("<ButtonRelease-1>", on_release)

            # 子ウィジェットに再帰
            try:
                for child in widget.winfo_children():
                    bind_recursive(child)
            except:
                pass

        # カード全体にバインド
        bind_recursive(self)

    def _update_border_color(self):
        """状態に応じた枠の色を設定"""
        print(f"[DEBUG] _update_border_color: {self.session.display_name}, status={self.session.status}")

        # テスト用に分かりやすい色を使用
        if self.session.status == "active":
            border_color = "#00ff00"  # 明るい緑（回答中）- テスト用
        elif self.session.status == "waiting":
            border_color = "#ffff00"  # 黄色（入力待ち）- テスト用
        else:
            border_color = "#3a3a3a"  # 暗いグレー（アイドル）

        print(f"  -> border_color={border_color}")

        # ネストフレーム方式：外側フレームの背景色を変更
        self.border_frame.config(bg=border_color)
        print(f"  -> config applied (nested frame bg)")

    def _truncate_output(self, text: str, max_length: int = 150) -> str:
        """出力を切り詰める"""
        if not text:
            return "(No output)"

        text = text.strip()
        if len(text) > max_length:
            return text[-max_length:] + "..."
        return text

    def _update_output_display(self):
        """要約を表示"""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)

        # Claude APIによる要約を表示
        if self.session.summary:
            # Claude APIで生成された要約を使用（改行はそのまま保持）
            summary_text = self.session.summary.strip()

            print(f"    Summary mode (API): {self.session.display_name}, showing API summary")
        else:
            # フォールバック：要約がない場合は簡易サマリー
            full_output = self.session.last_output if self.session.last_output else ""
            summary_parts = []
            summary_parts.append(f"Status: {self.session.status}")

            if self.session.todo_progress:
                summary_parts.append(f"Progress: {self.session.todo_progress}")

            # 最新100文字を追加
            if full_output:
                lines = full_output.strip().split('\n')
                relevant_lines = [line for line in reversed(lines) if line.strip() and not line.startswith('$')][:3]
                relevant_lines.reverse()

                if relevant_lines:
                    latest = '\n'.join(relevant_lines)
                    if len(latest) > 100:
                        latest = latest[-100:]
                    summary_parts.append(f"\nLatest output:\n{latest}")
                else:
                    summary_parts.append("\n(No recent output)")
            else:
                summary_parts.append("\n(No output)")

            summary_text = '\n'.join(summary_parts)
            print(f"    Summary mode (fallback): {self.session.display_name}, showing fallback summary")

        self.output_text.insert("1.0", summary_text)

        # 最下部にスクロール
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)

    def update_output_frame_height(self, height: int):
        """要約エリアの高さを更新"""
        if hasattr(self, 'output_frame'):
            self.output_frame.config(height=height)
            print(f"    Updated output_frame height for {self.session.display_name}: {height}px")

    def update_session(self, session: TerminalSession):
        """セッション情報を更新"""
        old_status = self.session.status
        old_name = self.session.display_name
        old_window_id = self.session.window_id
        old_tab_index = self.session.tab_index

        self.session = session

        print(f"[DEBUG] update_session: {old_name} -> {session.display_name}")
        print(f"  Old: window_id={old_window_id}, tab_index={old_tab_index}, status={old_status}")
        print(f"  New: window_id={session.window_id}, tab_index={session.tab_index}, status={session.status}")

        # 各要素を更新（ウィンドウID）
        display_text = f"{session.display_name} [{session.window_id}]"
        self.name_label.config(text=display_text)

        # 枠の色を更新（状態に応じて）
        self._update_border_color()

        # 表示モードに応じて出力を更新
        self._update_output_display()

        # 状態表示を更新（Updatedは表示しない）
        status_text = f"Status: {session.status}"
        self.time_label.config(text=status_text)

        # クリックイベントを再バインド（更新後も確実にクリック可能に）
        self._bind_click_events()
        print(f"[DEBUG] Click events rebound for {session.display_name}")


class MonitorWindow:
    """メインモニタリングウィンドウ"""

    def __init__(self, on_session_click: Callable, on_reorder_complete: Optional[Callable] = None, on_force_update: Optional[Callable] = None, api_key_configured: bool = False):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg=COLORS["bg"])
        self.on_session_click = on_session_click
        self.on_reorder_complete = on_reorder_complete
        self.on_force_update = on_force_update
        self.api_key_configured = api_key_configured

        # macOS Tk 9.0バグ回避: ウィンドウを一旦非表示にしてから表示
        # マウスポインタがウィンドウ内にある状態で表示されると、キーウィンドウになれない
        self.root.withdraw()

        # 初回表示時のみフォーカスを取得（その後は奪わない）
        self._initial_focus_done = False

        # ドラッグ中フラグ（更新処理の一時停止用）
        self.is_any_card_dragging = False

        # 設定ファイルのパス
        self.config_file_path = "config.json"

        # 設定を読み込む
        self._load_settings()

        # 音声読み上げプロセス管理
        self.tts_process = None  # 現在の読み上げプロセス
        self.tts_thread = None  # 読み上げスレッド
        self.tts_stop_flag = False  # 読み上げ中断フラグ

        # メニューバーを作成
        self._create_menu_bar()

        def _initial_focus():
            if not self._initial_focus_done:
                self.root.deiconify()
                self.root.focus_force()
                self._initial_focus_done = True
                print("[DEBUG] Initial window focus set")

        # 50ms後に初回フォーカス設定
        self.root.after(50, _initial_focus)

        self.session_cards: List[SessionCard] = []

        self._build_ui()

    def _load_settings(self):
        """設定ファイルから設定を読み込む"""
        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                gui_settings = config.get('gui_settings', {})

                # 各設定を読み込み（デフォルト値を指定）
                self.always_on_top = gui_settings.get('always_on_top', True)
                self.summary_area_height = gui_settings.get('summary_area_height', 120)
                self.tts_mode = gui_settings.get('tts_mode', 'none')
                self.tts_include_summary = gui_settings.get('tts_include_summary', True)
                self.tts_speed = gui_settings.get('tts_speed', 1.0)

                # 最前面固定を適用
                self.root.attributes('-topmost', self.always_on_top)

                print(f"[CONFIG] Settings loaded from {self.config_file_path}")
                print(f"  always_on_top={self.always_on_top}")
                print(f"  summary_area_height={self.summary_area_height}")
                print(f"  tts_mode={self.tts_mode}")
                print(f"  tts_include_summary={self.tts_include_summary}")
                print(f"  tts_speed={self.tts_speed}")
        except FileNotFoundError:
            print(f"[CONFIG] Config file not found, using defaults")
            self._set_default_settings()
        except json.JSONDecodeError as e:
            print(f"[CONFIG] Error parsing config file: {e}, using defaults")
            self._set_default_settings()
        except Exception as e:
            print(f"[CONFIG] Error loading settings: {e}, using defaults")
            self._set_default_settings()

    def _set_default_settings(self):
        """デフォルト設定を適用"""
        self.always_on_top = True
        self.summary_area_height = 120
        self.tts_mode = "none"
        self.tts_include_summary = True
        self.tts_speed = 1.0
        self.root.attributes('-topmost', self.always_on_top)

    def _save_settings(self):
        """設定をファイルに保存"""
        try:
            # 既存の設定を読み込む
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # GUI設定を更新
            config['gui_settings'] = {
                'always_on_top': self.always_on_top,
                'summary_area_height': self.summary_area_height,
                'tts_mode': self.tts_mode,
                'tts_include_summary': self.tts_include_summary,
                'tts_speed': self.tts_speed
            }

            # ファイルに書き込み
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            print(f"[CONFIG] Settings saved to {self.config_file_path}")
        except Exception as e:
            print(f"[CONFIG] Error saving settings: {e}")

    def _create_menu_bar(self):
        """メニューバーを作成"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # Viewメニュー
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)

        # 最前面固定のチェックボックス
        self.topmost_var = tk.BooleanVar(value=self.always_on_top)
        view_menu.add_checkbutton(
            label="Always on Top",
            variable=self.topmost_var,
            command=self._toggle_always_on_top
        )

        view_menu.add_separator()

        # 要約エリアの高さ
        summary_height_menu = tk.Menu(view_menu, tearoff=0)
        view_menu.add_cascade(label="Summary Area Height", menu=summary_height_menu)

        self.summary_height_var = tk.IntVar(value=self.summary_area_height)
        for height in [60, 80, 100, 120, 150, 180, 220, 260, 300]:
            summary_height_menu.add_radiobutton(
                label=f"{height}px",
                variable=self.summary_height_var,
                value=height,
                command=self._set_summary_area_height
            )

        # Audioメニュー
        audio_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Audio", menu=audio_menu)

        # 読み上げモード選択
        self.tts_mode_var = tk.StringVar(value=self.tts_mode)
        audio_menu.add_radiobutton(
            label="No Speech",
            variable=self.tts_mode_var,
            value="none",
            command=self._set_tts_mode
        )
        audio_menu.add_radiobutton(
            label="Apple TTS",
            variable=self.tts_mode_var,
            value="apple",
            command=self._set_tts_mode
        )
        audio_menu.add_radiobutton(
            label="VOICEVOX (Zundamon)",
            variable=self.tts_mode_var,
            value="voicevox",
            command=self._set_tts_mode
        )

        audio_menu.add_separator()

        # 要約読み上げのチェックボックス
        self.tts_summary_var = tk.BooleanVar(value=self.tts_include_summary)
        audio_menu.add_checkbutton(
            label="Include Summary",
            variable=self.tts_summary_var,
            command=self._toggle_tts_summary
        )

        audio_menu.add_separator()

        # 読み上げ速度
        speed_menu = tk.Menu(audio_menu, tearoff=0)
        audio_menu.add_cascade(label="Speed", menu=speed_menu)

        self.tts_speed_var = tk.DoubleVar(value=self.tts_speed)
        speed_menu.add_radiobutton(
            label="0.5x (Slow)",
            variable=self.tts_speed_var,
            value=0.5,
            command=self._set_tts_speed
        )
        speed_menu.add_radiobutton(
            label="0.75x",
            variable=self.tts_speed_var,
            value=0.75,
            command=self._set_tts_speed
        )
        speed_menu.add_radiobutton(
            label="1.0x (Normal)",
            variable=self.tts_speed_var,
            value=1.0,
            command=self._set_tts_speed
        )
        speed_menu.add_radiobutton(
            label="1.25x",
            variable=self.tts_speed_var,
            value=1.25,
            command=self._set_tts_speed
        )
        speed_menu.add_radiobutton(
            label="1.5x",
            variable=self.tts_speed_var,
            value=1.5,
            command=self._set_tts_speed
        )
        speed_menu.add_radiobutton(
            label="2.0x (Fast)",
            variable=self.tts_speed_var,
            value=2.0,
            command=self._set_tts_speed
        )

    def _toggle_always_on_top(self):
        """最前面固定を切り替え"""
        self.always_on_top = self.topmost_var.get()
        self.root.attributes('-topmost', self.always_on_top)
        status = "enabled" if self.always_on_top else "disabled"
        print(f"[WINDOW] Always on top {status}")
        self._save_settings()

    def _set_tts_mode(self):
        """読み上げモードを設定"""
        self.tts_mode = self.tts_mode_var.get()
        print(f"[TTS] Mode set to: {self.tts_mode}")
        self._save_settings()

    def _toggle_tts_summary(self):
        """要約読み上げを切り替え"""
        self.tts_include_summary = self.tts_summary_var.get()
        status = "enabled" if self.tts_include_summary else "disabled"
        print(f"[TTS] Include summary {status}")
        self._save_settings()

    def _set_tts_speed(self):
        """読み上げ速度を設定"""
        self.tts_speed = self.tts_speed_var.get()
        print(f"[TTS] Speed set to: {self.tts_speed}x")
        self._save_settings()

    def _set_summary_area_height(self):
        """要約エリアの高さを設定"""
        self.summary_area_height = self.summary_height_var.get()
        print(f"[VIEW] Summary area height set to: {self.summary_area_height}px")
        # 現在のセッションカードの高さを更新
        if hasattr(self, 'session_cards'):
            for card in self.session_cards:
                card.update_output_frame_height(self.summary_area_height)
        self._save_settings()

    def _stop_current_speech(self):
        """現在の読み上げを中断"""
        self.tts_stop_flag = True
        if self.tts_process:
            try:
                self.tts_process.terminate()
                self.tts_process.wait(timeout=1)
            except:
                pass
            self.tts_process = None
        print("[TTS] Speech stopped")

    def speak_status_change(self, session: TerminalSession, previous_status: str):
        """状態変化時の読み上げ"""
        if self.tts_mode == "none":
            return

        # 前の読み上げを中断
        self._stop_current_speech()

        # 読み上げテキストを構築
        speech_parts = []

        # タイトル
        speech_parts.append(session.display_name)

        # activeからの変化の場合、完了を伝える
        if previous_status == "active":
            speech_parts.append("が終わりました。")
        else:
            speech_parts.append("。")

        # 要約を含める場合
        if self.tts_include_summary and session.summary:
            # 要約から不要な記号を除去
            summary = session.summary.replace("~要約中~", "")
            summary = summary.replace("**", "").replace("#", "")
            if summary.strip():
                speech_parts.append(summary)

        text = "".join(speech_parts)

        # バックグラウンドスレッドで読み上げ
        self.tts_stop_flag = False
        self.tts_thread = threading.Thread(target=self._speak_thread, args=(text,), daemon=True)
        self.tts_thread.start()

    def _speak_thread(self, text: str):
        """読み上げスレッド"""
        if self.tts_stop_flag:
            return

        try:
            if self.tts_mode == "apple":
                # Apple TTS (say コマンド) - 速度指定
                rate = int(200 * self.tts_speed)  # デフォルト200 words/min
                self.tts_process = subprocess.Popen(
                    ["say", "-v", "Kyoko", "-r", str(rate), text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.tts_process.wait()

            elif self.tts_mode == "voicevox":
                # VOICEVOX (ずんだもん: speaker_id=3) - PyAudioで連続再生
                import requests
                import re
                import tempfile
                import wave
                import pyaudio
                from concurrent.futures import ThreadPoolExecutor

                # VOICEVOX EngineのURL（デフォルトポート50021）
                voicevox_url = "http://localhost:50021"
                speaker_id = 3  # ずんだもん

                # テキストを句読点で分割
                sentences = re.split(r'([。、！？])', text)
                # 区切り文字を前の文に結合
                merged_sentences = []
                for i in range(0, len(sentences), 2):
                    if i + 1 < len(sentences):
                        merged_sentences.append(sentences[i] + sentences[i+1])
                    elif sentences[i].strip():
                        merged_sentences.append(sentences[i])

                # 空の文を除外
                merged_sentences = [s.strip() for s in merged_sentences if s.strip()]

                def generate_audio(sentence_text):
                    """音声を生成してWAVデータを返す"""
                    try:
                        # 音声合成クエリを作成
                        query_response = requests.post(
                            f"{voicevox_url}/audio_query",
                            params={"text": sentence_text, "speaker": speaker_id},
                            timeout=5
                        )

                        if query_response.status_code == 200:
                            query_json = query_response.json()
                            query_json["speedScale"] = self.tts_speed

                            # 音声を合成
                            synthesis_response = requests.post(
                                f"{voicevox_url}/synthesis",
                                params={"speaker": speaker_id},
                                json=query_json,
                                timeout=10
                            )

                            if synthesis_response.status_code == 200:
                                return synthesis_response.content
                    except Exception as e:
                        print(f"[TTS] VOICEVOX generation error: {e}")
                    return None

                # PyAudioで連続再生
                p = pyaudio.PyAudio()
                stream = None

                try:
                    # 2つ先まで先読みして再生
                    with ThreadPoolExecutor(max_workers=3) as executor:
                        future_to_index = {}
                        audio_data = {}

                        # 最初の3つを先読み開始
                        for i in range(min(3, len(merged_sentences))):
                            if self.tts_stop_flag:
                                break
                            future = executor.submit(generate_audio, merged_sentences[i])
                            future_to_index[future] = i

                        # 順次再生しながら先読み
                        for i in range(len(merged_sentences)):
                            if self.tts_stop_flag:
                                break

                            # 次の音声生成を開始（2つ先まで）
                            next_index = i + 3
                            if next_index < len(merged_sentences):
                                future = executor.submit(generate_audio, merged_sentences[next_index])
                                future_to_index[future] = next_index

                            # 現在の音声データを取得（まだ生成中なら待機）
                            if i not in audio_data:
                                for future in list(future_to_index.keys()):
                                    if future_to_index[future] == i:
                                        audio_data[i] = future.result()
                                        del future_to_index[future]
                                        break

                            # 音声を再生
                            wav_data = audio_data.get(i)
                            if wav_data:
                                # WAVデータを一時ファイルに書き込み
                                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                                    f.write(wav_data)
                                    temp_path = f.name

                                # WAVファイルを開く
                                wf = wave.open(temp_path, 'rb')

                                # 初回のみストリームを作成
                                if stream is None:
                                    stream = p.open(
                                        format=p.get_format_from_width(wf.getsampwidth()),
                                        channels=wf.getnchannels(),
                                        rate=wf.getframerate(),
                                        output=True,
                                        frames_per_buffer=1024
                                    )

                                # データを読み込んで再生
                                chunk_size = 1024
                                data = wf.readframes(chunk_size)
                                while data and not self.tts_stop_flag:
                                    stream.write(data)
                                    data = wf.readframes(chunk_size)

                                wf.close()

                                # 一時ファイルを削除
                                try:
                                    os.unlink(temp_path)
                                except:
                                    pass

                finally:
                    # ストリームをクリーンアップ
                    if stream is not None:
                        stream.stop_stream()
                        stream.close()
                    p.terminate()

        except Exception as e:
            print(f"[TTS] Speech error: {e}")
        finally:
            self.tts_process = None

    def _on_card_reorder(self, session: TerminalSession, direction: str):
        """カードの並び替え"""
        print(f"[REORDER] Moving {session.display_name} {direction}")

        # 現在のカードのインデックスを取得
        current_index = None
        for i, card in enumerate(self.session_cards):
            if card.session.window_id == session.window_id and card.session.tab_index == session.tab_index:
                current_index = i
                break

        if current_index is None:
            return

        # 新しいインデックスを計算
        new_index = current_index - 1 if direction == "up" else current_index + 1
        if new_index < 0 or new_index >= len(self.session_cards):
            return  # 範囲外

        # カードを入れ替え
        self.session_cards[current_index], self.session_cards[new_index] = \
            self.session_cards[new_index], self.session_cards[current_index]

        # display_orderを更新
        for i, card in enumerate(self.session_cards):
            card.session.display_order = i + 1
            print(f"  [{i+1}] {card.session.display_name}, display_order={card.session.display_order}")

        # カードを再配置
        for card in self.session_cards:
            card.pack_forget()
        for card in self.session_cards:
            card.pack(fill=tk.X, pady=5, padx=5)

        # main.pyのsession_mapを更新するコールバックを呼び出す
        if self.on_reorder_complete:
            sessions = [card.session for card in self.session_cards]
            self.on_reorder_complete(sessions)

        # ドロップ直後に画面を即座に更新（2回連続ドラッグ対策）
        # 100ms後に強制更新をトリガー
        self.root.after(100, self._force_update_after_reorder)

    def _build_ui(self):
        """UIを構築"""
        # API設定エリア（APIキーが未設定の場合のみ表示）
        if not self.api_key_configured:
            api_config_frame = tk.Frame(self.root, bg="#2a2a2a", relief=tk.FLAT, borderwidth=1)
            api_config_frame.pack(fill=tk.X, padx=5, pady=5)

            # タイトル
            title_label = tk.Label(
                api_config_frame,
                text="Claude API Configuration",
                font=("Courier", 10, "bold"),
                fg="#cccccc",
                bg="#2a2a2a"
            )
            title_label.pack(pady=(8, 5))

            info_label = tk.Label(
                api_config_frame,
                text="API key is required for AI-powered summarization",
                font=("Courier", 8),
                fg="#888888",
                bg="#2a2a2a"
            )
            info_label.pack(pady=(0, 8))

            # API キー入力フィールド
            input_frame = tk.Frame(api_config_frame, bg="#2a2a2a")
            input_frame.pack(pady=5, padx=10, fill=tk.X)

            api_key_label = tk.Label(
                input_frame,
                text="API Key:",
                font=("Courier", 9),
                fg="#cccccc",
                bg="#2a2a2a"
            )
            api_key_label.pack(side=tk.LEFT, padx=(0, 8))

            self.api_key_entry = tk.Entry(
                input_frame,
                font=("Courier", 9),
                bg="#1a1a1a",
                fg="#00ff00",
                insertbackground="#00ff00",
                show="*",
                relief=tk.FLAT,
                borderwidth=2
            )
            self.api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

            save_button = tk.Button(
                input_frame,
                text="Save",
                font=("Courier", 9, "bold"),
                bg="#cccccc",
                fg="#000000",
                activebackground="#dddddd",
                activeforeground="#000000",
                relief=tk.FLAT,
                borderwidth=0,
                padx=15,
                command=self._save_api_key
            )
            save_button.pack(side=tk.LEFT)

            # リンク
            link_label = tk.Label(
                api_config_frame,
                text="Get API key: https://console.anthropic.com/",
                font=("Courier", 7),
                fg="#666666",
                bg="#2a2a2a",
                cursor="hand2"
            )
            link_label.pack(pady=(5, 8))
            link_label.bind("<Button-1>", lambda e: self._open_url("https://console.anthropic.com/"))

        # スクロール可能なセッションリスト（スクロールバーなし）
        canvas_frame = tk.Frame(self.root, bg=COLORS["bg"])
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Canvas（スクロールバーなし）
        self.canvas = tk.Canvas(canvas_frame, bg=COLORS["bg"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # スクロール可能なフレームを作成
        self.scrollable_frame = tk.Frame(self.canvas, bg=COLORS["bg"])
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # スクロール領域の更新
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # Canvasのリサイズ時に横幅を更新
        def _on_canvas_configure(event):
            self.canvas.itemconfig(self.canvas_window, width=event.width)

        self.canvas.bind("<Configure>", _on_canvas_configure)

        # マウスホイール/トラックパッドでスクロール
        # Tk 8.7+では、macOSトラックパッドは<TouchpadScroll>イベントを使用
        # Tk 8.6以前およびマウスホイールは<MouseWheel>を使用

        # Canvasのスクロール単位を1ピクセルに設定（ピクセル単位でスムーズにスクロール）
        self.canvas.configure(yscrollincrement=1)

        # トラックパッドスクロール用のアキュムレータ（小数点以下を蓄積）
        self._scroll_accumulator = 0.0

        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * event.delta), "units")

        def _on_touchpad(event):
            # event.deltaは32bitに圧縮されたdx,dyを含む
            dx, dy = map(int, self.root.tk.call("tk::PreciseScrollDeltas", event.delta))

            # macOSでは16bit符号付き整数の-1が65535として届くので修正
            if dy > 32767:
                dy -= 65536

            # deltaをそのままピクセル単位として扱う（dyを反転）
            delta = -dy

            # アキュムレータに蓄積
            self._scroll_accumulator += delta

            # 整数部分を取り出してスクロール
            step = int(self._scroll_accumulator)
            if step != 0:
                print(f"[SCROLL-DETAIL] dx={dx}, dy={dy}, delta={delta}, accumulator={self._scroll_accumulator:.2f}, step={step}")
                self.canvas.yview_scroll(step, "units")  # yscrollincrement=1なので1unit=1pixel
                # 小数点以下の余りを保持
                self._scroll_accumulator -= step

        # Canvasとその子孫全てに対してスクロールイベントをバインド
        # これによりCanvas内のどこにマウスがあってもスクロール可能
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")
        self.canvas.bind_all("<TouchpadScroll>", _on_touchpad, add="+")

        # デバッグ: 全てのクリックを検出
        self.root.bind_all("<Button-1>", lambda e: print(f"[DEBUG] Global click detected on: {e.widget.__class__.__name__} ({e.widget})"))

        # 定期的にフォーカス状態をチェック（5秒ごと）
        self._check_focus_periodically()

    def _check_focus_periodically(self):
        """定期的にフォーカス状態をチェック"""
        try:
            focus = self.root.focus_get()
            focus_displayof = self.root.focus_displayof()
            print(f"[FOCUS-CHECK] focus_get={focus}, focus_displayof={focus_displayof}")
        except Exception as e:
            print(f"[FOCUS-CHECK] Error: {e}")

        # 5秒後に再実行
        self.root.after(5000, self._check_focus_periodically)

    def update_sessions(self, sessions: List[TerminalSession]):
        """セッションリストを更新（既存カードを再利用し、順序を保持）"""
        # ドラッグ中は更新をスキップ
        if self.is_any_card_dragging:
            print(f"  MonitorWindow.update_sessions SKIPPED (dragging in progress)")
            return

        print(f"  MonitorWindow.update_sessions called with {len(sessions)} sessions")
        for i, s in enumerate(sessions):
            print(f"    Session {i+1}: {s.display_name}, window_id={s.window_id}, tab_index={s.tab_index}, output_len={len(s.last_output)}")

        # 既存カードをキーでマップ
        card_map = {(card.session.window_id, card.session.tab_index): card for card in self.session_cards}

        # 新しいカードリストを作成（sessionsの順序通り）
        new_cards = []
        for session in sessions:
            session_key = (session.window_id, session.tab_index)

            if session_key in card_map:
                # 既存カードを再利用して更新
                card = card_map[session_key]
                card.update_session(session)
                new_cards.append(card)
                print(f"    Reusing card: {session.display_name}")
            else:
                # 新規カード作成
                card = SessionCard(
                    self.scrollable_frame,
                    session,
                    self.on_session_click,
                    self._on_card_reorder,
                    monitor_window=self
                )
                new_cards.append(card)
                print(f"    Created new card: {session.display_name}")

        # 削除されたセッションのカードを破棄
        current_keys = {(s.window_id, s.tab_index) for s in sessions}
        for old_card in self.session_cards:
            old_key = (old_card.session.window_id, old_card.session.tab_index)
            if old_key not in current_keys:
                old_card.destroy()
                print(f"    Removed card: {old_card.session.display_name}")

        # 既存のカードを全て削除
        for old_card in self.session_cards:
            old_card.pack_forget()

        # 新しい順序でカードを配置
        for i, card in enumerate(new_cards):
            card.pack(fill=tk.X, pady=5, padx=5)
            summary_preview = card.session.summary[:50] if card.session.summary else "(no summary)"
            print(f"    Packed card at position {i+1}: {card.session.display_name} (window_id={card.session.window_id}, tab_index={card.session.tab_index})")
            print(f"      Summary preview: {summary_preview}")

        # カードリストを更新
        self.session_cards = new_cards

        # スクロール領域を更新
        self.scrollable_frame.update_idletasks()

    def show_notification(self, message: str, type: str = "info"):
        """通知を表示（無効化済み）"""
        # 通知表示を無効化
        pass

    def _force_update_after_reorder(self):
        """ドロップ後に強制的に画面更新を実行"""
        print("[REORDER] Forcing update after reorder")
        if self.on_force_update:
            self.on_force_update()

    def _save_api_key(self):
        """APIキーを保存して再起動"""
        import json
        import sys
        import os
        from pathlib import Path

        api_key = self.api_key_entry.get().strip()
        if not api_key:
            print("Error: API key is empty")
            return

        config_path = Path(__file__).parent / "config.json"

        try:
            # 既存の設定を読み込み
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {
                    "model": "claude-sonnet-4-5-20250929",
                    "max_tokens": 200,
                    "temperature": 0.7,
                    "summary_instructions": "以下のClaude Codeセッションの出力を、10秒で読める程度（約150文字）に要約してください。重要なポイント、エラー、進捗状況を含めてください。"
                }

            # APIキーを更新
            config["anthropic_api_key"] = api_key

            # 保存
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            print(f"API key saved to {config_path}")
            print("Restarting application...")

            # アプリケーションを再起動
            self.root.destroy()  # 現在のウィンドウを閉じる

            # main.pyを再実行
            python = sys.executable
            main_script = Path(__file__).parent / "main.py"
            os.execl(python, python, str(main_script))

        except Exception as e:
            print(f"Error saving API key: {e}")
            import traceback
            traceback.print_exc()

    def _open_url(self, url: str):
        """URLをブラウザで開く"""
        import webbrowser
        webbrowser.open(url)

    def run(self):
        """GUIを起動"""
        self.root.mainloop()


if __name__ == "__main__":
    # テスト実行
    def on_click(session):
        print(f"Clicked: {session.display_name}")

    window = MonitorWindow(on_session_click=on_click)

    # テストデータ
    from terminal_monitor import TerminalSession
    test_sessions = [
        TerminalSession(
            window_id=1,
            tab_index=0,
            tab_name="claude-code project1",
            is_running_claude=True,
            last_output="Running tests... All passed!",
            status="active",
            todo_progress="3/5 completed",
            last_updated=datetime.now()
        ),
        TerminalSession(
            window_id=1,
            tab_index=1,
            tab_name="bash",
            is_running_claude=False,
            last_output="$ ls -la",
            status="idle",
            todo_progress=None,
            last_updated=datetime.now()
        )
    ]

    window.update_sessions(test_sessions)
    window.run()
