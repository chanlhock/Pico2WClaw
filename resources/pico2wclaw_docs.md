# Pico2WClaw Technical Documentation

## 1. Introduction

Pico2WClaw is a minimal agentic AI runtime for the Raspberry Pi Pico 2 W. It runs MicroPython, connects to WiFi, communicates with users via a serial REPL and a Telegram bot, calls an OpenAI-compatible LLM API (DeepSeek by default), executes hardware tools (GPIO, sensors, display, buzzer, LED), schedules recurring monitors, loads pluggable skills, and persists a simple keyword-based memory on the filesystem.

The system is designed around a tight resource budget: 520 KB SRAM, 4 MB flash, and MicroPython's constrained standard library. Every design decision—from avoiding `collections.Counter` to using `machine.Timer(0)` with a minimum-gap guard—reflects these constraints.

---

## 2. System Architecture

Pico2WClaw consists of the following modules:

| Module | File | Purpose |
|--------|------|---------|
| Boot | `boot.py` | WiFi connection, NTP sync, display splash, start agent + Telegram thread |
| Agent | `agent.py` | Core loop, LLM client, tool orchestration, serial REPL, Telegram polling, cron tick |
| Tools | `tools.py` | Tool registry, JSON schemas for LLM, hardware callables (GPIO, ADC, PWM, I2C, exec, display, buzzer, LED, cron) |
| Memory | `memory.py` (as `pico_memory.py`) | On-device keyword/TF-IDF memory, persisted to `/memory/transcript.txt` |
| Display | `display.py` | SSD1306 OLED driver wrapper, buzzer tones, status UI, boot splash |
| LED Blink | `led_blink.py` | Persistent onboard-LED blink using `machine.Timer(0)` with minimum-gap guard |
| Config | `config.py` | WiFi credentials, LLM endpoint/model/key, Telegram token, agent name, system prompt, cron settings |
| SSD1306 | `ssd1306.py` | Low-level SSD1306 OLED I2C driver |
| Skills Loader | `skills_loader.py` | Loads pluggable skills from `skills/*.py` (instructions + extra tools) |
| Cron | `pico_cron.py` | Lightweight interval scheduler persisting jobs to `/cron/jobs.txt` |

### High-Level Block Diagram

```
                         +----------------------+
                         |     User (Human)     |
                         +----------+-----------+
                                    |  natural language
            +-----------------------+-----------------------+
            |                       |                       |
            v                       v                       v
   +----------------+      +----------------+      +----------------+
   |  Serial REPL   |      |  Telegram Bot  |      |  (future I/O)  |
   +--------+-------+      +--------+-------+      +--------+-------+
            |                       |                       |
            +-----------+-----------+-----------+-----------+
                        |                       |
                        v                       v
               +-------------------------------------------+
               |               agent.py (Agent)            |
               |  - serial_loop()  - telegram_loop()       |
               |  - run_turn()     - _build_messages()     |
               |  - _call_llm()    - cron tick (main loop) |
               +-----+---------------------------+---------+
                     |                           |
       +-------------+-------------+             |
       |                           |             |
       v                           v             v
 +-----------+             +---------------+   +-----------+
 | tools.py  |             | pico_memory   |   | pico_cron |
 | registry  |             | (TF-IDF)      |   | scheduler |
 +-----+-----+             +-------+-------+   +-----+-----+
       |                           |                 |
       | calls                     | R/W             | R/W
       v                           v                 v
 +-----------+             +---------------+   +-----------+
 | Hardware  |             | /memory/*.txt |   | /cron/    |
 | GPIO/ADC/ |             +---------------+   | jobs.txt  |
 | PWM/I2C/  |                                     +-----------+
 | OLED/Buz  |
 +-----------+
       |
       v
 +-----------+
 |   LLM     |  (OpenAI-compatible endpoint, e.g. DeepSeek)
 |  API      |
 +-----------+
```

### Data Flow

```
User Input (Serial REPL or Telegram)
         |
         v
   +-------------+
   |   boot.py   |  -- starts _thread for Telegram polling
   +-------------+
         |
         v
   +-------------+
   |  agent.py   |  <-- Agent class
   |             |  - serial_loop(): non-blocking character read
   |             |  - telegram_loop(): poll getUpdates, dispatch messages
   |             |  - _build_messages(): system + memory snippets + recent history
   |             |  - run_turn(): LLM call -> tool execution -> final answer
   |             |  - _call_llm(): urequests POST to LLM endpoint
   |             |  - cron tick(): runs due jobs from main loop
   +-------------+
         |
         | calls
         v
   +-------------+
   |  tools.py   |  <-- TOOL_REGISTRY + call_tool()
   |             |  - gpio_write, gpio_read, adc_read, pwm_set, i2c_scan
   |             |  - device_info, display_text, beep_now, exec_code
   |             |  - led_blink_start, start_blink, led_blink_stop, led_toggle
   |             |  - cron_add, cron_list, cron_remove
   +-------------+
         |
         | uses
         v
   +-------------+     +-------------+     +-------------+
   | memory.py   |     | display.py  |     | led_blink.py|
   | (TF-IDF)    |     | (OLED+buz)  |     | (Timer(0))  |
   +-------------+     +-------------+     +-------------+
         |
         | uses
         v
   +-------------+
   | skills_loader.py |  <-- loads skills/*.py (instrs + extra tools)
   +-------------+
```

---

## 3. Boot Sequence (`boot.py`)

The boot script runs on every power-up or soft-reset. It performs the following steps in order:

### 3.1 Onboard LED On

```python
led = Pin("LED", Pin.OUT)
led.on()
```

The onboard LED is turned on immediately to indicate that the Pico 2 W is alive and executing code. On Pico W / Pico 2 W, `Pin("LED")` controls the CYW43 WiFi chip's LED, not GPIO25 directly.

