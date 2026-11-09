"""
Pico2WClaw: A minimal agentic AI runtime for Raspberry Pi Pico 2 W.
Runs MicroPython, connects to WiFi, calls an OpenAI-compatible LLM API,
executes tools (GPIO, sensors), and persists simple memory.
"""

# =============================================================================
# config.py — WiFi, LLM provider, and device settings
# =============================================================================

WIFI_SSID = "YOUR_WIFI_SSD"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

# LLM provider (OpenAI-compatible endpoint)
# DeepSeek API (primary)
LLM_BASE_URL = "https://api.deepseek.com/v1"
LLM_API_KEY = "LLM_API_KEY"
LLM_MODEL = "deepseek-chat"  # pick a small/fast model

# Fallback LLM provider (used only when primary is unavailable)
LLM_FALLBACK_ENABLED = True
LLM_FALLBACK_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
LLM_FALLBACK_API_KEY = "«redacted:AIza…»"
LLM_FALLBACK_MODEL = "gemini-2.0-flash"

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
# WiFi recovery (non-blocking reconnect in main loop)
WIFI_RECONNECT_ENABLED = True
WIFI_RECONNECT_COOLDOWN_MS = 10000
WIFI_AUTO_SOFT_RESET_MS = 0  # 0 disables automatic soft reset after prolonged outage
