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
TMUX_SESSION = get_property("project.name") or "claude"

if not BOT_TOKEN or not CHAT_ID:
    print("❌ Configuration error: Check project.bot.token, project.bot.chatid")
    sys.exit(1)

CHAT_ID = int(CHAT_ID)

# Pending file path (single file)
script_dir = os.path.dirname(os.path.abspath(__file__))
PENDING_FILE = os.path.join(script_dir, "pending.json")

# Wait time (seconds) - send after this delay if question is on tmux screen
PENDING_WAIT_SECONDS = 30

bot = telebot.TeleBot(BOT_TOKEN)

# Store processed callback message IDs (prevent duplicates)
processed_callbacks = set()

# Claude input waiting state
waiting_for_claude_input = False

# Question index management (reset to 0 on startup)
current_question_idx = 0
# Question content storage (idx -> question keyword)
question_keywords = {}
# Last sent question content (for detecting new questions and invalidating old idx)
last_sent_msg = ""

# ========== Capture tmux screen and check for question messages ==========
def get_tmux_screen():
    """Capture tmux screen (remove ANSI codes)"""
    try:
        result = subprocess.run(
            ['tmux', 'has-session', '-t', TMUX_SESSION],
            capture_output=True
        )
        if result.returncode != 0:
            return ""

        result = subprocess.run(
            ['tmux', 'capture-pane', '-t', TMUX_SESSION, '-p', '-S', '-100'],
            capture_output=True, text=True
        )
        content = result.stdout

        # Remove ANSI escape codes
        import re
        content = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', content)
        content = re.sub(r'\x1b\].*?\x07', '', content)

        return content
    except Exception:
        return ""

def is_question_on_screen(question_msg):
    """Check if selection UI is currently active on tmux screen (bottom 5 lines only)"""
    screen = get_tmux_screen()
    if not screen:
        return False
    # Only check bottom 5 lines (ignore previous UI text in scrollback)
    bottom = '\n'.join(screen.split('\n')[-5:])
    return "Esc to cancel" in bottom or "Enter to select" in bottom

# ========== Pending File Monitoring (single file) ==========
def pending_monitor():
    """Send notification if pending.json exists and question is on tmux screen after delay"""
    global current_question_idx, last_sent_msg
    pending_start_time = {}  # Wait start time per message

    while True:
        try:
            if not os.path.exists(PENDING_FILE):
                pending_start_time.clear()
                time.sleep(2)
                continue

            # Check file size (skip if empty)
            if os.path.getsize(PENDING_FILE) == 0:
                pending_start_time.clear()
                time.sleep(2)
                continue

            with open(PENDING_FILE, 'r') as f:
                data = json.load(f)

            msg_text = data.get('message', '')
            buttons = data.get('buttons', [])

            if not msg_text:
                time.sleep(2)
                continue

            # Check if selection UI is on tmux screen
            if not is_question_on_screen(msg_text):
                # No selection UI - reset wait time and clear file (already handled)
                if msg_text in pending_start_time:
                    del pending_start_time[msg_text]
                open(PENDING_FILE, 'w').close()
                time.sleep(2)
                continue

            # Record wait start time if on screen
            if msg_text not in pending_start_time:
                pending_start_time[msg_text] = time.time()
                # If previous question was sent and content differs, invalidate immediately
                if last_sent_msg and msg_text != last_sent_msg:
                    current_question_idx += 1
                    log(f"⏭️ New question detected, Q{current_question_idx-1} invalidated → now Q{current_question_idx}")
                log(f"⏳ Question detected, waiting {PENDING_WAIT_SECONDS}s: {msg_text[:40]}...")

            # Check wait time
            elapsed = time.time() - pending_start_time[msg_text]
            if elapsed < PENDING_WAIT_SECONDS:
                time.sleep(1)
                continue

            # Before sending: verify question is still on screen
            if not is_question_on_screen(msg_text):
                log(f"⏭️ Already answered, skipping send: {msg_text[:40]}...")
                del pending_start_time[msg_text]
                open(PENDING_FILE, 'w').close()
                time.sleep(2)
                continue

            # Send notification
            try:
                current_question_idx += 1
                q_idx = current_question_idx

                if buttons:
                    markup = types.InlineKeyboardMarkup(row_width=len(buttons))
                    btn_list = []
                    for btn in buttons:
                        if ':' in btn:
                            label, choice = btn.rsplit(':', 1)
                            # callback_data format: "idx:choice" (e.g., "5:1")
                            callback_data = f"{q_idx}:{choice.strip()}"
                            btn_list.append(types.InlineKeyboardButton(label.strip(), callback_data=callback_data))
                    if btn_list:
                        markup.add(*btn_list)
                        result = bot.send_message(CHAT_ID, f"❓ [Q{q_idx}] {msg_text}", reply_markup=markup)
                    else:
                        result = bot.send_message(CHAT_ID, f"❓ [Q{q_idx}] {msg_text}")
                else:
                    result = bot.send_message(CHAT_ID, f"❓ [Q{q_idx}] {msg_text}")
                # Save question keyword (for callback verification)
                question_keywords[q_idx] = msg_text.split('\n')[0][:60]
                last_sent_msg = msg_text
                log(f"📤 Notification sent: [Q{q_idx}] {msg_text[:50]} (msg_id={result.message_id})")
            except Exception as send_err:
                log(f"❌ Notification failed: {send_err}")

            # Clear file and reset wait time
            del pending_start_time[msg_text]
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