### 3.2 Display + Buzzer Initialization

```python
from display import boot_splash
boot_splash()
```

`boot_splash()` initializes the SSD1306 OLED (I2C0, SDA=GP20, SCL=GP21) and buzzer (GPIO22 PWM). It then animates a 5-frame text splash. Each frame is displayed for 200 ms. A short 500 Hz beep plays at the end. If the OLED fails to init, `beep_error()` is played instead.

### 3.3 WiFi Connection

```python
wlan = connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD)
```

`connect_wifi()` activates `network.WLAN(network.STA_IF)` and attempts to connect for up to 20 seconds. If the Pico is already connected (e.g., after a soft reboot), it returns immediately. On failure, the agent continues in "serial mode only" with no LLM access.

### 3.4 NTP Time Sync

```python
import ntptime
ntptime.settime()
```

Best-effort NTP synchronization. If it fails (no internet, blocked NTP), the agent continues without real-time clock.

### 3.5 Onboard LED Off

```python
led.off()
```

The boot LED is turned off once initialization is complete.

### 3.6 Agent Instantiation

```python
from agent import Agent
agent = Agent()
```

Creates the `Agent` object, which initializes `Memory()` (loads `/memory/transcript.txt` if present), resets conversation history, loads skills from `skills/`, initializes the cron scheduler, and sets Telegram state variables. The Telegram update offset is restored from `/telegram_offset.txt` so stale updates (e.g. `/exit`) are not re-processed after a restart.

### 3.7 Telegram Thread (Background Polling)

```python
import _thread
def _tg_worker():
    while True:
        try:
            had_work = agent.telegram_loop()
            if had_work:
                print("> ", end="")
        except Exception as e:
            print("[telegram] thread error:", e)
        time.sleep(1)
_thread.start_new_thread(_tg_worker, ())
```

Telegram polling runs in a dedicated `_thread` so that its HTTP blocking never delays the main serial REPL. `telegram_loop()` polls `getUpdates` with a 2-second HTTP timeout and 5-second Telegram long-poll timeout. After processing any messages, it returns `True`, and `_tg_worker` prints `> ` to restore the serial REPL prompt.

**Fallback path:** If `_thread` is unavailable, a `machine.Timer(-1)` fires every 3 seconds to set `agent._telegram_due = True`. The main `serial_loop()` checks this flag and calls `telegram_loop()`.

### 3.8 Main Serial Loop

```python
agent.serial_loop()
```

This is the final blocking call. It handles serial REPL input, cron ticks, and (in the fallback path) Telegram polling in a single loop.

---

## 4. Agent Core (`agent.py`)

The `Agent` class is the central orchestrator.

### 4.1 State Variables

| Variable | Purpose |
|----------|---------|
| `self.memory` | `Memory` instance for long-term storage |
| `self.history` | In-memory list of recent conversation turns |
| `self.running` | Shutdown flag (set by `/exit`) |
| `self._telegram_offset` | Last processed `update_id` for Telegram polling (persisted to `/telegram_offset.txt`) |
| `self._telegram_due` | Flag set by timer fallback when Telegram should be polled |
| `self._prompt_printed` | Shared flag between `serial_loop()` and `telegram_loop()` for prompt restoration |
| `self._skill_instrs` | Instruction strings contributed by loaded skills |
| `self._skill_namespaces` | Dict of skill name -> namespace (for `read_skill`) |
| `self.cron` | `CronStore` instance (or `None` if init failed) |
| `self._cron_last_tick` | Timestamp of last cron tick |
| `self._telegram_running` / `self._telegram_alive` | Shutdown coordination for the Telegram worker |
| `self._tg_timer` | Timer handle for the fallback polling path |

### 4.2 Serial REPL (`serial_loop()`)

The serial REPL is implemented as a non-blocking character reader:

```python
sys.stdin.settimeout(0.02)  # 20 ms timeout
```

Each loop iteration:

1. Reads one character with a 20 ms timeout.
2. If a character is received:
   - `\r` / `\n`: submit the accumulated line.
   - `\x08` / `\x7f`: backspace.
   - `\x03`: Ctrl+C shutdown.
   - Other: append to line buffer.
