"""
縦長モニタリングウィンドウのGUI
"""
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import List, Callable, Optional
from datetime import datetime
import threading

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
        output_frame = tk.Frame(self.content_frame, bg=COLORS["bg"], height=120)
        output_frame.pack(fill=tk.X, padx=10, pady=5)
        output_frame.pack_propagate(False)  # 子要素によるサイズ変更を防止

        self.output_text = tk.Text(
            output_frame,
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
            # Claude APIで生成された要約を使用
            summary_text = self.session.summary

            # 要約に改行を追加して読みやすくする
            # 句点（。）の後に改行を入れる
            summary_text = summary_text.replace('。', '。\n')

            # 末尾の余分な改行を削除
            summary_text = summary_text.strip()

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

    def __init__(self, on_session_click: Callable, on_reorder_complete: Optional[Callable] = None, on_force_update: Optional[Callable] = None):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg=COLORS["bg"])
        self.on_session_click = on_session_click
        self.on_reorder_complete = on_reorder_complete
        self.on_force_update = on_force_update

        # macOS Tk 9.0バグ回避: ウィンドウを一旦非表示にしてから表示
        # マウスポインタがウィンドウ内にある状態で表示されると、キーウィンドウになれない
        self.root.withdraw()

        # 初回表示時のみフォーカスを取得（その後は奪わない）
        self._initial_focus_done = False

        # ドラッグ中フラグ（更新処理の一時停止用）
        self.is_any_card_dragging = False

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
