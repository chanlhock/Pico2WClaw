"""
Pico2WClaw: A minimal agentic AI runtime for Raspberry Pi Pico 2 W.
Runs MicroPython, connects to WiFi, calls an OpenAI-compatible LLM API,
executes tools (GPIO, sensors), and persists simple memory.
"""

# =============================================================================
# config.py — WiFi, LLM provider, and device settings
# =============================================================================

WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

# LLM provider (OpenAI-compatible endpoint)
# DeepSeek API
LLM_BASE_URL = "https://api.deepseek.com/v1"
LLM_API_KEY = "YOUR_API_KEY_HERE"
LLM_MODEL = "deepseek-chat"  # pick a small/fast model
# For OpenAI: "https://api.openai.com/v1"
# For Ollama local: "http://192.168.1.100:11434/v1"

# Telegram bot (optional — leave TOKEN="" to disable)
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_ALLOWED_USERS = []  # e.g. [123456789]

# Agent behaviour
AGENT_NAME = "Pico2WClaw"
SYSTEM_PROMPT = (
    "You are Pico2WClaw, a helpful embedded AI agent running on a Raspberry Pi Pico 2 W. "
    "You can read/write GPIO pins, read sensors, execute MicroPython code, and remember things. "
    "Be concise. Use tools when needed."
)
MAX_CONTEXT_TOKENS = 4000  # keep small for 520 KB SRAM
MAX_RESPONSE_TOKENS = 512
TOOL_CALL_MAX_ROUNDS = 4    # safety cap per turn
MEMORY_MAX_SNIPPETS = 5
MEMORY_MAX_CHARS = 1500

# Cron scheduler (interval-based monitoring -> Telegram)
CRON_ENABLED = True
CRON_TICK_MS = 1000
CRON_DEFAULT_CHAT_ID = None  # falls back to first TELEGRAM_ALLOWED_USERS entry


