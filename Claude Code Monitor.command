#!/bin/bash
cd "$(dirname "$0")"
python3 main.py > /tmp/claude_voice_controller.log 2>&1 &
echo "Claude Code Monitor started!"
sleep 2

# このターミナルウィンドウを閉じる
osascript -e 'tell application "Terminal" to close (every window whose name contains ".command")' &
