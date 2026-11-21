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
| `boot2.py` | Entry point — WiFi, NTP, WDT init, starts agent + Telegram thread |
| `agent.py` | Agent loop — LLM call, tool execution, memory, skills |
| `tools.py` | Tool registry: GPIO, ADC, PWM, I2C, exec, info, LED blink, buzzer, DHT11 |
| `pico_memory.py` | File-backed keyword memory store (default: `/memory/`) |
| `pico_cron.py` | Interval cron scheduler — GPIO/ADC/DHT monitoring + Telegram status (persisted in `/cron/jobs.txt`) |
| `skills_loader.py` | Loads `skills/*.py` skill files at agent startup |
| `led_blink.py` | Persistent onboard-LED blink helper (`led_blink_start` by Hz, `start_blink` by ms period, `led_blink_stop`, `led_toggle`) |
| `config.py` | WiFi SSID/password, LLM API key/model, Telegram bot token, plus optional WATCHDOG_* settings |
| `ssd1306.py` | SSD1306 OLED I2C driver (required for display output) |
| `display.py` | OLED + buzzer wrapper: status UI, boot splash, tone playback |
| `watchdog` | Hardware watchdog module (RP2350) — automatic reset on hang, reset logging to `/wdt.log` |

## Setup

1. Install MicroPython for Pico 2 W:
   https://datasheets.raspberrypi.com/pico/getting-started-with-pico.pdf
   (use the **RP2350** UF2)

2. Create a `skills/` folder on the Pico if you want to add custom skills.

3. Copy files to the Pico:
   - Open **Thonny**
   - Select **MicroPython (RP2350)** as the interpreter
   - Save `config.py` to the Pico and edit your WiFi + API key + Telegram bot token
   - Save `boot2.py`, `agent.py`, `pico_memory.py`, `tools.py`, `led_blink.py`, `ssd1306.py`, `display.py`, `skills_loader.py`, `pico_cron.py`, `watchdog` to the Pico
   - If you have custom skills, create the `skills/` folder and place your `.py` skill files inside

3. Power-cycle the Pico. It will connect to WiFi and print a `>` prompt.

## Usage

At the `>` prompt, type messages like:

- `Turn on LED on GPIO 25`
- `Read temperature from ADC 26`
- `Scan the I2C bus`
- `Display "Hello" on line 1`
- `Beep at 1000Hz for 0.2s`
- `Read DHT11 on GPIO4`
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
- `/wdt` — show watchdog status and recent watchdog reset log
- `/wdt_test` — trigger a deliberate hang to test the watchdog (hardware reset after timeout)

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

Pico2WClaw supports extensible **MicroPython skills** — self-contained `.py` modules in a `skills/` folder. Each skill is a reusable component that the agent can invoke to perform a specific task. Skills are loaded at agent startup and their instructions are injected into the LLM system prompt.

### Skill file contract

A skill is a MicroPython `.py` module that exposes two variables:

```python
# my_skill.py
SKILL_INSTR = "1-3 sentences describing when and how to use this skill."

TOOLS = {
    "tool_name": {
        "description": "What it does.",
        "parameters": {...},
        "callable": some_function,
    }
}
```

- **`SKILL_INSTR`** — instruction text (1-3 sentences) injected into the LLM system prompt. The LLM uses this to decide when to call the skill.
- **`TOOLS`** — optional dict of tool definitions. Each entry maps a tool name to:
  - `description` — what the tool does (shown to the LLM)
  - `parameters` — JSON schema of the tool's input parameters
  - `callable` — the MicroPython function to execute when the tool is called

When a skill is loaded, `skills_loader.py` scans `skills/*.py`, loads each `SKILL_INSTR` into the system prompt under `[Loaded skills]`, and merges any tool definitions into the main `TOOL_REGISTRY` (from `agent.py`).

### Creating a skill

1. Create a file in the `skills/` folder, e.g., `skills/my_skill.py`
2. Define `SKILL_INSTR` with a clear description of when and how to use the skill
3. Optionally define `TOOLS` with callable functions
4. Import any required dependencies at the top of the file

### MicroPython constraints

- Import every dependency at the top of the skill file (`time`, `machine`, etc.). The `exec()` namespace does not inherit the agent's globals.
- Do not name skill files `memory.py`, `time.py`, `re.py`, etc. — they may shadow built-ins. Use project-prefixed names.
- Avoid heavy stdlib: no `collections.Counter`, `re.findall`, `str.isalnum`, or `os.path`.
- Skills are executed in an isolated `exec()` namespace. No side effects at import time.

## Cron

Pico2WClaw includes an interval-based **cron scheduler** (`pico_cron.py`) that runs periodic background tasks at fixed intervals. Cron jobs execute in the main loop without LLM calls — they are pure MicroPython callbacks.

### Supported cron types

| Type | Description | Required parameters |
|---|---|---|
| `gpio` | Read a GPIO pin's state at an interval | `<pin> <interval_ms>` |
| `adc` | Read an ADC pin's value at an interval | `<pin> <interval_ms>` |
| `dht` | Read DHT11 temperature/humidity at an interval | `<pin> <interval_ms>` |

### Cron commands

| Command | Description |
|---|---|
| `/cron` | List all jobs |
| `/cron list` | List all jobs |
| `/cron add <type> <pin> <interval_ms> [chat_id] [message...]` | Add a new cron job |
| `/cron on <id>` | Enable job id |
| `/cron off <id>` | Disable job id |
| `/cron del <id>` | Delete job id |

