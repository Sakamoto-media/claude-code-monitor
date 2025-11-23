"""
縦長モニタリングウィンドウのGUI
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import List, Callable, Optional
from datetime import datetime
import threading

from config import COLORS, WINDOW_WIDTH, WINDOW_HEIGHT, UPDATE_INTERVAL
from terminal_monitor import TerminalSession


class SessionCard(tk.Frame):
    """各セッションを表示するカード"""

    def __init__(self, parent, session: TerminalSession, on_click: Callable):
        super().__init__(parent, bg=COLORS["bg"], relief=tk.RAISED, borderwidth=2)
        self.session = session
        self.on_click = on_click

        self._build_ui()
        self.bind("<Button-1>", lambda e: self.on_click(session))

    def _build_ui(self):
        """UIを構築"""
        # ヘッダー部分
        header_frame = tk.Frame(self, bg=COLORS["bg"])
        header_frame.pack(fill=tk.X, padx=10, pady=5)

        # セッション名
        self.name_label = tk.Label(
            header_frame,
            text=self.session.display_name,
            font=("Arial", 12, "bold"),
            fg=COLORS["fg"],
            bg=COLORS["bg"],
            anchor="w"
        )
        self.name_label.pack(side=tk.LEFT)

        # 状態インジケーター
        self.status_indicator = tk.Label(
            header_frame,
            text="●",
            font=("Arial", 16),
            fg=self._get_status_color(self.session.status),
            bg=COLORS["bg"]
        )
        self.status_indicator.pack(side=tk.RIGHT)

        # Claude実行中かのバッジ
        if self.session.is_running_claude:
            claude_badge = tk.Label(
                header_frame,
                text="Claude",
                font=("Arial", 9),
                fg=COLORS["bg"],
                bg=COLORS["highlight"],
                padx=5,
                pady=2
            )
            claude_badge.pack(side=tk.RIGHT, padx=5)

        # 進捗情報
        if self.session.todo_progress:
            progress_frame = tk.Frame(self, bg=COLORS["bg"])
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

        # 最新出力プレビュー（スクロール可能）
        output_frame = tk.Frame(self, bg=COLORS["bg"])
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            font=("Courier", 10),
            fg="#cccccc",
            bg="#2a2a2a",
            wrap=tk.WORD,
            height=10,
            width=40,
            relief=tk.FLAT,
            borderwidth=0
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)

        # 初期テキストを挿入
        initial_text = self.session.last_output if self.session.last_output else "(No output)"
        print(f"    SessionCard.__init__: {self.session.display_name}, inserting {len(initial_text)} chars")
        self.output_text.insert("1.0", initial_text)
        # 最下部にスクロール
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)  # 読み取り専用
        print(f"    SessionCard created for {self.session.display_name}")

        # 更新時刻
        time_str = self.session.last_updated.strftime("%H:%M:%S")
        self.time_label = tk.Label(
            self,
            text=f"Updated: {time_str}",
            font=("Arial", 8),
            fg="#888888",
            bg=COLORS["bg"],
            anchor="e"
        )
        self.time_label.pack(fill=tk.X, padx=10, pady=2)

        # ホバー効果
        self._bind_hover_effects()

    def _bind_hover_effects(self):
        """ホバーエフェクトをバインド"""
        def on_enter(e):
            self.config(bg=COLORS["highlight"], borderwidth=3)

        def on_leave(e):
            self.config(bg=COLORS["bg"], borderwidth=2)

        self.bind("<Enter>", on_enter)
        self.bind("<Leave>", on_leave)

    def _get_status_color(self, status: str) -> str:
        """状態に応じた色を返す"""
        colors = {
            "active": COLORS["active"],
            "waiting": COLORS["waiting"],
            "error": COLORS["error"],
            "idle": COLORS["idle"]
        }
        return colors.get(status, COLORS["idle"])

    def _truncate_output(self, text: str, max_length: int = 150) -> str:
        """出力を切り詰める"""
        if not text:
            return "(No output)"

        text = text.strip()
        if len(text) > max_length:
            return text[-max_length:] + "..."
        return text

    def update_session(self, session: TerminalSession):
        """セッション情報を更新"""
        self.session = session

        # 各要素を更新
        self.name_label.config(text=session.display_name)
        self.status_indicator.config(fg=self._get_status_color(session.status))

        # ScrolledTextウィジェットの内容を更新
        self.output_text.config(state=tk.NORMAL)  # 一時的に編集可能に
        self.output_text.delete("1.0", tk.END)

        output_text = session.last_output if session.last_output else "(No output)"
        self.output_text.insert("1.0", output_text)

        # デバッグ: 出力長をログ
        print(f"    GUI Card updated: {session.display_name}, Output length: {len(output_text)}")

        # 最下部にスクロール
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)  # 再度読み取り専用に

        time_str = session.last_updated.strftime("%H:%M:%S")
        self.time_label.config(text=f"Updated: {time_str}")


class MonitorWindow:
    """メインモニタリングウィンドウ"""

    def __init__(self, on_session_click: Callable, on_voice_command: Optional[Callable] = None):
        self.root = tk.Tk()
        self.root.title("Claude Code Voice Controller")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg=COLORS["bg"])

        # 常に最前面
        self.root.attributes('-topmost', True)

        self.on_session_click = on_session_click
        self.on_voice_command = on_voice_command

        self.session_cards: List[SessionCard] = []
        self.voice_listening = False

        self._build_ui()

    def _build_ui(self):
        """UIを構築"""
        # タイトルバー
        title_frame = tk.Frame(self.root, bg=COLORS["highlight"], height=50)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        title_label = tk.Label(
            title_frame,
            text="🎤 Claude Code Controller",
            font=("Arial", 14, "bold"),
            fg=COLORS["fg"],
            bg=COLORS["highlight"]
        )
        title_label.pack(pady=10)

        # 音声コントロールバー
        control_frame = tk.Frame(self.root, bg="#2a2a2a", height=60)
        control_frame.pack(fill=tk.X)
        control_frame.pack_propagate(False)

        self.voice_button = tk.Button(
            control_frame,
            text="🎤 音声入力開始",
            font=("Arial", 11),
            bg=COLORS["active"],
            fg=COLORS["fg"],
            command=self._toggle_voice_listening,
            relief=tk.FLAT,
            padx=10,
            pady=5
        )
        self.voice_button.pack(pady=10)

        self.voice_status_label = tk.Label(
            control_frame,
            text="待機中",
            font=("Arial", 9),
            fg="#cccccc",
            bg="#2a2a2a"
        )
        self.voice_status_label.pack()

        # スクロール可能なセッションリスト
        canvas_frame = tk.Frame(self.root, bg=COLORS["bg"])
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas = tk.Canvas(canvas_frame, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)

        self.scrollable_frame = tk.Frame(self.canvas, bg=COLORS["bg"])
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # マウスホイールでスクロール
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        """マウスホイールスクロール"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _toggle_voice_listening(self):
        """音声入力のON/OFF切り替え"""
        self.voice_listening = not self.voice_listening

        if self.voice_listening:
            self.voice_button.config(
                text="🛑 音声入力停止",
                bg=COLORS["error"]
            )
            self.voice_status_label.config(text="聞いています...")

            if self.on_voice_command:
                # 別スレッドで音声認識開始
                threading.Thread(target=self._voice_listening_loop, daemon=True).start()
        else:
            self.voice_button.config(
                text="🎤 音声入力開始",
                bg=COLORS["active"]
            )
            self.voice_status_label.config(text="待機中")

    def _voice_listening_loop(self):
        """音声認識ループ（バックグラウンド）"""
        while self.voice_listening:
            if self.on_voice_command:
                self.on_voice_command()

    def update_sessions(self, sessions: List[TerminalSession]):
        """セッションリストを更新"""
        print(f"  MonitorWindow.update_sessions called with {len(sessions)} sessions")
        for i, s in enumerate(sessions):
            print(f"    Session {i+1}: {s.display_name}, output_len={len(s.last_output)}")

        # 既存のカードをクリア
        for card in self.session_cards:
            card.destroy()
        self.session_cards.clear()

        # 新しいカードを作成
        for session in sessions:
            card = SessionCard(
                self.scrollable_frame,
                session,
                self.on_session_click
            )
            card.pack(fill=tk.X, pady=5, padx=5)
            self.session_cards.append(card)

        # スクロール領域を更新
        self.scrollable_frame.update_idletasks()

    def show_notification(self, message: str, type: str = "info"):
        """通知を表示"""
        colors = {
            "info": COLORS["highlight"],
            "success": COLORS["active"],
            "error": COLORS["error"],
            "warning": COLORS["waiting"]
        }

        notification = tk.Label(
            self.root,
            text=message,
            font=("Arial", 10),
            fg=COLORS["fg"],
            bg=colors.get(type, COLORS["highlight"]),
            padx=10,
            pady=5
        )
        notification.place(relx=0.5, rely=0.9, anchor="center")

        # 3秒後に消去
        self.root.after(3000, notification.destroy)

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
