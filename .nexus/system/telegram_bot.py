#!/usr/bin/env python3
"""
Telegram Bot - Claude Code Remote Control
- Inline button callback handling
- Direct input via /claude command
"""

import subprocess
import os
import sys
import json
import threading
import time
from datetime import datetime

# Disable stdout buffering (immediate log output)
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

def log(msg):
    """Print log with timestamp"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

try:
    import telebot
    from telebot import types
except ImportError:
    print("❌ pyTelegramBotAPI required:")
    print("   pip3 install pyTelegramBotAPI")
    sys.exit(1)

# Read value from settings file
def get_property(key, settings_file=None):
    if settings_file is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        settings_file = os.path.join(script_dir, "../settings/nexus.properties")

    try:
        with open(settings_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split('=', 1)[1]
    except FileNotFoundError:
        pass
    return None

# Load settings
BOT_TOKEN = get_property("project.bot.token")
CHAT_ID = get_property("project.bot.chatid")
TMUX_SESSION = get_property("project.bot.tmux.session") or "claude"

if not BOT_TOKEN or not CHAT_ID:
    print("❌ Configuration error: Check project.bot.token, project.bot.chatid")
    sys.exit(1)

CHAT_ID = int(CHAT_ID)

# Pending file path (single file)
script_dir = os.path.dirname(os.path.abspath(__file__))
PENDING_FILE = os.path.join(script_dir, "pending.json")

# Wait time (seconds)
PENDING_WAIT_SECONDS = 30

bot = telebot.TeleBot(BOT_TOKEN)

# Store processed callback message IDs (prevent duplicates)
processed_callbacks = set()

# ========== Pending File Monitoring (single file) ==========
def pending_monitor():
    """Send telegram notification if pending.json content is older than 15 seconds"""
    while True:
        try:
            if not os.path.exists(PENDING_FILE):
                time.sleep(2)
                continue

            # Check file size (skip if empty)
            if os.path.getsize(PENDING_FILE) == 0:
                time.sleep(2)
                continue

            with open(PENDING_FILE, 'r') as f:
                data = json.load(f)

            # Check if timestamp is older than 15 seconds
            file_ts = data.get('timestamp', 0)
            now = time.time()
            if now - file_ts < PENDING_WAIT_SECONDS:
                time.sleep(2)
                continue

            # Send notification
            msg_text = data.get('message', '')
            buttons = data.get('buttons', [])

            if buttons:
                markup = types.InlineKeyboardMarkup(row_width=len(buttons))
                btn_list = []
                for btn in buttons:
                    if ':' in btn:
                        label, callback = btn.rsplit(':', 1)
                        btn_list.append(types.InlineKeyboardButton(label.strip(), callback_data=callback.strip()))
                if btn_list:
                    markup.add(*btn_list)
                    bot.send_message(CHAT_ID, f"⏰ {msg_text}", reply_markup=markup)
                else:
                    bot.send_message(CHAT_ID, f"⏰ {msg_text}")
            else:
                bot.send_message(CHAT_ID, f"⏰ {msg_text}")

            log(f"📤 Pending notification: {msg_text[:50]}")

            # Clear file (send complete)
            open(PENDING_FILE, 'w').close()

        except json.JSONDecodeError:
            # Empty file or invalid JSON - ignore
            pass
        except FileNotFoundError:
            pass
        except Exception as e:
            log(f"❌ Monitor error: {e}")

        time.sleep(2)

def send_to_tmux(text, send_enter=True):
    """Send text to tmux session"""
    try:
        # Check if tmux session exists
        result = subprocess.run(
            ['tmux', 'has-session', '-t', TMUX_SESSION],
            capture_output=True
        )
        if result.returncode != 0:
            return False, f"tmux session '{TMUX_SESSION}' not found"

        # Send text (-l: literal, send special characters as-is)
        subprocess.run(['tmux', 'send-keys', '-t', TMUX_SESSION, '-l', text], capture_output=True)
        if send_enter:
            subprocess.run(['tmux', 'send-keys', '-t', TMUX_SESSION, 'Enter'], capture_output=True)
        return True, "Sent successfully"
    except Exception as e:
        return False, str(e)

def send_selection_to_tmux(choice_num):
    """Send selection to Claude Code selection UI (arrow keys + Enter)"""
    try:
        # Check if tmux session exists
        result = subprocess.run(
            ['tmux', 'has-session', '-t', TMUX_SESSION],
            capture_output=True
        )
        if result.returncode != 0:
            return False, f"tmux session '{TMUX_SESSION}' not found"

        # Send Down key based on selection number (1st is already selected)
        choice_num = int(choice_num)
        for _ in range(choice_num - 1):
            subprocess.run(['tmux', 'send-keys', '-t', TMUX_SESSION, 'Down'], capture_output=True)
            import time
            time.sleep(0.05)  # Small delay

        # Send Enter
        subprocess.run(['tmux', 'send-keys', '-t', TMUX_SESSION, 'Enter'], capture_output=True)
        return True, "Selection complete"
    except Exception as e:
        return False, str(e)

def is_authorized(message):
    """Check if user is authorized"""
    return message.chat.id == CHAT_ID

# Callback query handler (inline buttons)
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.message.chat.id != CHAT_ID:
        return

    # Check if message already processed (prevent duplicates)
    msg_id = call.message.message_id
    if msg_id in processed_callbacks:
        bot.answer_callback_query(call.id, "⚠️ Already processed")
        return

    # Button data: "1", "2", "3", etc.
    choice = call.data

    # Send arrow keys + Enter to Claude Code selection UI
    success, msg = send_selection_to_tmux(choice)

    if success:
        # Mark as processed
        processed_callbacks.add(msg_id)
        log(f"✅ Button clicked: #{choice}")
        bot.answer_callback_query(call.id, f"✅ Selected #{choice}")
        # Remove buttons and show selection result
        try:
            original_text = call.message.text
            bot.edit_message_text(
                f"{original_text}\n\n✅ Selected: #{choice}",
                call.message.chat.id,
                msg_id,
                reply_markup=None
            )
        except:
            bot.edit_message_reply_markup(call.message.chat.id, msg_id, reply_markup=None)
        # Processing notification
        bot.send_message(call.message.chat.id, "⏳ Processing...")
    else:
        log(f"❌ Button failed: {msg}")
        bot.answer_callback_query(call.id, f"❌ Failed: {msg}")

# /yes, /1 - Select option 1
@bot.message_handler(commands=['yes', 'y', '1'])
def cmd_yes(message):
    if not is_authorized(message):
        return

    success, msg = send_to_tmux("1")
    if success:
        bot.reply_to(message, "✅ Option 1 (Yes) selected\n⏳ Processing...")
    else:
        bot.reply_to(message, f"❌ Failed: {msg}")

# /allow, /2 - Select option 2
@bot.message_handler(commands=['allow', 'a', '2'])
def cmd_allow(message):
    if not is_authorized(message):
        return

    success, msg = send_to_tmux("2")
    if success:
        bot.reply_to(message, "✅ Option 2 (Allow for session) selected\n⏳ Processing...")
    else:
        bot.reply_to(message, f"❌ Failed: {msg}")

# /no, /3 - Select option 3
@bot.message_handler(commands=['no', 'n', '3'])
def cmd_no(message):
    if not is_authorized(message):
        return

    success, msg = send_to_tmux("3")
    if success:
        bot.reply_to(message, "✅ Option 3 (No) selected\n⏳ Processing...")
    else:
        bot.reply_to(message, f"❌ Failed: {msg}")

# /4 - Select option 4
@bot.message_handler(commands=['4'])
def cmd_4(message):
    if not is_authorized(message):
        return

    success, msg = send_to_tmux("4")
    if success:
        bot.reply_to(message, "✅ Option 4 selected\n⏳ Processing...")
    else:
        bot.reply_to(message, f"❌ Failed: {msg}")

# /claude <message> - Direct input to Claude
@bot.message_handler(commands=['claude', 'c'])
def cmd_claude(message):
    if not is_authorized(message):
        return

    # Extract message after command
    text = message.text.split(maxsplit=1)
    if len(text) < 2:
        bot.reply_to(message, "Usage: /claude <message>")
        return

    user_input = text[1]
    success, msg = send_to_tmux(user_input)

    if success:
        bot.reply_to(message, f"✅ Sent: {user_input[:50]}...\n⏳ Processing...")
    else:
        bot.reply_to(message, f"❌ Failed: {msg}")

# /tail - Last 2000 characters of Claude CLI screen
@bot.message_handler(commands=['tail', 't'])
def cmd_tail(message):
    if not is_authorized(message):
        return

    try:
        import re

        # Check if tmux session exists
        result = subprocess.run(
            ['tmux', 'has-session', '-t', TMUX_SESSION],
            capture_output=True
        )
        if result.returncode != 0:
            bot.reply_to(message, f"❌ tmux session '{TMUX_SESSION}' not found")
            return

        # Capture entire tmux scrollback buffer
        result = subprocess.run(
            ['tmux', 'capture-pane', '-t', TMUX_SESSION, '-p', '-S', '-500'],
            capture_output=True, text=True
        )
        content = result.stdout

        # Remove ANSI escape codes
        content = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', content)
        content = re.sub(r'\x1b\].*?\x07', '', content)  # OSC sequences

        # Remove consecutive blank lines (3+ -> 1)
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = content.strip()

        if not content:
            bot.reply_to(message, "📭 Screen is empty")
            return

        # Extract last 2000 characters
        if len(content) > 2000:
            content = "..." + content[-1997:]

        bot.reply_to(message, f"📺 Claude CLI:\n```\n{content}\n```", parse_mode='Markdown')

    except Exception as e:
        bot.reply_to(message, f"❌ Failed: {e}")

# /status - Check status
@bot.message_handler(commands=['status'])
def cmd_status(message):
    if not is_authorized(message):
        return

    # Check tmux session
    result = subprocess.run(
        ['tmux', 'has-session', '-t', TMUX_SESSION],
        capture_output=True
    )

    if result.returncode == 0:
        bot.reply_to(message, f"✅ tmux session '{TMUX_SESSION}' is running")
    else:
        bot.reply_to(message, f"❌ tmux session '{TMUX_SESSION}' not found")

# /help - Help
@bot.message_handler(commands=['help', 'start'])
def cmd_help(message):
    if not is_authorized(message):
        return

    help_text = """🤖 Claude Code Remote Control

**Selection Commands:**
/yes, /1 - Select option 1 (Yes)
/allow, /2 - Select option 2 (Allow)
/no, /3 - Select option 3 (No)
/4 - Select option 4

**Other:**
/claude <message> - Direct input to Claude
/tail - Last 2000 characters of screen
/status - Check tmux session status
/help - Help
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

if __name__ == "__main__":
    log("🤖 Telegram bot started")
    log(f"   Session: {TMUX_SESSION}")
    log(f"   Chat ID: {CHAT_ID}")
    log(f"   Wait time: {PENDING_WAIT_SECONDS} seconds")

    # Start pending monitoring thread
    monitor_thread = threading.Thread(target=pending_monitor, daemon=True)
    monitor_thread.start()
    log("📡 Pending monitor started")

    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        log("👋 Bot stopped")
    except Exception as e:
        log(f"❌ Error: {e}")
