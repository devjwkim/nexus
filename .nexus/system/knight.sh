#!/bin/bash
# Claude Code + Telegram Bot integrated startup script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SESSION_NAME="claude"
VENV_DIR="$PROJECT_ROOT/venv"
BOT_SCRIPT="$SCRIPT_DIR/telegram_bot.py"
PID_FILE="$SCRIPT_DIR/bot.pid"
LOG_FILE="$SCRIPT_DIR/telegram_bot.log"
MAX_LOG_LINES=1000

echo "🚀 Starting Claude Code K.N.I.G.H.T. environment..."
echo ""

# ========== 1. Telegram Bot ==========
echo "📱 Setting up Telegram bot..."

# Create virtual environment if not exists
if [ ! -d "$VENV_DIR" ]; then
    echo "   🔧 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Check pyTelegramBotAPI installation
if ! python3 -c "import telebot" 2>/dev/null; then
    echo "   📦 Installing pyTelegramBotAPI..."
    pip3 install pyTelegramBotAPI --quiet
fi

# Terminate existing bot
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "   🔄 Terminating existing bot (PID: $OLD_PID)"
        kill "$OLD_PID" 2>/dev/null
        sleep 1
    fi
fi

# Log rotation
if [ -f "$LOG_FILE" ]; then
    tail -n $MAX_LOG_LINES "$LOG_FILE" > "${LOG_FILE}.tmp"
    mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi

# Run bot in background
nohup python3 "$BOT_SCRIPT" >> "$LOG_FILE" 2>&1 &
BOT_PID=$!
echo "$BOT_PID" > "$PID_FILE"
echo "   ✅ Bot started (PID: $BOT_PID)"

# Deactivate virtual environment
deactivate

# ========== 2. tmux + Claude Code ==========
echo ""
echo "💻 Setting up Claude Code K.N.I.G.H.T...."

# Terminate existing session (ignore errors)
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
sleep 1

# Create new session
if ! tmux new-session -d -s "$SESSION_NAME" 2>/dev/null; then
    echo "   ⚠️  Retrying tmux session creation..."
    sleep 1
    tmux new-session -d -s "$SESSION_NAME"
fi

sleep 1
tmux send-keys -t "$SESSION_NAME" "cd $PROJECT_ROOT && claude" Enter

echo "   ✅ tmux session created"

# ========== Complete ==========
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ All setup complete!"
echo ""
echo "📱 Telegram bot: PID $BOT_PID"
echo "   Log: tail -f $LOG_FILE"
echo "   Stop: kill $BOT_PID"
echo ""
echo "💻 Claude Code Knight: tmux session 'claude'"
echo "   Detach: Ctrl+B, D"
echo "   Stop: tmux kill-session -t claude"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check tmux session and attach
sleep 1
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    tmux attach -t "$SESSION_NAME"
else
    echo "❌ Failed to connect to tmux session. Run manually:"
    echo "   tmux new-session -s claude"
    echo "   claude"
fi
