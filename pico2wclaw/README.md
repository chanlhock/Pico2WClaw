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
| `boot.py` | Entry point — WiFi, NTP, starts agent + Telegram thread |
| `agent.py` | Agent loop — LLM call, tool execution, memory, skills |
| `tools.py` | Tool registry: GPIO, ADC, PWM, I2C, exec, info, LED blink, buzzer |
| `pico_memory.py` | File-backed keyword memory store (default: `/memory/`) |
| `pico_cron.py` | Interval cron scheduler — GPIO/ADC monitoring + Telegram status (persisted in `/cron/jobs.txt`) |
| `skills_loader.py` | Loads `skills/*.py` skill files at agent startup |
| `led_blink.py` | Persistent onboard-LED blink helper (`led_blink_start` by Hz, `start_blink` by ms period, `led_blink_stop`, `led_toggle`) |
| `config.py` | WiFi SSID/password, LLM API key/model, Telegram bot token |
| `ssd1306.py` | SSD1306 OLED I2C driver (required for display output) |
| `display.py` | OLED + buzzer wrapper: status UI, boot splash, tone playback |

## Setup

1. Install MicroPython for Pico 2 W:
   https://datasheets.raspberrypi.com/pico/getting-started-with-pico.pdf
   (use the **RP2350** UF2)

2. Create a `skills/` folder on the Pico if you want to add custom skills.

3. Copy files to the Pico:
   - Open **Thonny**
   - Select **MicroPython (RP2350)** as the interpreter
   - Save `config.py` to the Pico and edit your WiFi + API key + Telegram bot token
   - Save `boot.py`, `agent.py`, `pico_memory.py`, `tools.py`, `led_blink.py`, `ssd1306.py`, `display.py`, `skills_loader.py`, `pico_cron.py` to the Pico
   - If you have custom skills, create the `skills/` folder and place your `.py` skill files inside

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
- `/skills` — list loaded skills
- `/skill_read <name>` — read a skill's instruction text
- `/help` — show command help
- `/cron` — manage cron jobs (`list`/`add`/`del`/`on`/`off`)
- `/exit` — stop the agent (serial + Telegram)
- `/model` — show LLM provider and model
- `/wifi` — check/reconnect WiFi

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

## Skills

Pico2WClaw supports extensible **MicroPython skills** placed in a `skills/` folder. Each skill is a `.py` module that exposes:

- `SKILL_INSTR` — instruction text injected into the LLM system prompt
- `TOOLS` — optional dict of tool definitions with callable references

At startup, `agent.py` calls `skills_loader.load_skills()`, which scans `skills/*.py`, loads their instructions into the system prompt under `[Loaded skills]`, and merges any tool definitions into the main `TOOL_REGISTRY`.

Available serial/Telegram commands:
- `/skills` — list all loaded skill names
- `/skill_read <name>` — read a skill's `SKILL_INSTR` text
- `/cron` — manage cron jobs (`list`/`add`/`del`/`on`/`off`)
- `/cron add <gpio|adc> <pin> <interval_ms> [chat_id] [message...]`
- `/exit` — stop the agent (serial + Telegram)
- `/model` — show LLM provider and model
- `/wifi` — check/reconnect WiFi

### Cron examples
```text
/cron                          # list jobs
/cron list                     # list jobs
/cron add gpio 25 5000         # read GPIO25 every 5s, send to default chat
/cron add adc 26 10000         # read ADC26 every 10s
/cron add adc 26 10000 8684515324 "ADC26 reading"   # custom chat + message
/cron on 1                     # enable job id 1
/cron off 1                    # disable job id 1
/cron del 1                    # delete job id 1
```
Message templates support `{value}`, `{pin}`, `{type}` placeholders, e.g. `GPIO{pin}={value}`.

Jobs are persisted in `/cron/jobs.txt` (survives `/clear` and reboots). Only one job runs per tick; execution uses the main loop (no LLM call).

**Skill file contract:**
```python
SKILL_INSTR = "1-3 sentences describing when and how to use this skill."

TOOLS = {
    "tool_name": {
        "description": "What it does.",
        "parameters": {...},
        "callable": some_function,
    }
}
```

**Important MicroPython constraints:**
- Import every dependency at the top of the skill file (`time`, `machine`, etc.). The `exec()` namespace does not inherit the agent's globals.
- Do not name skill files `memory.py`, `time.py`, `re.py`, etc. — they may shadow built-ins. Use project-prefixed names.
- Avoid heavy stdlib: no `collections.Counter`, `re.findall`, `str.isalnum`, or `os.path`.
- Skills are executed in an isolated `exec()` namespace. No side effects at import time.

## OLED + Buzzer

The agent auto-initialises the SSD1306 display and buzzer on boot:
- **Display**: I2C on GPIO20/21, 128×64
- **Buzzer**: PWM on GPIO22
- **Status updates**: Ready, Thinking, Tool, Error, WiFi/LLM status
- **Beeps**: Success tone (ascending), error tone (descending), click tick

The LLM can also control the display and buzzer via `display_text`, `display_bottom`, `clear_display_bottom`, and `beep_now` tools.
- **Layout**: 8 lines at 8px spacing. Top 4 lines are persistent status/title; bottom 4 lines are transient detail.
- **Tunes**: `buzzer_play_tune` accepts an optional `title` and shows it on the bottom lines during playback, then clears them.

## LLM Provider

Set `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in `config.py`.

Works with any OpenAI-compatible API:
- OpenAI GPT-4o / GPT-4o-mini
- Google Gemini (via `/v1beta/openai` compatibility endpoint)
- Ollama local (`http://<ip>:11434/v1`)
- OpenRouter, Groq, Together AI, etc.

For best latency on Pico, use a fast/small model (e.g., `gemini-2.0-flash-lite`, `gpt-4o-mini`).

## Notes

- Memory is persisted to `/memory/transcript.txt` on the Pico's flash filesystem. No SD card is required.
- Skills are loaded from the `skills/` directory at agent startup. Each skill is a MicroPython `.py` module with `SKILL_INSTR` and optional `TOOLS`.
- Do not name files `memory.py`, `time.py`, `re.py`, etc. — they may shadow MicroPython built-ins. The memory module is named `pico_memory.py` to avoid this.
- Tool calls are recursive up to `TOOL_CALL_MAX_ROUNDS` (default 4) per turn.
- No sub-agents or cron — kept simple for 520 KB SRAM.