def send_key_to_tmux(key):
    """Send special key to tmux session (Escape, Enter, Up, Down, etc.)"""
    try:
        # Check if tmux session exists
        result = subprocess.run(
            ['tmux', 'has-session', '-t', TMUX_SESSION],
            capture_output=True
        )
        if result.returncode != 0:
            return False, f"tmux session '{TMUX_SESSION}' not found"

        # Send special key
        subprocess.run(['tmux', 'send-keys', '-t', TMUX_SESSION, key], capture_output=True)
        return True, f"{key} key sent"
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
    global current_question_idx

    if call.message.chat.id != CHAT_ID:
        return

    # Check if message already processed (prevent duplicates)
    msg_id = call.message.message_id
    if msg_id in processed_callbacks:
        bot.answer_callback_query(call.id, "⚠️ Already processed")
        return

    # Parse button data: "idx:choice" format (e.g., "5:1")
    callback_data = call.data
    if ':' in callback_data:
        q_idx_str, choice = callback_data.split(':', 1)
        try:
            q_idx = int(q_idx_str)
        except ValueError:
            q_idx = 0
            choice = callback_data
    else:
        # Legacy format compatibility (number only)
        q_idx = current_question_idx
        choice = callback_data

    # Condition 1: Check if this is the latest question
    if q_idx != current_question_idx:
        log(f"⏰ Expired question: Q{q_idx} (current: Q{current_question_idx})")
        bot.answer_callback_query(call.id, f"⏰ Expired question.")
        # Remove buttons
        try:
            original_text = call.message.text
            bot.edit_message_text(
                f"{original_text}\n\n⏰ Expired question. (Q{q_idx} → current Q{current_question_idx})",
                call.message.chat.id,
                msg_id,
                reply_markup=None
            )
        except:
            pass
        return

    # Condition 2: Check if selection UI is still active on tmux screen bottom
    screen = get_tmux_screen()
    bottom = '\n'.join(screen.split('\n')[-5:]) if screen else ""
    if "Esc to cancel" not in bottom and "Enter to select" not in bottom:
        log(f"⏰ Already selected (on PC): Q{q_idx}")
        bot.answer_callback_query(call.id, "⏰ Already selected on PC.")
        try:
            original_text = call.message.text
            bot.edit_message_text(
                f"{original_text}\n\n⏰ Already selected on PC.",
                call.message.chat.id,
                msg_id,
                reply_markup=None
            )
        except:
            pass
        return

    # Send arrow keys + Enter to Claude Code selection UI
    success, msg = send_selection_to_tmux(choice)

    if success:
        # Mark as processed
        processed_callbacks.add(msg_id)
        log(f"✅ Button clicked: Q{q_idx} - option {choice}")
        bot.answer_callback_query(call.id, f"✅ Option {choice} selected")
        # Remove buttons and show selection result
        try:
            original_text = call.message.text
            bot.edit_message_text(
                f"{original_text}\n\n✅ Selected: option {choice}",
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

# /2 - Select option 2
@bot.message_handler(commands=['2'])
def cmd_2(message):
    if not is_authorized(message):
        return

    success, msg = send_to_tmux("2")
    if success:
        bot.reply_to(message, "✅ Option 2 selected\n⏳ Processing...")
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

# /esc - Send ESC key
@bot.message_handler(commands=['esc'])
def cmd_esc(message):
    if not is_authorized(message):
        return

    success, msg = send_key_to_tmux("Escape")
    if success:
        log("⎋ ESC key sent")
        bot.reply_to(message, "⎋ ESC key sent")
    else:
        bot.reply_to(message, f"❌ Failed: {msg}")

# /claude <message> - Direct input to Claude
@bot.message_handler(commands=['claude', 'c'])
def cmd_claude(message):
    global waiting_for_claude_input
    if not is_authorized(message):
        return

    # Extract message after command
    text = message.text.split(maxsplit=1)
    if len(text) < 2:
        # No message, enter waiting mode
        waiting_for_claude_input = True
        bot.reply_to(message, "✏️ Enter message to send to Claude:", reply_markup=get_main_keyboard())
        return

    user_input = text[1]
    success, msg = send_to_tmux(user_input)

    if success:
        bot.reply_to(message, f"✅ Sent: {user_input[:50]}...\n⏳ Processing...", reply_markup=get_main_keyboard())
    else:
        bot.reply_to(message, f"❌ Failed: {msg}", reply_markup=get_main_keyboard())

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

        bot.reply_to(message, f"📺 Claude CLI:\n{content}")

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

# Create keyboard buttons
def get_main_keyboard():
    """Create main keyboard buttons"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.row(
        types.KeyboardButton("1"),
        types.KeyboardButton("2"),
        types.KeyboardButton("3"),
        types.KeyboardButton("4"),
        types.KeyboardButton("ST"),
        types.KeyboardButton("TL"),
        types.KeyboardButton("CLD")
    )
    return keyboard

# /help - Help
@bot.message_handler(commands=['help', 'start'])
def cmd_help(message):
    if not is_authorized(message):
        return

    help_text = """🤖 Claude Code Remote Control

**Select:** 1, 2, 3, 4
**Cancel:** /esc (ESC key)
**Status:** ST (status)
**Log:** TL (tail)
**Input:** CLD (claude)
"""
    bot.reply_to(message, help_text, reply_markup=get_main_keyboard())

# Handle text messages (buttons and Claude input waiting)
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    global waiting_for_claude_input
    if not is_authorized(message):
        return

    text = message.text.strip()

    # Handle button commands
    if text in ["1", "2", "3", "4"]:
        success, msg = send_to_tmux(text)
        if success:
            bot.reply_to(message, f"✅ Option {text} selected\n⏳ Processing...", reply_markup=get_main_keyboard())
        else:
            bot.reply_to(message, f"❌ Failed: {msg}", reply_markup=get_main_keyboard())
        return

    if text.lower() == "tl":
        cmd_tail(message)
        return

    if text.lower() == "st":
        cmd_status(message)
        return

    if text.lower() == "cld":
        waiting_for_claude_input = True
        bot.reply_to(message, "✏️ Enter message to send to Claude:", reply_markup=get_main_keyboard())
        return

    # If waiting for Claude input, send message to Claude
    if waiting_for_claude_input:
        waiting_for_claude_input = False
        success, msg = send_to_tmux(text)

        if success:
            bot.reply_to(message, f"✅ Sent: {text[:50]}...\n⏳ Processing...", reply_markup=get_main_keyboard())
        else:
            bot.reply_to(message, f"❌ Failed: {msg}", reply_markup=get_main_keyboard())

def kill_previous_bot():
    """Terminate previously running telegram_bot.py processes"""
    import signal
    my_pid = os.getpid()
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'telegram_bot.py'],
            capture_output=True, text=True
        )
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            pid = int(line.strip())
            if pid != my_pid:
                log(f"🔪 Terminating previous bot process: PID {pid}")
                os.kill(pid, signal.SIGTERM)
    except Exception as e:
        log(f"⚠️ Failed to terminate previous process: {e}")

if __name__ == "__main__":
    kill_previous_bot()
    log("🤖 Telegram bot started")
    log(f"   Session: {TMUX_SESSION}")
    log(f"   Chat ID: {CHAT_ID}")
    log(f"   Wait time: {PENDING_WAIT_SECONDS} seconds")

    # Clear pending.json on startup (remove expired questions from previous session)
    try:
        open(PENDING_FILE, 'w').close()
        log("🗑️ Previous pending cleared")
    except:
        pass

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