3. If no character is received within 20 ms:
   - If a partial line has been idle for >300 ms, auto-submit it (workaround for builds that don't reliably deliver newline characters).
   - Sleep 5 ms and continue.
4. On each iteration, run a cron tick if `CRON_ENABLED` and `CRON_TICK_MS` has elapsed.

This design keeps the loop responsive enough for `machine.Timer(0)` callbacks to fire on schedule, preserving LED blink accuracy.

### 4.3 Telegram Polling (`telegram_loop()`)

```python
url = "https://api.telegram.org/bot%s/getUpdates?offset=%s&timeout=5"
resp = urequests.get(url, timeout=2)
data = resp.json()
```

`telegram_loop()` fetches updates from the Telegram Bot API. For each update:

- Extract `message` or `channel_post`.
- Check `chat_id` against `TELEGRAM_ALLOWED_USERS` (if configured).
- Handle direct commands: `/info`, `/tools`, `/memory`, `/clear`, `/cron` without an LLM call.
- For all other text: call `self.run_turn(text, source="telegram")`.
- Send the reply via `telegram_send(chat_id, reply)`.
- Persist the new offset to `/telegram_offset.txt`.

It returns `True` if any message was processed, allowing `boot.py`'s `_tg_worker` to print the serial prompt.

### 4.4 Direct Telegram Commands

To avoid LLM latency and API cost for simple queries, `/info`, `/tools`, `/memory`, `/clear`, `/cron`, and `/wifi` are handled directly in `telegram_loop()`:

- `/info`: calls `tools.device_info()` and sends the result.
- `/tools`: lists all tool names and descriptions from `get_tool_defs()`.
- `/memory`: searches memory and returns snippets.
- `/clear`: clears in-memory history and on-device memory.
- `/cron`: lists cron jobs via `cron_list()`.
- `/wifi`: reports connection state and triggers a non-blocking reconnect via `ensure_wifi()`; replies with `connected` or `disconnected/reconnecting`.

---

## 5. LLM Integration

### 5.1 API Client (`_call_llm()`)

```python
url = config.LLM_BASE_URL.rstrip("/") + "/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + config.LLM_API_KEY,
}
payload = {
    "model": config.LLM_MODEL,
    "messages": messages,
    "max_tokens": config.MAX_RESPONSE_TOKENS,
    "temperature": 0.7,
}
if tools:
    payload["tools"] = tools
    payload["tool_choice"] = "auto"
resp = urequests.post(url, headers=headers, json=payload, timeout=30)
```

The client is a thin wrapper around `urequests.post()`. It supports any OpenAI-compatible endpoint. DeepSeek is the default:

- Base URL: `https://api.deepseek.com/v1`
- Model: `deepseek-flash`
- Max response tokens: 512

If the LLM returns an error or the API key is missing, a fallback message is returned. The provider name is inferred from the base URL (`_provider_name()`), supporting DeepSeek, OpenAI, Gemini, Groq, OpenRouter, Together, and Ollama.

### 5.2 Message Construction (`_build_messages()`)

Each agent turn sends a list of messages to the LLM:

1. **System prompt** (`config.SYSTEM_PROMPT`) + available tool names + skill instruction block.
2. **Memory snippets**: retrieved via `self.memory.search()`, limited to `MEMORY_MAX_SNIPPETS=5` and `MEMORY_MAX_CHARS=1500`.
3. **Recent history**: last 10 conversation turns.
4. **Current user message**: with memory block appended.

Example system message:

```
You are Pico2WClaw, a helpful embedded AI agent running on a Raspberry Pi Pico 2 W. You can read/write GPIO pins, read sensors, execute MicroPython code, and remember things. Be concise. Use tools when needed.

Available tools: gpio_write, gpio_read, adc_read, pwm_set, i2c_scan, device_info, display_text, beep_now, exec_code, led_blink_start, start_blink, led_blink_stop, led_toggle, cron_add, cron_list, cron_remove, ...
[Loaded skills]
...
Use tools when the user asks to interact with hardware, sensors, or code.
```

### 5.3 Tool Calling Loop (`run_turn()`)

`run_turn()` implements a bounded tool-calling loop (max 4 rounds):

```python
rounds = 0
while rounds < config.TOOL_CALL_MAX_ROUNDS:
    rounds += 1
    data = self._call_llm(messages, tools=tools)
    ...
    msg = data["choices"][0]["message"]
    tool_calls = msg.get("tool_calls") or []

    if not tool_calls:
        final_answer = msg.get("content") or "(no content)"
        break

    for tc in tool_calls:
        name = tc["function"]["name"]
        args = json.loads(tc["function"]["arguments"])
        result = call_tool(name, args)
        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": result,
        })
```

Each round:

1. Send messages + tool schemas to LLM.
2. If the LLM returns a final text answer (no `tool_calls`), return it. If the first round returns empty content, retry once with a nudge.
3. If the LLM returns `tool_calls`, execute each one via `call_tool()` and append the result to the message history.
4. Loop again so the LLM can synthesize a final answer from tool results.

This is the standard OpenAI "function calling" pattern. The LLM decides which tools to call, in what order, and how to combine their outputs.

After the loop, the user message and final answer are added to memory and history, memory is saved to disk, and status is set to "ready".

### 5.4 Memory-Augmented Context

Before sending the user message to the LLM, `_build_messages()` searches on-device memory for relevant past conversations. These snippets are appended to the user message:

```python
snippets = self.memory.search(user_message, max_results=5, max_chars=1500)
memory_block = "\n\n[Relevant memory]\n" + "\n".join(snippets)
messages.append({"role": "user", "content": user_message + memory_block})
```

This allows the agent to recall previous instructions, sensor readings, or user preferences without sending the entire transcript on every request.

---

## 6. Tool System (`tools.py`)

### 6.1 Tool Registry

`TOOL_REGISTRY` is a dictionary mapping tool names to metadata:

```python
TOOL_REGISTRY = {
    "gpio_write": {
        "name": "gpio_write",
        "description": "Set a GPIO pin HIGH or LOW...",
        "parameters": {...},
        "callable": gpio_write,
    },
    ...
}
```

### 6.2 Schema Generation (`get_tool_defs()`)

```python
def get_tool_defs():
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for name, t in TOOL_REGISTRY.items()
    ]
```

This converts the registry into the OpenAI-compatible JSON schema format. The LLM uses these schemas to understand what tools are available and what arguments they accept.

### 6.3 Tool Execution (`call_tool()`)

```python
def call_tool(name, arguments):
    if name not in TOOL_REGISTRY:
        return f"Error: unknown tool '{name}'"
    fn = TOOL_REGISTRY[name]["callable"]
    if fn is None:
        # Lazy import for tools in separate modules (led_blink, cron)
        ...
    return str(fn(**arguments))
```

Most tools are simple Python callables. The LED blink tools and cron tools use lazy imports because they depend on `machine.Timer` and the cron store, which must be initialized carefully.

### 6.4 Hardware Tools

#### GPIO

```python
def gpio_write(pin, value):
    _get_pin(pin, machine.Pin.OUT).value(int(value))
    return f"GPIO{pin} set to {'HIGH' if value else 'LOW'}"

def gpio_read(pin):
    val = _get_pin(pin, machine.Pin.IN).value()
    return f"GPIO{pin} = {'HIGH' if val else 'LOW'} ({val})"
```

Pin objects are cached in `_pin_cache` to avoid reinitializing the same pin with conflicting modes.

#### ADC

```python
def adc_read(pin):
    adc = machine.ADC(machine.Pin(int(pin)))
    raw = adc.read_u16()
    val12 = raw >> 4  # 16-bit to 12-bit
    voltage = (val12 / 4095) * 3.3
    return f"ADC{pin}: raw={val12}, voltage={voltage:.2f}V"
```

RP2350's ADC is 16-bit, so the result is shifted right by 4 bits to produce a 12-bit value.

#### PWM

```python
def pwm_set(pin, freq, duty):
    p = _get_pin(pin)
    pwm = machine.PWM(p)
    pwm.freq(int(freq))
    pwm.duty_u16(int(duty))
    return f"PWM set on GPIO{pin}: {int(freq)}Hz, duty={int(duty)}/65535"
```

Duty cycle is 16-bit (0–65535).

#### I2C Scan

```python
def i2c_scan(bus=0):
    i2c = machine.I2C(bus, sda=machine.Pin(0), scl=machine.Pin(1))
    devices = i2c.scan()
    return f"I2C bus {bus} devices: {', '.join(hex(d) for d in devices)}"
```

#### Display

```python
def display_text(line1="", line2="", line3="", line4=""):
    from display import show_text
    show_text(str(line1), str(line2), str(line3), str(line4))
    return "Display updated"
```

Writes up to 4 lines to the SSD1306 OLED.

#### Buzzer

```python
def beep_now(freq=1000, duration=0.1):
    from display import beep
    beep(int(freq), float(duration))
    return f"Beep: {freq}Hz for {duration}s"
```

`buzzer_play_tune(melody, beat_seconds, duty)` plays a melody given as a list of `[note, beats]` pairs, where `note` is a note name (C, D, E, F, G, A, B, C#, ...), an octave-qualified name (G4, A4, C5), a frequency in Hz, or `R` for rest. It runs in a background thread so the main loop is not blocked.

#### Device Info

`device_info()` reports board, CPU frequency, RAM (free/used/total), flash (free/used/total), chip temperature, WiFi RSSI, and MicroPython version.

### 6.5 Code Execution (`exec_code()`)

`exec_code()` is the most powerful and dangerous tool. It allows the LLM to write and execute arbitrary MicroPython code on the device:

```python
def exec_code(code):
    capture = []
    def _print(*args, **kwargs):
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        capture.append(sep.join(str(a) for a in args) + end)

    env = dict(_builtins_safe)
    env["print"] = _print
    env["__name__"] = "__main__"
    env["machine"] = machine
    env["time"] = time
    env["sys"] = sys
    env["Pin"] = machine.Pin
    env["PWM"] = machine.PWM
    env["ADC"] = machine.ADC
    env["I2C"] = machine.I2C
    env["Timer"] = machine.Timer
    env["UART"] = machine.UART
    env["SPI"] = machine.SPI

    try:
        exec(code, env)
        out = "".join(capture)
        return out if out else "(code executed, no output)"
    except Exception as e:
        return f"Error: {e}"
```

**Security note:** The sandbox is minimal. Only `_builtins_safe` (a curated subset of builtins) is exposed. `__import__` is not provided, so the executed code cannot import arbitrary modules—only the pre-injected ones (`machine`, `time`, `sys`, etc.).

**Persistence caveat:** Code executed via `exec_code()` runs in the current call frame. Timers, threads, and object state created inside `exec_code()` are garbage-collected when the function returns unless they are anchored to module-level objects. For persistent behaviors (like blinking), the agent should use the dedicated `led_blink_start` / `start_blink` tools, which use module-scoped `_Blinker` instances.

---

## 7. LED Blink System (`led_blink.py`)

The `_Blinker` class manages persistent LED blinking using a hardware timer:

```python
class _Blinker:
    def __init__(self):
        self.t = None
        self.running = False
        self.last_toggle_ms = 0
        self.led = None
        self.period_ms = 0

    def _toggle(self, _):
        if not self.running or self.led is None:
            return
        now = time.ticks_ms()
        min_gap = max(1, self.period_ms // 4)
        if time.ticks_diff(now, self.last_toggle_ms) < min_gap:
            return
        self.last_toggle_ms = now
        self.led.value(1 if self.led.value() == 0 else 0)
```

Key design points:

- **Hardware timer:** `machine.Timer(0)` is used first (high-priority, hardware-backed). If unavailable, `machine.Timer(-1)` (virtual timer) is the fallback.
- **Module-scoped instance:** `_blinker = _Blinker()` is defined at module level. This ensures the timer callback survives across `exec_code()` calls, which have their own local scope.
- **Minimum-gap guard:** `time.ticks_diff(now, self.last_toggle_ms) < min_gap` suppresses spurious toggles caused by timer drift or delayed callbacks. `min_gap` is 25% of the period.
- **Period semantics:** `period_ms` is the time the LED stays in each state (ON then OFF). `start_period(2000)` means 2 seconds ON, 2 seconds OFF.
- **Frequency variant:** `start(freq_hz)` converts frequency to period: `period_ms = int(1000 / hz)`.

### Blink Tool Schemas

Two tools expose this to the LLM:

1. `start_blink(period_ms)`: Use when the user says "every N seconds" or "blink with period".
2. `led_blink_start(freq_hz)`: Use when the user says "blink at X Hz".

Both call `_blinker.start(period_ms)` under the hood. `led_blink_stop()` stops the blink and turns the LED off. `led_toggle()` toggles the LED once.

---

## 8. Memory System (`pico_memory.py`)

Pico2WClaw uses a lightweight keyword/TF-IDF memory stored on the filesystem. No vector embeddings are used (too heavy for 520 KB SRAM).

### 8.1 Storage Format

Memory is persisted to `/memory/transcript.txt`. Each line is:

```
role|text
```

Example:

```
user|turn on the red LED
assistant|LED turned on
user|what is the temperature
assistant|27.3C
```

The directory `/memory` is created on first run if it does not exist. (Note: this differs from an earlier `/sd/memory` convention; the code uses `/memory`.)

### 8.2 Tokenization

```python
def _tokenize(self, text):
    text = text.lower()
    words = []
    current = []
    for ch in text:
        if ("a" <= ch <= "z") or ("0" <= ch <= "9") or ch == "_":
            current.append(ch)
        else:
            if current:
                word = "".join(current)
                if len(word) > 2:
                    words.append(word)
                current = []
    ...
    stop = {"the", "is", "at", "of", "on", "and", ...}
    return [w for w in words if w not in stop]
```

Tokens are lowercase alphanumeric sequences longer than 2 characters, with a 33-word stoplist.

### 8.3 TF-IDF Scoring

```python
def search(self, query, max_results=5, max_chars=1500):
    query_tokens = self._tokenize(query)
    scores = []
    N = len(self.documents)
    for i, doc in enumerate(self.documents):
        doc_tokens = self._tokenize(doc["text"])
        doc_counts = _counter(doc_tokens)
        score = 0.0
        for qt in query_tokens:
            if qt in doc_counts:
                tf = doc_counts[qt]
                df = self.vocab.get(qt, 1)
                idf = (N / (1 + df))
                score += tf * idf
        if score > 0:
            scores.append((score, i))
    scores.sort(reverse=True)
    ...
```

For each query term, the score is `tf * idf`, where `idf = N / (1 + df)`. Documents with higher term frequency and lower document frequency rank higher. Results are truncated to `max_chars`.

### 8.4 Usage in Agent

Every `run_turn()` call:

1. Adds the user message to memory (`memory.add("user", ...)`).
2. Searches memory for relevant snippets.
3. Appends snippets to the LLM context.
4. After the turn, adds the assistant's final answer to memory and persists to disk (`memory.save()`).

---

## 9. Display & Peripherals (`display.py`)

### 9.1 SSD1306 OLED

- Controller: SSD1306 via I2C0
- SDA: GP20, SCL: GP21, frequency 400 kHz
- Resolution: 128×64
- Font: default 8×8 (up to ~21 chars per line)

The OLED shows:

- Boot splash (5 frames during initialization)
- Status updates: "Ready", "Thinking", "Tool", "Error", "WiFi", "LLM"
- User text via `display_text(line1, line2, line3, line4)`

### 9.2 Buzzer

- Pin: GPIO22 (PWM)
- Tones:
  - `beep_success()`: 440→660→880 Hz ascending (3×80 ms)
  - `beep_error()`: 880→660→440 Hz descending (3×100 ms)
  - `beep_click()`: 2000 Hz for 30 ms (UI feedback)

### 9.3 Display Reliability & Timeout Handling

The OLED I2C link can occasionally stall (e.g., loose wiring, power glitch, or a stuck bus). To prevent a single failed `show()` from crashing the whole agent, every display operation is wrapped in `try/except` and, on failure, calls `_disable_display()`:

```python
def show_text(line1="", line2="", line3="", line4=""):
    if _oled is None:
        return
    try:
        _oled.fill(0)
        ...
        _oled.show()
    except Exception as e:
        print("[display] show_text failed:", e)
        _disable_display()   # set _oled = None; no further I2C attempts
```

`_disable_display()` sets the module-global `_oled = None`, so subsequent calls become no-ops instead of repeatedly hammering a dead bus. The same pattern is applied in `clear()`. This is the "display timeout bug fix": instead of blocking on a hung I2C transaction or raising an unhandled exception that kills the main loop, the display is gracefully disabled and the agent continues running (serial REPL, Telegram, cron, LED blink all keep working). The display can be re-enabled by rebooting.

Additional notes:
- `beep()` uses `utime.sleep(duration)`, which blocks the calling thread for the beep duration. Keep beep durations short (≤0.1 s) in the main loop to avoid delaying timer callbacks.
- `beep_success()`/`beep_error()` chain 3 beeps; these are acceptable because they run during status transitions, not in tight loops.

---

## 10. WiFi Recovery (Non-Blocking Reconnect)

Pico2WClaw includes a non-blocking WiFi recovery mechanism so that a dropped or flaky connection does not freeze the serial REPL, timer callbacks, or LED blink. The state machine lives in `Agent.ensure_wifi()` and is invoked from the top of every `serial_loop()` iteration.

### 10.1 State Machine

States: `unknown` → `connected` → (on drop) `idle` → `connecting` → (success) `connected` / (timeout) `cooldown` → `idle` → ...

```python
def ensure_wifi(self):
    if not getattr(config, "WIFI_RECONNECT_ENABLED", True):
        return self.wifi_connected()
    wlan = self._wlan()
    if wlan is None:
        return False
    now = time.ticks_ms()
    try:
        if wlan.isconnected():
            if self._wifi_state != "connected":
                print("[wifi] reconnected:", wlan.ifconfig())
                set_status("wifi_ok", beep_type="success")
            self._wifi_state = "connected"
            self._wifi_down_since_ms = 0
            return True
    except Exception:
        pass

    # Track how long WiFi has been down
    if self._wifi_down_since_ms == 0:
        self._wifi_down_since_ms = now

    # Cooldown between attempts
    if self._wifi_state == "cooldown":
        if time.ticks_diff(now, self._wifi_cooldown_until_ms) < 0:
            return False
        self._wifi_state = "idle"

    # If already connecting, poll status without re-calling connect()
    if self._wifi_state == "connecting":
        if time.ticks_diff(now, self._wifi_connect_started_ms) > 8000:
            print("[wifi] connect attempt timed out")
            self._wifi_state = "cooldown"
            self._wifi_cooldown_until_ms = now + getattr(config, "WIFI_RECONNECT_COOLDOWN_MS", 10000)
        return False

    # Start a new connection attempt
    try:
        wlan.active(True)
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        self._wifi_state = "connecting"
        self._wifi_connect_started_ms = now
        print("[wifi] reconnecting...")
        set_status("wifi_fail", beep_type="error")
    except Exception as e:
        print("[wifi] reconnect error:", e)
        self._wifi_state = "cooldown"
        self._wifi_cooldown_until_ms = now + getattr(config, "WIFI_RECONNECT_COOLDOWN_MS", 10000)
    return False
```

Key properties:

- **Non-blocking:** `wlan.connect()` is called once; subsequent iterations only poll `isconnected()`. No `time.sleep()` loops.
- **Cooldown:** Failed attempts wait `WIFI_RECONNECT_COOLDOWN_MS` (default 10 s) before retrying, preventing tight retry storms.
- **Attempt timeout:** A single attempt gives up after 8 s and enters cooldown.
- **Soft reset (optional):** `wifi_maybe_soft_reset()` triggers `machine.soft_reset()` if WiFi has been down longer than `WIFI_AUTO_SOFT_RESET_MS` (default 0 = disabled). This is a last-resort recovery for stuck CYW43 states.
- **Status feedback:** On reconnect, the OLED shows "WiFi / connected" with a success beep; on failure, "WiFi / FAILED" with an error beep.

### 10.2 Configuration

```python
# config.py
WIFI_RECONNECT_ENABLED = True
WIFI_RECONNECT_COOLDOWN_MS = 10000   # ms between reconnect attempts
WIFI_AUTO_SOFT_RESET_MS = 0          # 0 disables; set e.g. 300000 for 5-min auto-reset
```

### 10.3 Serial / Telegram Command

- Serial REPL: `/wifi` prints `[wifi] connected` or `[wifi] disconnected/reconnecting`.
- Telegram: `/wifi` replies with the same status string.

---

## 11. Cron Scheduler (`pico_cron.py`)

A lightweight interval scheduler for recurring GPIO/ADC monitoring that sends status to Telegram.

### 10.1 Storage

Jobs persist in `/cron/jobs.txt` using a pipe-delimited line format (no JSON, to stay MicroPython-safe):

```
id|type|pin|interval_ms|chat_id|enabled|template
```

Example:

```
1|adc|26|5000|8684515324|1|ADC26: {value}
2|gpio|15|10000||1|GPIO15 = {value}
```

### 10.2 Design Constraints

- Runs only from the main loop (never from an ISR or background thread) so `urequests`/pin access stay safe.
- One job per tick to bound latency.
- On first tick, a job's `last_run` is baselined; the first real fire happens after one full interval.

### 10.3 API

- `cron_add(type, pin, interval_ms, chat_id, message)` — schedule a job. `type` is `gpio` or `adc`. `message` is a template using `{value}`, `{pin}`, `{type}`.
- `cron_list()` — list jobs.
- `cron_remove(id)` — remove a job.
- `CronStore.tick(now_ms)` — called from the main loop; fires due jobs.

The `chat_id` defaults to `CRON_DEFAULT_CHAT_ID` (or the first `TELEGRAM_ALLOWED_USERS` entry) when not provided.

---

## 12. Skills Loader (`skills_loader.py`)

Loads pluggable skills from the `skills/` directory. Each skill is a `.py` file with an optional `SKILL_INSTR` string (injected into the LLM system prompt) and an optional `TOOLS` dict (merged into `TOOL_REGISTRY`).

```python
# skills/example.py
SKILL_INSTR = "You can read the DHT22 sensor on pin 15."
TOOLS = {
    "dht_read": {
        "name": "dht_read",
        "description": "Read temperature and humidity from DHT22.",
        "parameters": {"type": "object", "properties": {"pin": {"type": "integer"}}, "required": ["pin"]},
        "callable": dht_read,
    }
}
```

`load_skills()` scans `skills/*.py`, `exec()`s each file in a fresh namespace, collects instructions and tools, and returns `(extra_tools, instruction_lines)`. Tools are merged via `merge_skill_tools()`. Skill namespaces are retained for `read_skill(name)`.

---

## 13. End-to-End Examples

### Example 1: Telegram `/info` Command

**User sends:** `/info` via Telegram

**Flow:**

1. `_tg_worker` calls `telegram_loop()`.
2. `telegram_loop()` receives the update, extracts `text="/info"`.
3. Direct command handler:
   ```python
   if text == "/info":
       from tools import device_info
       reply = device_info()
   ```
4. `device_info()` reads CPU frequency, temperature, WiFi RSSI, and `sys.version`.
5. `telegram_send(chat_id, reply)` sends the formatted string to Telegram.
6. `telegram_loop()` returns `True`.
7. `_tg_worker` prints `> ` to restore the serial REPL prompt.

**No LLM call is made.** This is instant and avoids API costs.

### Example 2: Telegram "Blink the LED every 2 seconds"

**User sends:** `Blink the LED every 2 seconds` via Telegram

**Flow:**

1. `_tg_worker` calls `telegram_loop()`.
2. Message text is not a direct command, so `run_turn(text, source="telegram")` is called.
3. `_build_messages()` constructs the LLM context (system prompt + tool names + memory snippets + recent history + user message).
4. `_call_llm()` POSTs to `https://api.deepseek.com/v1/chat/completions` with `tools=[get_tool_defs()]`.
5. DeepSeek responds with a tool call:
   ```json
   {
     "tool_calls": [{
       "id": "call_abc123",
       "function": {
         "name": "start_blink",
         "arguments": "{\"period_ms\": 2000}"
       }
     }]
   }
   ```
6. `call_tool("start_blink", {"period_ms": 2000})` is invoked.
7. `start_period(2000)` calls `_blinker.start(2000)`.
8. `_blinker.start()` initializes `machine.Pin("LED")` and starts `machine.Timer(0)` with a 2000 ms period.
9. Result string: `"Blinking with period 2000 ms (2 s ON, 2 s OFF)"` is sent back to the LLM as a `tool` message.
10. LLM synthesizes final answer: "The onboard LED is now blinking every 2 seconds (2s ON, 2s OFF)."
11. `telegram_send(chat_id, reply)` sends the answer.
12. `_tg_worker` prints `> `.

### Example 3: Serial REPL "Read pin 26 and show it on display"

**User types:** `read pin 26 and show it on display` and presses Enter in serial REPL.

**Flow:**

1. `serial_loop()` accumulates characters, submits on newline.
2. `_process_serial_input()` calls `run_turn(user_input, source="serial")`.
3. LLM is called with the same message construction as Example 2.
4. DeepSeek responds with **two tool calls** in a single round:
   ```json
   {
     "tool_calls": [
       {"id": "call_1", "function": {"name": "adc_read", "arguments": "{\"pin\": 26}"}},
       {"id": "call_2", "function": {"name": "display_text", "arguments": "{\"line1\": \"ADC26\", \"line2\": \"1.23V\"}"}}
     ]
   }
   ```
5. `call_tool("adc_read", {"pin": 26})` executes, returns `"ADC26: raw=2464, voltage=1.98V"`.
6. `call_tool("display_text", ...)` executes, writes to OLED.
7. Both results are appended to `messages` as `tool` role entries.
8. LLM sees the ADC result and generates a final text answer: "GPIO26 reads 1.98V. Display updated."
9. `run_turn()` returns the final answer.
10. `_process_serial_input()` prints: `Pico2WClaw: GPIO26 reads 1.98V. Display updated.`
11. `serial_loop()` prints `> `.

### Example 4: Serial REPL "Execute code to blink pin 15"

**User types:** `execute code: for i in range(5): Pin(15,OUT).toggle(); time.sleep_ms(200)` and presses Enter.

**Flow:**

1. LLM receives the request and responds with a tool call to `exec_code`.
2. `call_tool("exec_code", {...})` executes the code in a restricted environment with `print` captured.
3. The code runs, toggling GPIO15 five times with 200 ms delays.
4. Output is captured: `"(code executed, no output)"` (because no print statements).
5. LLM responds: "GPIO15 toggled 5 times."
6. `run_turn()` returns the answer.

**Important:** The LLM is instructed not to create persistent timers or threads inside `exec_code()`, because those objects die when `exec_code()` returns. For persistent blinking, the agent must use `led_blink_start` or `start_blink`.

### Example 5: Memory Recall Across Sessions

**Session 1:**

- User: "My favorite sensor is the DS18B20 on pin 28."
- LLM calls `memory.add("user", "My favorite sensor is the DS18B20 on pin 28")`.
- Memory is saved to `/memory/transcript.txt`.

**Session 2 (later):**

- User: "Which sensor do I like?"
- LLM calls `memory.search("which sensor do i like")`.
- TF-IDF scoring finds "DS18B20" with high relevance.
- Snippet is injected into the user message as `[Relevant memory]`.
- LLM responds: "You mentioned your favorite sensor is the DS18B20 on pin 28."

### Example 6: Cron Monitor

**User sends (serial):** `monitor ADC pin 26 every 5 seconds`

**Flow:**

1. LLM responds with `cron_add(type="adc", pin=26, interval_ms=5000)`.
2. `cron_add` calls `_store.add_job(...)`, persists to `/cron/jobs.txt`, returns `"Added cron job #1"`.
3. Every 5 seconds, the main loop's cron tick fires job #1, reads ADC26, and sends the formatted message to the configured Telegram chat.

### Example 7: WiFi Drop & Recovery

**Scenario:** WiFi AP reboots mid-session.

1. `serial_loop()` calls `agent.ensure_wifi()` at the top of each iteration.
2. `wlan.isconnected()` returns `False`; state moves `connected` → `idle`, `_wifi_down_since_ms` is recorded.
3. On the next iteration, state is `idle` → a new attempt starts: `wlan.connect(SSID, PASSWORD)`, state becomes `connecting`, OLED shows "WiFi / FAILED".
4. For the next 8 s, iterations poll `isconnected()` only (no re-connect).
5. If the AP comes back, `isconnected()` becomes `True` → state returns to `connected`, OLED shows "WiFi / connected" with success beep.
6. If it stays down past 8 s, state moves to `cooldown` for `WIFI_RECONNECT_COOLDOWN_MS` (10 s) before another attempt.
7. If `WIFI_AUTO_SOFT_RESET_MS` is set and WiFi has been down that long, `wifi_maybe_soft_reset()` triggers `machine.soft_reset()`.

---

## 14. Constraints & Design Decisions

### 14.1 Memory Constraints

- **520 KB SRAM:** LLM context is limited to 4000 tokens (`MAX_CONTEXT_TOKENS`). Response is capped at 512 tokens (`MAX_RESPONSE_TOKENS`). Tool-calling rounds are limited to 4 (`TOOL_CALL_MAX_ROUNDS`).
- **No `collections.Counter`:** Replaced with `_counter()` using plain dicts.
- **No `re.findall()`:** Tokenization uses a manual character loop.
- **No `str.isalnum()`:** Character ranges `("a" <= ch <= "z")` and `("0" <= ch <= "9")` are used instead.
- **Skills and cron** add small but real overhead; keep skill files minimal.

### 14.2 Timing Constraints

- **Serial REPL blocking:** `sys.stdin.settimeout(0)` is unreliable on some MicroPython builds. A 20 ms timeout is used instead.
- **LED blink accuracy:** `machine.Timer(0)` (hardware timer) is preferred over `machine.Timer(-1)` (virtual timer). A minimum-gap guard suppresses timer drift artifacts.
- **WiFi recovery:** `ensure_wifi()` is non-blocking; cooldown prevents retry storms. `wifi_maybe_soft_reset()` is opt-in (default disabled).
- **Display reliability:** I2C failures disable the OLED permanently for the session (`_disable_display()`); the agent keeps running without display.
- **Telegram thread isolation:** Telegram polling runs in `_thread` so its HTTP blocking never delays the serial REPL or timer callbacks.
- **Cron runs only from the main loop** to avoid unsafe concurrent access.

### 13.3 Network Constraints

- **HTTP timeout:** Reduced to 2 seconds for Telegram polling to avoid blocking the background thread for too long.
- **LLM timeout:** 30 seconds for API calls (enough for `deepseek-flash` on a good connection).
- **Error suppression:** Expected network errors (`ETIMEDOUT`, `ECONNRESET`, `EHOSTUNREACH`) are suppressed in `telegram_loop()` to avoid log spam.

### 13.4 Security Constraints

- **`exec_code()` sandbox:** Only `_builtins_safe` is available. No `__import__`, no file I/O (other than memory save/load), no network access from executed code.
- **Telegram access control:** `TELEGRAM_ALLOWED_USERS` can restrict which chat IDs are accepted. Empty list means all users are allowed.
- **Skills are `exec()`ed** in a fresh namespace; a malicious skill file can run arbitrary code. Only load trusted skills.

---

## 15. Troubleshooting

### 14.1 LED Blink Stretched or Glitchy

- **Symptom:** LED period is 3–4x longer than requested, or visible on-off spikes.
- **Cause:** Main loop blocked by `input()` or `urequests.get()`.
- **Fix:** Use `sys.stdin.settimeout(0.02)` for serial input. Telegram polling must run in `_thread` or a `machine.Timer` fallback.

### 14.2 CLI Prompt Missing After Telegram Output

- **Symptom:** After a Telegram message is processed, the serial REPL does not show `> ` until Enter is pressed.
- **Cause:** The background `_thread` Telegram path bypasses the `_telegram_due` flag that `serial_loop()` monitors.
- **Fix:** `boot.py`'s `_tg_worker` prints `> ` directly after `telegram_loop()` returns `True`.

### 14.3 DeepSeek Auth Failures

- **Symptom:** "Authentication Fails" for non-command Telegram messages.
- **Cause:** Invalid, expired, or rate-limited API key. Or the placeholder key is still in `config.py`.
- **Fix:** Verify `config.LLM_API_KEY` is a real DeepSeek key. Check quota at platform.deepseek.com.

### 14.4 `/info` Hang on Serial

- **Symptom:** Typing `/info` in serial REPL causes the prompt to hang.
- **Cause:** `sys.stdin.settimeout(0)` returns `None` for newlines on some MicroPython builds.
- **Fix:** Use `sys.stdin.settimeout(0.02)` with a 300 ms auto-submit fallback for incomplete lines.

### 14.5 Memory Not Persisting

- **Symptom:** Memory is empty after reboot.
- **Cause:** `/memory` directory does not exist or is not writable.
- **Fix:** Ensure flash storage is writable. Check `pico_memory.py`'s `storage_dir` path (default `/memory`).

### 14.6 Cron Job Not Firing

- **Symptom:** Scheduled job never sends a Telegram message.
- **Cause:** `CRON_ENABLED` is False, the main loop is blocked, or `chat_id` is None and no default is configured.
- **Fix:** Verify `config.CRON_ENABLED = True`, keep the serial loop responsive, and set `CRON_DEFAULT_CHAT_ID` or `TELEGRAM_ALLOWED_USERS`.

---

## 16. File Structure

```
pico2wclaw/
├── boot.py           # Boot script: WiFi, NTP, agent, Telegram thread
├── agent.py          # Core agent: LLM client, tool loop, serial + Telegram, cron tick
├── tools.py          # Tool registry, JSON schemas, hardware callables
├── pico_memory.py    # TF-IDF memory, filesystem persistence (/memory)
├── display.py        # OLED + buzzer UI, status, boot splash
├── led_blink.py      # Persistent LED blink via hardware timer
├── config.py         # WiFi, LLM, Telegram, agent, cron settings
├── ssd1306.py        # SSD1306 OLED driver (I2C)
├── skills_loader.py  # Pluggable skills loader
├── pico_cron.py      # Interval scheduler, persists /cron/jobs.txt
├── skills/           # Optional skill modules (*.py)
└── README.md         # Setup instructions
```

Upload all `.py` files to the Pico 2 W using Thonny IDE or `mpremote`. Ensure `ssd1306.py` is present in the same directory. Create `/memory` and `/cron` directories if they do not exist (the code creates them automatically).

---

## 17. Summary

Pico2WClaw is a complete embedded agentic AI system that fits within the Raspberry Pi Pico 2 W's resource constraints. It achieves this through:

- **Modular architecture:** Each concern (boot, agent, tools, memory, display, LED, cron, skills) is isolated in its own module.
- **Non-blocking I/O:** Serial REPL and Telegram polling coexist without blocking each other.
- **Minimal memory footprint:** Keyword-based memory instead of embeddings; tool schemas are compact; context is bounded.
- **Hardware-aware design:** Direct register access via `machine` module; timer-based LED blink; I2C display and buzzer PWM.
- **Extensibility:** Pluggable skills add instructions and tools without modifying core code.
- **Scheduling:** Cron monitors report sensor/GPIO state to Telegram on an interval.
- **Resilient error handling:** Graceful degradation when WiFi, LLM, or peripherals fail.

The result is a device that can understand natural language, remember context, control hardware, execute code, schedule monitors, and load skills—all from a $6 microcontroller.
