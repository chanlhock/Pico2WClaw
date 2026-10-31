# Pico2WClaw Technical Documentation

## 1. Introduction

Pico2WClaw is a minimal agentic AI runtime for the Raspberry Pi Pico 2 W. It runs MicroPython, connects to WiFi, communicates with users via a serial REPL and Telegram bot, calls an OpenAI-compatible LLM API (DeepSeek by default), executes hardware tools (GPIO, sensors, display, buzzer), and persists a simple keyword-based memory on the filesystem.

The system is designed around a tight resource budget: 520 KB SRAM, 4 MB flash, and MicroPython's constrained standard library. Every design decision—from avoiding `collections.Counter` to using `machine.Timer(0)` with a minimum-gap guard—reflects these constraints.

---

## 2. System Architecture

Pico2WClaw consists of the following modules:

| Module | File | Purpose |
|--------|------|---------|
| Boot | `boot.py` | WiFi connection, NTP sync, display splash, start agent + Telegram thread |
| Agent | `agent.py` | Core loop, LLM client, tool orchestration, serial REPL, Telegram polling, skills loading |
| Tools | `tools.py` | Tool registry, JSON schemas for LLM, hardware callables (GPIO, ADC, PWM, I2C, exec, display, buzzer, LED) |
| Memory | `pico_memory.py` | On-device keyword/TF-IDF memory, persisted to `/memory/transcript.txt` |
| Skills | `skills_loader.py` | Loads `skills/*.py` skill files at startup, injects instructions into LLM system prompt |
| Display | `display.py` | SSD1306 OLED driver wrapper, buzzer tones, status UI, boot splash |
| LED Blink | `led_blink.py` | Persistent onboard-LED blink using `machine.Timer(0)` with minimum-gap guard |
| Config | `config.py` | WiFi credentials, LLM endpoint/model/key, Telegram token, agent name, system prompt |

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
   |             |  - _build_messages(): system + memory snippets + [Loaded skills] + recent history
   |             |  - run_turn(): LLM call -> tool execution -> final answer
   |             |  - _call_llm(): urequests POST to DeepSeek/OpenAI endpoint
   +-------------+
         |
         | calls
         v
   +-------------+
   |  tools.py   |  <-- TOOL_REGISTRY + call_tool()
   |             |  - gpio_write, gpio_read, adc_read, pwm_set, i2c_scan
   |             |  - device_info, display_text, beep_now, exec_code
   |             |  - led_blink_start, start_blink, led_blink_stop, led_toggle
   +-------------+
         |
         | uses
         v
         +-------------+
         | pico_memory |  <-- simple TF-IDF, no embeddings
         +-------------+
               |
               | uses
               v
         +-------------+
         | skills_loader|  <-- loads skills/*.py
         +-------------+
               |
               | uses
               v
         +-------------+
         | skills/     |  <-- .py modules with SKILL_INSTR + TOOLS
         +-------------+
               |
               | uses
               v
         +-------------+
         | display.py  |  <-- SSD1306 I2C + buzzer PWM
         +-------------+
         |
         | uses
         v
   +-------------+
   | led_blink.py|  <-- machine.Timer(0) callback, module-scoped _Blinker
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

`boot_splash()` initializes the SSD1306 OLED (I2C0, SDA=GP20, SCL=GP21) and buzzer (GPIO22 PWM). It then animates a 5-frame text splash: "Pico2WClaw", " Booting", "  Booting.", "   Booting..", "    Booting...". Each frame is displayed for 200 ms. A short 500 Hz beep plays at the end.

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

Creates the `Agent` object, which initializes `Memory()` (loads `/memory/transcript.txt` if present), resets conversation history, and sets Telegram state variables.

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

This is the final blocking call. It handles serial REPL input and timer-fallback Telegram polling in a single loop.

---

## 4. Agent Core (`agent.py`)

The `Agent` class is the central orchestrator.

### 4.1 State Variables

| Variable | Purpose |
|----------|---------|
| `self.memory` | `Memory` instance for long-term storage |
| `self.history` | In-memory list of recent conversation turns |
| `self._telegram_offset` | Last processed `update_id` for Telegram polling |
| `self._telegram_due` | Flag set by timer fallback when Telegram should be polled |
| `self._prompt_printed` | Shared flag between `serial_loop()` and `telegram_loop()` for prompt restoration |

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
- Handle direct commands: `/info`, `/tools`, `/memory`, `/clear` without an LLM call.
- For all other text: call `self.run_turn(text, source="telegram")`.
- Send the reply via `telegram_send(chat_id, reply)`.

It returns `True` if any message was processed, allowing `boot.py`'s `_tg_worker` to print the serial prompt.

### 4.4 Direct Telegram Commands

To avoid LLM latency and API cost for simple queries, `/info`, `/tools`, `/memory`, `/clear`, `/skills`, and `/skill_read` are handled directly in `telegram_loop()`:

- `/info`: calls `tools.device_info()` and sends the result.
- `/tools`: lists all tool names and descriptions from `get_tool_defs()`.
- `/memory`: searches memory and returns snippets.
- `/clear`: clears in-memory history and on-device memory.
- `/skills`: lists all loaded skill names from `skills_loader.get_skill_namespaces()`.
- `/skill_read <name>`: returns `SKILL_INSTR` text for a specific skill file.

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

If the LLM returns an error or the API key is missing, a fallback message is returned.

### 5.2 Message Construction (`_build_messages()`)

Each agent turn sends a list of messages to the LLM:

1. **System prompt** (`config.SYSTEM_PROMPT`) + available tool names.
2. **Memory snippets**: retrieved via `self.memory.search()`, limited to `MEMORY_MAX_SNIPPETS=5` and `MEMORY_MAX_CHARS=1500`.
3. **Recent history**: last 10 conversation turns.
4. **Current user message**: with memory block appended.

Example system message:

```
You are Pico2WClaw, a helpful embedded AI agent running on a Raspberry Pi Pico 2 W. You can read/write GPIO pins, read sensors, execute MicroPython code, and remember things. Be concise. Use tools when needed.

Available tools: gpio_write, gpio_read, adc_read, pwm_set, i2c_scan, device_info, display_text, beep_now, exec_code, led_blink_start, start_blink, led_blink_stop, led_toggle
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
2. If the LLM returns a final text answer (no `tool_calls`), return it.
3. If the LLM returns `tool_calls`, execute each one via `call_tool()` and append the result to the message history.
4. Loop again so the LLM can synthesize a final answer from tool results.

This is the standard OpenAI "function calling" pattern. The LLM decides which tools to call, in what order, and how to combine their outputs.

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
        # Lazy import for tools in separate modules (led_blink)
        ...
    return str(fn(**arguments))
```

Most tools are simple Python callables. The LED blink tools use lazy imports because they depend on `machine.Timer`, which must be initialized carefully to avoid conflicts.

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
    i2c = machine.I2C(bus)
    devices = i2c.scan()
    return f"I2C{bus} devices: {[hex(d) for d in devices]}"
```

#### Display

```python
def display_text(line1="", line2="", line3="", line4=""):
    from display import show_text
    show_text(str(line1), str(line2), str(line3), str(line4))
    return "Display updated"
```

Writes up to 4 lines (21 characters each) to the SSD1306 OLED.

#### Buzzer

```python
def beep_now(freq=1000, duration=0.1):
    from display import beep
    beep(int(freq), float(duration))
    return f"Beep: {freq}Hz for {duration}s"
```

Uses the same PWM channel as the buzzer peripheral.

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

Both call `_blinker.start(period_ms)` under the hood.

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

For each query term, the score is `tf * idf`, where `idf = N / (1 + df)`. Documents with higher term frequency and lower document frequency rank higher.

### 8.4 Usage in Agent

Every `run_turn()` call:

1. Adds the user message to memory.
2. Searches memory for relevant snippets.
3. Appends snippets to the LLM context.
4. After the turn, adds the assistant's final answer to memory and persists to disk.

---

## 9. Skills System (`skills_loader.py`)

Pico2WClaw supports extensible **MicroPython skills** placed in a `skills/` directory. Each skill is a plain `.py` module with no YAML or heavy stdlib dependencies.

### 9.1 Skill File Contract

Each skill module exposes two optional globals:

```python
SKILL_INSTR = "1-3 sentences describing when and how to use this skill."
TOOLS = {
    "tool_name": {
        "description": "What it does.",
        "parameters": {
            "type": "object",
            "properties": {...},
            "required": [...],
        },
        "callable": some_function,
    }
}
```

### 9.2 Loading Flow

1. `Agent.__init__()` calls `skills_loader.load_skills()`.
2. `load_skills()` scans `skills/*.py` files, uses `exec()` to extract `SKILL_INSTR` and `TOOLS`.
3. All `SKILL_INSTR` texts are concatenated and injected into the LLM system prompt under `[Loaded skills]`.
4. All `TOOLS` callables are merged into `TOOL_REGISTRY` via `merge_skill_tools()`.
5. `/skills` and `/skill_read <name>` commands are added to serial CLI and Telegram handling.

### 9.3 Path Resolution

`skills_loader._skill_dir()` resolves the skills directory:

```python
def _skill_dir():
    try:
        import os.path
        return os.path.dirname(os.path.abspath(__file__)) + "/skills"
    except AttributeError:
        return "skills"
```

Stock MicroPython builds may lack `os.path`. The fallback returns `"skills"`, a CWD-relative path.

### 9.4 Isolation & Constraints

Skills execute in an isolated `exec()` namespace:
- **No inherited globals:** `time`, `machine`, `random`, `os` are not shared from the agent. Import them inside the skill file.
- **No side effects at import:** Skills are loaded at agent startup. Avoid network calls, infinite loops, or blocking operations at module top level.
- **No heavy stdlib:** Avoid `collections.Counter`, `re.findall`, `str.isalnum`, or `os.path`.
- **No built-in shadowing:** Do not name skill files `memory.py`, `time.py`, `re.py`, etc. Use project-prefixed names.

### 9.5 Built-in Skills

`skills/led_patterns.py` is included and provides:
- `led_pattern(pattern)` — run an LED blink pattern on the onboard LED (`Pin("LED")`).
- Patterns: `sos` (Morse code), `heartbeat` (double pulse), `candle` (flicker simulation).

Each pattern function imports `time` internally and calls `led_blink.start_period(period_ms=...)` to drive the hardware timer.

---

## 10. Display & Peripherals (`display.py`)

### 10.1 SSD1306 OLED

- Controller: SSD1306 via I2C0
- SDA: GP20, SCL: GP21
- Resolution: 128×64
- Font: default 8×8

The OLED shows:
- Boot splash (5 frames during initialization)
- Status updates: "Ready", "Thinking", "Tool", "Error", "WiFi", "LLM"
- User text via `display_text(line1, line2, line3, line4)`

### 10.2 Buzzer

- Pin: GPIO22 (PWM)
- Tones:
  - `beep_success()`: 440→660→880 Hz ascending (3×80 ms)
  - `beep_error()`: 880→660→440 Hz descending (3×100 ms)
  - `beep_click()`: 2000 Hz for 30 ms (UI feedback)

---

## 11. End-to-End Examples

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
3. `_build_messages()` constructs the LLM context:
   - System prompt + tool names
   - Memory snippets (if any relevant past conversations)
   - Recent history (last 10 turns)
   - User message: `Blink the LED every 2 seconds`
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
6. `call_tool("display_text", {"line1": "ADC26", "line2": "1.98V"})` executes, writes to OLED.
7. Both results are appended to `messages` as `tool` role entries.
8. LLM sees the ADC result and generates a final text answer: "GPIO26 reads 1.98V. Display updated."
9. `run_turn()` returns the final answer.
10. `_process_serial_input()` prints: `Pico2WClaw: GPIO26 reads 1.98V. Display updated.`
11. `serial_loop()` prints `> `.

### Example 4: Serial REPL "Execute code to blink pin 15"

**User types:** `execute code: for i in range(5): Pin(15,OUT).toggle(); time.sleep_ms(200)` and presses Enter.

**Flow:**
1. LLM receives the request and responds with a tool call to `exec_code`:
   ```json
   {"function": {"name": "exec_code", "arguments": "{\"code\": \"for i in range(5):\\\\n  Pin(15,OUT).toggle()\\\\n  time.sleep_ms(200)\"}"}}
   ```
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

---

## 12. Constraints & Design Decisions

### 12.1 Memory Constraints

- **520 KB SRAM:** LLM context is limited to 4000 tokens (`MAX_CONTEXT_TOKENS`). Response is capped at 512 tokens (`MAX_RESPONSE_TOKENS`). Tool-calling rounds are limited to 4 (`TOOL_CALL_MAX_ROUNDS`).
- **No `collections.Counter`:** Replaced with `_counter()` using plain dicts.
- **No `re.findall()`:** Tokenization uses a manual character loop.
- **No `str.isalnum()`:** Character ranges `("a" <= ch <= "z")` and `("0" <= ch <= "9")` are used instead.

### 12.2 Timing Constraints

- **Serial REPL blocking:** `sys.stdin.settimeout(0)` is unreliable on some MicroPython builds. A 20 ms timeout is used instead.
- **LED blink accuracy:** `machine.Timer(0)` (hardware timer) is preferred over `machine.Timer(-1)` (virtual timer). A minimum-gap guard suppresses timer drift artifacts.
- **Telegram thread isolation:** Telegram polling runs in `_thread` so its HTTP blocking never delays the serial REPL or timer callbacks.

### 12.3 Network Constraints

- **HTTP timeout:** Reduced to 2 seconds for Telegram polling to avoid blocking the background thread for too long.
- **LLM timeout:** 30 seconds for DeepSeek API calls (enough for `deepseek-flash` on a good connection).
- **Error suppression:** Expected network errors (`ETIMEDOUT`, `ECONNRESET`, `EHOSTUNREACH`) are suppressed in `telegram_loop()` to avoid log spam.

### 12.4 Security Constraints

- **`exec_code()` sandbox:** Only `_builtins_safe` is available. No `__import__`, no file I/O (other than memory save/load), no network access from executed code.
- **Telegram access control:** `TELEGRAM_ALLOWED_USERS` can restrict which chat IDs are accepted. Empty list means all users are allowed.

### 12.5 Skills Constraints

- **Memory isolation:** `load_skills()` uses `exec()` in an isolated namespace. No globals from the agent module are shared. Skills must import `time`, `machine`, etc. internally.
- **No heavy stdlib:** Skills cannot use `collections.Counter`, `re.findall`, `str.isalnum`, or `os.path`. These are unavailable on stock MicroPython builds.
- **No built-in shadowing:** Skill file names must not collide with MicroPython built-in modules (`memory.py`, `time.py`, `re.py`, `os.py`).
- **Disk footprint:** Each skill file must fit within the ~114 KB used flash budget. Keep skill modules minimal.
- **No email deletion:** The agent has no email tools.

---

## 13. Troubleshooting

### 13.1 LED Blink Stretched or Glitchy

- **Symptom:** LED period is 3–4x longer than requested, or visible on-off spikes.
- **Cause:** Main loop blocked by `input()` or `urequests.get()`.
- **Fix:** Use `sys.stdin.settimeout(0.02)` for serial input. Telegram polling must run in `_thread` or a `machine.Timer` fallback.

### 13.2 CLI Prompt Missing After Telegram Output

- **Symptom:** After a Telegram message is processed, the serial REPL does not show `> ` until Enter is pressed.
- **Cause:** The background `_thread` Telegram path bypasses the `_telegram_due` flag that `serial_loop()` monitors.
- **Fix:** `boot.py`'s `_tg_worker` prints `> ` directly after `telegram_loop()` returns `True`.

### 13.3 DeepSeek Auth Failures

- **Symptom:** "Authentication Fails (governor)" for non-command Telegram messages.
- **Cause:** Invalid, expired, or rate-limited API key. Or the placeholder key is still in `config.py`.
- **Fix:** Verify `config.LLM_API_KEY` is a real DeepSeek key. Check quota at platform.deepseek.com.

### 13.4 `/info` Hang on Serial

- **Symptom:** Typing `/info` in serial REPL causes the prompt to hang.
- **Cause:** `sys.stdin.settimeout(0)` returns `None` for newlines on some MicroPython builds.
- **Fix:** Use `sys.stdin.settimeout(0.02)` with a 300 ms auto-submit fallback for incomplete lines.

### 13.5 Memory Not Persisting

- **Symptom:** Memory is empty after reboot.
- **Cause:** `/sd` directory does not exist or is not writable. The Pico 2 W must have a microSD card mounted, or the storage path must be changed to flash.
- **Fix:** Check `pico_memory.py`'s `storage_dir` path and ensure the `/memory` directory exists and is writable.

### 13.6 Skills Not Loading

- **Symptom:** `/skills` returns empty list or `ImportError` on boot.
- **Cause:** Skill file name shadows a built-in module (`memory.py`, `time.py`, `re.py`), or the skill file is missing required imports (`time`, `machine`).
- **Fix:** Rename the file to avoid built-in collisions. Ensure every dependency is imported at the top of the skill file. Verify with `python3 -m py_compile skills/<name>.py`.

### 13.7 Skill Tool Execution Errors

- **Symptom:** A skill tool fails with `unexpected keyword argument` or `NameError: name 'time' isn't defined`.
- **Cause:** The tool callable signature does not match the `parameters` schema in `TOOLS`, or the skill file omitted an import.
- **Fix:** Align callable signatures with the JSON schema exactly. Import all used modules inside the skill file.

---

## 14. File Structure

```
pico2wclaw/
├── boot.py           # Boot script: WiFi, NTP, agent, Telegram thread
├── agent.py          # Core agent: LLM client, tool loop, serial + Telegram
├── tools.py          # Tool registry, JSON schemas, hardware callables
├── pico_memory.py    # TF-IDF memory, filesystem persistence
├── skills_loader.py  # Loads skills/*.py skill files at startup
├── display.py        # OLED + buzzer UI, status, boot splash
├── led_blink.py      # Persistent LED blink via hardware timer
├── config.py         # WiFi, LLM, Telegram, agent settings
├── ssd1306.py        # SSD1306 OLED driver (I2C)
├── skills/           # Optional skill modules
│   └── led_patterns.py
└── README.md         # Setup instructions
```

Upload all `.py` files to the Pico 2 W using Thonny IDE or `mpremote`. Ensure `ssd1306.py` is present in the same directory. If you add custom skills, create the `skills/` directory and place `.py` skill files inside.

---

## 15. Summary

Pico2WClaw is a complete embedded agentic AI system that fits within the Raspberry Pi Pico 2 W's resource constraints. It achieves this through:

- **Modular architecture:** Each concern (boot, agent, tools, memory, display, LED) is isolated in its own module.
- **Non-blocking I/O:** Serial REPL and Telegram polling coexist without blocking each other.
- **Minimal memory footprint:** Keyword-based memory instead of embeddings; tool schemas are compact; context is bounded.
- **Hardware-aware design:** Direct register access via `machine` module; timer-based LED blink; I2C display and buzzer PWM.
- **Resilient error handling:** Graceful degradation when WiFi, LLM, or peripherals fail.

The result is a device that can understand natural language, remember context, control hardware, and execute code—all from a $6 microcontroller.