### Cron job types and examples

#### GPIO polling

Read a GPIO pin state at a fixed interval:

```text
/cron add gpio 25 5000         # read GPIO25 every 5s, send to default chat
/cron add gpio 2 1000          # read GPIO2 every 1s
```

Example message template:

```text
GPIO{pin}={value}              # e.g., "GPIO25=1"
```

#### ADC polling

Read an ADC pin's analog value at a fixed interval:

```text
/cron add adc 26 10000         # read ADC26 every 10s, send to default chat
/cron add adc 27 5000 8684515324 "ADC27 reading"   # custom chat + message
```

Example message template:

```text
ADC{pin}={value}               # e.g., "ADC26=521"
```

#### DHT11 sensor

Read DHT11 temperature/humidity at a fixed interval:

```text
/cron add dht 4 300000         # read DHT11 on GPIO4 every 5min
/cron add dht 5 600000         # read DHT11 on GPIO5 every 10min
```

Example message template:

```text
temp {temp}C, humidity {hum}%  # e.g., "temp 28C, humidity 62%"
```

### Message templates

Cron jobs support message templates with placeholders. The `{value}`, `{pin}`, `{type}`, `{temp}`, and `{hum}` placeholders are filled from the latest reading:

- `{value}` — the raw sensor value
- `{pin}` — the GPIO/ADC pin number
- `{type}` — the cron type (`gpio`, `adc`, or `dht`)
- `{temp}` — the temperature value (for DHT11)
- `{hum}` — the humidity value (for DHT11)

Example:

```text
From DHT11 on GPIO4: temp {temp}C, humidity {hum}%
```

### Job persistence

Jobs are persisted in `/cron/jobs.txt` (survives `/clear` and reboots). Only one job runs per tick; execution uses the main loop (no LLM call).

## Watchdog (WDT)

The project supports a hardware watchdog timer (RP2350) for automatic recovery from hangs. When enabled, the boot script (`boot2.py`) initializes the watchdog and a periodic feed timer. If the board hangs for longer than `WATCHDOG_TIMEOUT_MS`, the hardware resets the Pico automatically.

### Configuration (`config.py`)

```python
WATCHDOG_ENABLED = True
WATCHDOG_TIMEOUT_MS = 4000          # WDT timeout (ms) — after this, the hardware resets
WATCHDOG_FEED_INTERVAL_MS = 500     # feed interval (ms) — must be less than timeout
WATCHDOG_LOG_FILE = "/wdt.log"      # reset log file
WATCHDOG_LOG_MAX_LINES = 20         # max lines kept in the reset log
```

### How it works

1. **Boot**: `boot2.py` reads the `WATCHDOG_*` settings from `config.py` and initializes the hardware watchdog.
2. **Feeding**: A hardware timer feeds the watchdog every `WATCHDOG_FEED_INTERVAL_MS` milliseconds.
3. **Hang detection**: If the main program stops running (e.g., stuck in an infinite loop, waiting on a failed network call, or crashed), the watchdog is not fed. After `WATCHDOG_TIMEOUT_MS` without a feed, the RP2350's hardware triggers a system reset.
4. **Reset logging**: On reset, the boot script logs the event with the current time (converted to UTC+8) to `WATCHDOG_LOG_FILE` (default `/wdt.log`). The log keeps up to `WATCHDOG_LOG_MAX_LINES` entries.
5. **Recovery**: The Pico boots back up, re-syncs WiFi and NTP, and resumes the agent.

### WDT status and control

| Command | Description |
|---|---|
| `/wdt` | Show WDT status and recent reset log entries from `/wdt.log` |
| `/wdt_test` | Trigger a deliberate hang by spinning an infinite loop — the watchdog resets the board after `WATCHDOG_TIMEOUT_MS`. Use to verify the watchdog works. |

Example `/wdt` output:

```text
WDT enabled: True
Latest reset: 2026-11-11 08:31:22+0800
Recent resets (up to 5):
  2026-11-11 08:31:22+0800
  2026-11-10 14:22:09+0800
```

Example `/wdt_test` flow:

1. `> /wdt_test` — agent enters an infinite loop
2. Wait ~4 seconds (if `WATCHDOG_TIMEOUT_MS = 4000`)
3. Hardware reset occurs; the Pico reboots
4. `/wdt` shows the latest reset entry in `/wdt.log`

To disable the watchdog, send `/exit`. The agent deinitializes the WDT, updates `config.py`, and stops.

### WDT test example

```text
> /wdt
WDT enabled: False

> config.py
WATCHDOG_ENABLED = True
WATCHDOG_TIMEOUT_MS = 4000
WATCHDOG_FEED_INTERVAL_MS = 500
WATCHDOG_LOG_FILE = "/wdt.log"
WATCHDOG_LOG_MAX_LINES = 20

> /wdt_test
(wait ~4s)
[hardware reset]

> /wdt
WDT enabled: True
Latest reset: 2026-11-12 09:15:33+0800
Recent resets (up to 5):
  2026-11-12 09:15:33+0800

> cat /wdt.log
2026-11-12 09:15:33+0800 — WDT triggered reset
```

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
- The hardware watchdog (`watchdog` module) automatically resets the board if the program hangs for longer than the configured `WATCHDOG_TIMEOUT_MS`. Recent resets are recorded in `/wdt.log`.
