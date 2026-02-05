#!/bin/bash
# Telegram send utility script
# Usage: source ".nexus/system/telegram.sh"
#        tg_send "message content"

# Find project root based on script location
_TG_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_TG_PROJECT_ROOT="$(cd "$_TG_SCRIPT_DIR/../.." && pwd)"
_TG_SETTINGS_FILE="$_TG_PROJECT_ROOT/.nexus/settings/nexus.properties"

# Function to read settings value
tg_get_property() {
    local key="$1"
    local settings="${2:-$_TG_SETTINGS_FILE}"
    grep -E "^[[:space:]]*${key}=" "$settings" 2>/dev/null | head -n1 | cut -d'=' -f2-
}

# Send telegram message (with parse_mode option)
tg_send() {
    local message="$1"
    local parse_mode="${2:-}"  # HTML or MarkdownV2

    local USE_YN BOT_TOKEN CHAT_ID
    USE_YN=$(tg_get_property "project.bot.useYn")
    BOT_TOKEN=$(tg_get_property "project.bot.token")
    CHAT_ID=$(tg_get_property "project.bot.chatid")

    # Exit silently if disabled or settings missing
    if [ "$USE_YN" != "y" ] || [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ] || [ -z "$message" ]; then
        return 0
    fi

    # Telegram length limit (4096 chars) - safely truncate at 3500
    if [ ${#message} -gt 3500 ]; then
        message="${message:0:3500}
...(truncated)"
    fi

    # Safely generate JSON with jq
    local payload
    if [ -n "$parse_mode" ]; then
        payload=$(jq -n \
            --arg chat_id "$CHAT_ID" \
            --arg text "$message" \
            --arg parse_mode "$parse_mode" \
            '{chat_id: ($chat_id | tonumber), text: $text, parse_mode: $parse_mode}')
    else
        payload=$(jq -n \
            --arg chat_id "$CHAT_ID" \
            --arg text "$message" \
            '{chat_id: ($chat_id | tonumber), text: $text}')
    fi

    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -H "Content-Type: application/json" \
        -d "$payload" >/dev/null 2>&1
}

# Send message with project name header
tg_send_with_header() {
    local title="$1"
    local content="$2"

    local PROJECT_NAME
    PROJECT_NAME=$(tg_get_property "project.name")
    PROJECT_NAME="${PROJECT_NAME:-Project}"

    local message="${title} [${PROJECT_NAME}]
━━━━━━━━━━━━━━━━━━━━
${content}
━━━━━━━━━━━━━━━━━━━━"

    tg_send "$message"
}

# Send as HTML code block (<pre> tag)
tg_send_code() {
    local title="$1"
    local content="$2"

    local PROJECT_NAME
    PROJECT_NAME=$(tg_get_property "project.name")
    PROJECT_NAME="${PROJECT_NAME:-Project}"

    # Escape HTML special characters
    content="${content//&/&amp;}"
    content="${content//</&lt;}"
    content="${content//>/&gt;}"

    local message="<b>${title}</b> [${PROJECT_NAME}]
<pre>${content}</pre>"

    tg_send "$message" "HTML"
}

# Send with inline buttons
# Usage: tg_send_buttons "message" "button1:callback1" "button2:callback2" ...
tg_send_buttons() {
    local message="$1"
    shift
    local buttons=("$@")

    local USE_YN BOT_TOKEN CHAT_ID PROJECT_NAME
    USE_YN=$(tg_get_property "project.bot.useYn")
    BOT_TOKEN=$(tg_get_property "project.bot.token")
    CHAT_ID=$(tg_get_property "project.bot.chatid")
    PROJECT_NAME=$(tg_get_property "project.name")
    PROJECT_NAME="${PROJECT_NAME:-Project}"

    if [ "$USE_YN" != "y" ] || [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ]; then
        return 0
    fi

    # Generate button JSON
    local keyboard="["
    local first=true
    for btn in "${buttons[@]}"; do
        local label="${btn%%:*}"
        local callback="${btn##*:}"
        if [ "$first" = true ]; then
            first=false
        else
            keyboard+=","
        fi
        keyboard+="{\"text\":\"${label}\",\"callback_data\":\"${callback}\"}"
    done
    keyboard+="]"

    local full_message="🔔 [${PROJECT_NAME}]
${message}"

    # Safely generate JSON with jq
    local payload
    payload=$(jq -n \
        --arg chat_id "$CHAT_ID" \
        --arg text "$full_message" \
        --argjson keyboard "$keyboard" \
        '{chat_id: ($chat_id | tonumber), text: $text, reply_markup: {inline_keyboard: [$keyboard]}}')

    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -H "Content-Type: application/json" \
        -d "$payload" >/dev/null 2>&1
}

# Send permission request (with inline buttons)
tg_send_permission() {
    local tool_name="$1"
    local detail="$2"

    local message="Proceed with ${tool_name}?
→ ${detail}"

    tg_send_buttons "$message" "1) Yes:1" "2) Allow:2" "3) No:3"
}

# Send question (dynamic buttons)
# Usage: tg_send_question "question" "option1" "option2" "option3"
tg_send_question() {
    local question="$1"
    shift
    local options=("$@")

    local buttons=()
    local i=1
    for opt in "${options[@]}"; do
        buttons+=("${i}) ${opt}:${i}")
        ((i++))
    done

    tg_send_buttons "$question" "${buttons[@]}"
}
