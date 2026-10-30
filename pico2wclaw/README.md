# Pico2WClaw

A minimal agentic AI runtime for the **Raspberry Pi Pico 2 W** (RP2350, 520 KB SRAM, 4 MB flash, WiFi).

This is a heavily trimmed-down port of the Pico2WClaw/OpenClaw concept:
- ✅ LLM API integration (OpenAI-compatible)
- ✅ Tool calling (GPIO, ADC, PWM, I2C, exec)
- ✅ On-device memory (keyword-based)
- ✅ Serial chat REPL (via Thonny / USB serial)
- ✅ WiFi + NTP sync
- ⛔ Sub-agents, MCP, LVGL, CAN, vector memory (removed to fit 520 KB SRAM)

## Files

| File | Role |
|---|---|
| `boot.py` | Entry point — WiFi, NTP, starts agent |
| `agent.py` | Agent loop — LLM call, tool execution, memory |
| `memory.py` | File-backed keyword memory store |
| `tools.py` | Tool registry: GPIO, ADC, PWM, I2C, exec, info, LED blink |
| `led_blink.py` | Persistent onboard-LED blink helper (`led_blink_start` by Hz, `start_blink` by ms period, `led_blink_stop`, `led_toggle`) |
| `config.py` | WiFi SSID/password, LLM API key/model, Telegram bot token |

## Setup

1. Install MicroPython for Pico 2 W:
   https://datasheets.raspberrypi.com/pico/getting-started-with-pico.pdf
   (use the **RP2350** UF2)

2. Copy files to the Pico:
   - Open **Thonny**
   - Select **MicroPython (RP2350)** as the interpreter
   - Save `config.py` to the Pico and edit your WiFi + API key + Telegram bot token
   - Save `boot.py`, `agent.py`, `memory.py`, `tools.py`, `led_blink.py`, `ssd1306.py`, `display.py` to the Pico

3. Power-cycle the Pico. It will connect to WiFi and print a `>` prompt.

## Usage

At the `>` prompt, type messages like:
- `Turn on LED on GPIO 25`
- `Read temperature from ADC 26`
- `Scan the I2C bus`
- `Display "Hello" on line 1`
- `Beep at 1000Hz for 0.2s`
- `Run this code: print(1+1)`
- `/info` — show hardware info (CPU, RAM, flash, temp, WiFi, MicroPython)
- `/tools` — list available tools
- `/memory` — search memory
- `/clear` — wipe history and memory
- `/help` — show command help

## Onboard LED Blinking

Use `led_blink_start`, `start_blink`, `led_blink_stop`, and `led_toggle` for persistent control of the onboard LED. The onboard LED on Pico W / Pico 2 W is driven by the CYW43 chip; this helper uses `Pin("LED")` so it works without wiring an external LED.

- `start_blink(period_ms=2000)` — recommended when the user specifies a duration like "every 2 seconds". `period_ms` is how long the LED stays in each state. `period_ms=2000` = 2s ON, 2s OFF.
- `led_blink_start(freq_hz=1)` — use when the user specifies a frequency like "1 Hz" or "blink twice per second".
- `led_blink_stop()` — stop blinking and turn LED off.
- `led_toggle()` — single manual toggle.

Example Telegram/serial prompts:
- `Blink the onboard LED every 2 seconds` → calls `start_blink(2000)`
- `Blink the onboard LED at 1 Hz` → calls `led_blink_start(1)`
- `Stop blinking`
- `Toggle the LED once`

## Telegram Bot

If `TELEGRAM_BOT_TOKEN` is set in `config.py`, the agent polls Telegram every 3 seconds and replies to messages automatically.

1. Create a bot via [@BotFather](https://t.me/BotFather) and copy the token
2. Set `TELEGRAM_BOT_TOKEN` in `config.py`
3. Open Telegram, search for your bot, and press **Start**
4. Optionally set `TELEGRAM_ALLOWED_USERS = [<your numeric Telegram user id>]` to restrict access

Replies go through the same LLM + tools pipeline as serial input.

## OLED + Buzzer

The agent auto-initialises the SSD1306 display and buzzer on boot:
- **Display**: I2C on GPIO20/21, 128×64
- **Buzzer**: PWM on GPIO22
- **Status updates**: Ready, Thinking, Tool, Error, WiFi/LLM status
- **Beeps**: Success tone (ascending), error tone (descending), click tick

The LLM can also control the display and buzzer via `display_text` and `beep_now` tools.

## LLM Provider

Set `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in `config.py`.

Works with any OpenAI-compatible API:
- OpenAI GPT-4o / GPT-4o-mini
- Google Gemini (via `/v1beta/openai` compatibility endpoint)
- Ollama local (`http://<ip>:11434/v1`)
- OpenRouter, Groq, Together AI, etc.

For best latency on Pico, use a fast/small model (e.g., `gemini-2.0-flash-lite`, `gpt-4o-mini`).

## Notes

- The memory file is stored at `/sd/memory/transcript.txt`. Create an `/sd` directory if using external storage.
- Tool calls are recursive up to `TOOL_CALL_MAX_ROUNDS` (default 4) per turn.
- No sub-agents or cron — kept simple for 520 KB SRAM.
