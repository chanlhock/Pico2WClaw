"""
tools.py — Tool registry for Pico2WClaw.
Each tool is a Python callable with a JSON schema for the LLM.
"""

import machine
import time
import utime
import sys

# Keep a reference to builtins for safe exec
_builtins_safe = {
    "print": print,
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "range": range,
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "round": round,
    "True": True,
    "False": False,
    "None": None,
}

# Cache for pin objects to avoid conflicts
_pin_cache = {}


def _get_pin(pin_id, mode=None):
    pin_id = int(pin_id)
    if pin_id not in _pin_cache:
        _pin_cache[pin_id] = machine.Pin(pin_id)
    p = _pin_cache[pin_id]
    if mode is not None:
        if mode in (machine.Pin.IN, machine.Pin.OUT):
            p.init(mode)
        elif mode == "IN":
            p.init(machine.Pin.IN)
        elif mode == "OUT":
            p.init(machine.Pin.OUT)
    return p


def gpio_write(pin, value):
    """Set a GPIO pin HIGH (1) or LOW (0)."""
    _get_pin(pin, machine.Pin.OUT).value(int(value))
    return f"GPIO{pin} set to {'HIGH' if value else 'LOW'}"


def gpio_read(pin):
    """Read digital state of a GPIO pin."""
    val = _get_pin(pin, machine.Pin.IN).value()
    return f"GPIO{pin} = {'HIGH' if val else 'LOW'} ({val})"


def adc_read(pin):
    """Read ADC value (12-bit, 0-4095) from a pin."""
    try:
        adc = machine.ADC(machine.Pin(int(pin)))
        raw = adc.read_u16()  # 16-bit on RP2350, scale down
        val12 = raw >> 4  # 16-bit to 12-bit
        voltage = (val12 / 4095) * 3.3
        return f"ADC{pin}: raw={val12}, voltage={voltage:.2f}V"
    except Exception as e:
        return f"ADC read error on pin {pin}: {e}"


def pwm_set(pin, freq, duty):
    """Set PWM on a pin. duty 0-65535 (RP2350 16-bit)."""
    p = _get_pin(pin)
    pwm = machine.PWM(p)
    pwm.freq(int(freq))
    pwm.duty_u16(int(duty))
    return f"PWM set on GPIO{pin}: {int(freq)}Hz, duty={int(duty)}/65535"


def i2c_scan(bus=0):
    """Scan I2C bus and return list of device addresses."""
    try:
        i2c = machine.I2C(bus, sda=machine.Pin(0), scl=machine.Pin(1))
        devices = i2c.scan()
        if devices:
            addrs = [hex(d) for d in devices]
            return f"I2C bus {bus} devices: {', '.join(addrs)}"
        return f"I2C bus {bus}: no devices found"
    except Exception as e:
        return f"I2C scan error: {e}"


def device_info():
    """Return Pico 2 W hardware info."""
    import sys
    import gc
    gc.collect()
    try:
        import network
        wlan = network.WLAN()
        rssi = wlan.status('rssi') if wlan.isconnected() else None
    except Exception:
        rssi = None
    freq = machine.freq()
    try:
        import gc
        free_ram = gc.mem_free()
        alloc_ram = gc.mem_alloc()
        total_ram = free_ram + alloc_ram
        ram_str = f"{total_ram:,} bytes (free: {free_ram:,}, used: {alloc_ram:,})"
    except Exception:
        ram_str = "N/A"
    try:
        import os
        st = os.statvfs('/')
        block_size = st[0]
        total_blocks = st[2]
        free_blocks = st[3]
        flash_total = block_size * total_blocks
        flash_free = block_size * free_blocks
        flash_str = f"{flash_total:,} bytes (free: {flash_free:,}, used: {flash_total - flash_free:,})"
    except Exception:
        flash_str = "N/A"
    try:
        temp_raw = machine.ADC(4).read_u16()
        temp_c = 27 - ((temp_raw * 3.3 / 65535) - 0.706) / 0.001721
        temp_str = f"{temp_c:.1f}C"
    except Exception:
        temp_str = "N/A"
    try:
        mp_ver = sys.version.split()[0].rstrip(";") if hasattr(sys, "version") else "unknown"
    except Exception:
        mp_ver = "unknown"
    info = (
        f"Board: Raspberry Pi Pico 2 W (RP2350)\n"
        f"CPU freq: {freq/1_000_000:.0f} MHz\n"
        f"RAM: {ram_str}\n"
        f"Flash: {flash_str}\n"
        f"Chip temp: {temp_str}\n"
        f"WiFi RSSI: {rssi} dBm\n"
        f"MicroPython: {mp_ver}"
    )
    if rssi is None:
        info = info.replace("\nWiFi RSSI: None dBm", "")
    return info


def display_text(line1="", line2="", line3="", line4=""):
    """Write up to 4 lines on the OLED display."""
    from display import show_text
    show_text(str(line1), str(line2), str(line3), str(line4))
    return "Display updated"


def display_bottom(line1="", line2="", line3="", line4=""):
    """Write up to 4 lines on the lower half of the OLED display."""
    from display import show_bottom
    show_bottom(str(line1), str(line2), str(line3), str(line4))
    return "Display updated"


def clear_display_bottom():
    """Clear the lower half of the OLED display."""
    from display import clear_bottom
    clear_bottom()
    return "Display cleared"


def read_dht(pin=4):
    """Read a DHT11 sensor on the given GPIO pin. Returns 'T=..C H=..%'."""
    try:
        import dht
        from machine import Pin
        time.sleep(2)   # To resolve the [Errno 110] ETIMEDOUT error 
        sensor = dht.DHT11(Pin(int(pin)))
        sensor.measure()
        t = sensor.temperature()
        h = sensor.humidity()
        return "T=%dC H=%d%%" % (t, h)
    except Exception as e:
        return "DHT error: %s" % e

def beep_now(freq=1000, duration=0.1):
    """Play a beep on the buzzer (GPIO22)."""
    from display import beep
    beep(int(freq), float(duration))
    return f"Beep: {freq}Hz for {duration}s"


def buzzer_play_tune(melody, beat_seconds=0.4, duty=32768, title=""):
    """Play a melody on the buzzer (GPIO22).

    melody: list of [note, beats] pairs. note is a note name
    (C, D, E, F, G, A, B, C6, R) or a frequency in Hz. beats is
    the length multiplier. R = rest (silence).
    """
    from display import beep
    try:
        beat_seconds = float(beat_seconds)
    except Exception:
        beat_seconds = 0.4

    if title:
        try:
            from display import show_bottom
            show_bottom("Playing tune", str(title)[:21], "", "")
        except Exception:
            pass

    _NOTE_OFFSET = {
        "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4,
        "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9,
        "A#": 10, "B": 11,
    }

    def _note_freq(note):
        try:
            if isinstance(note, (int, float)) and note:
                return float(note)
            s = str(note).upper().strip()
            if s == "R":
                return 0.0
            if s in _NOTE_OFFSET:
                octave = 4
                name = s
            else:
                # Parse note+octave like G4, A4, C5, B5, G6, E6
                name = s[0]
                if len(s) >= 2 and s[1] == "#":
                    name = s[:2]
                    octave = int(s[2:]) if len(s) > 2 else 4
                else:
                    octave = int(s[1:]) if len(s) > 1 else 4
            midi = (octave + 1) * 12 + _NOTE_OFFSET.get(name, 0)
            return 440.0 * (2.0 ** ((midi - 69) / 12.0))
        except Exception:
            return 0.0

    def _play():
        for item in melody:
            try:
                note, beats = item
            except Exception:
                continue
            beats = max(beats, 0)
            duration = beat_seconds * beats
            freq = _note_freq(note)
            if freq:
                beep(int(freq), duration * 0.9)
            else:
                utime.sleep(duration * 0.9)
            utime.sleep(duration * 0.1)

        try:
            from display import clear_bottom
            clear_bottom()
        except Exception:
            pass

    try:
        import _thread
        _thread.start_new_thread(_play, ())
    except Exception:
        _play()
    return "Tune playing"


def exec_code(code):
    """Execute MicroPython code in a restricted environment. Returns captured output."""
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


# ---------------------------------------------------------------------------
# Tool registry — the LLM sees these schemas
# ---------------------------------------------------------------------------
TOOL_REGISTRY = {
    "gpio_write": {
        "name": "gpio_write",
        "description": "Set a GPIO pin HIGH or LOW. Use for LEDs, relays, transistors.",
        "parameters": {
            "type": "object",
            "properties": {
                "pin": {"type": "integer", "description": "GPIO pin number (0-29)"},
                "value": {"type": "integer", "enum": [0, 1], "description": "0=LOW, 1=HIGH"},
            },
            "required": ["pin", "value"],
        },
        "callable": gpio_write,
    },
    "gpio_read": {
        "name": "gpio_read",
        "description": "Read digital state of a GPIO pin.",
        "parameters": {
            "type": "object",
            "properties": {
                "pin": {"type": "integer", "description": "GPIO pin number (0-29)"},
            },
            "required": ["pin"],
        },
        "callable": gpio_read,
    },
    "adc_read": {
        "name": "adc_read",
        "description": "Read 12-bit ADC value and voltage from a pin.",
        "parameters": {
            "type": "object",
            "properties": {
                "pin": {"type": "integer", "description": "ADC-capable GPIO pin (e.g. 26, 27, 28)"},
            },
            "required": ["pin"],
        },
        "callable": adc_read,
    },
    "pwm_set": {
        "name": "pwm_set",
        "description": "Set PWM frequency and duty on a GPIO pin.",
        "parameters": {
            "type": "object",
            "properties": {
                "pin": {"type": "integer"},
                "freq": {"type": "integer", "description": "Frequency in Hz"},
                "duty": {"type": "integer", "description": "Duty cycle 0-65535 (16-bit)"},
            },
            "required": ["pin", "freq", "duty"],
        },
        "callable": pwm_set,
    },
    "i2c_scan": {
        "name": "i2c_scan",
        "description": "Scan I2C bus for connected devices.",
        "parameters": {
            "type": "object",
            "properties": {
                "bus": {"type": "integer", "description": "I2C bus number (default 0)"},
            },
            "required": [],
        },
        "callable": i2c_scan,
    },
    "device_info": {
        "name": "device_info",
        "description": "Return Pico 2 W hardware info (CPU, RAM, temp, WiFi RSSI).",
        "parameters": {"type": "object", "properties": {}},
        "callable": device_info,
    },
    "display_text": {
        "name": "display_text",
        "description": "Write up to 4 lines on the OLED display (128x64).",
        "parameters": {
            "type": "object",
            "properties": {
                "line1": {"type": "string"},
                "line2": {"type": "string"},
                "line3": {"type": "string"},
                "line4": {"type": "string"},
            },
            "required": [],
        },
        "callable": display_text,
    },
    "display_bottom": {
        "name": "display_bottom",
        "description": "Write up to 4 lines on the lower half of the OLED display (transient info).",
        "parameters": {
            "type": "object",
            "properties": {
                "line1": {"type": "string"},
                "line2": {"type": "string"},
                "line3": {"type": "string"},
                "line4": {"type": "string"},
            },
            "required": [],
        },
        "callable": display_bottom,
    },
    "clear_display_bottom": {
        "name": "clear_display_bottom",
        "description": "Clear the lower half of the OLED display.",
        "parameters": {"type": "object", "properties": {}},
        "callable": clear_display_bottom,
    },

    "read_dht": {
        "name": "read_dht",
        "description": "Read a DHT11 sensor on a GPIO pin. Returns temperature and humidity.",
        "parameters": {
            "type": "object",
            "properties": {"pin": {"type": "integer", "description": "GPIO pin number (default 4)"}},
            "required": [],
        },
        "callable": read_dht,
    },

        "beep_now": {
        "name": "beep_now",
        "description": "Play a short beep on the buzzer (GPIO22). freq in Hz, duration in seconds.",
        "parameters": {
            "type": "object",
            "properties": {
                "freq": {"type": "integer"},
                "duration": {"type": "number"},
            },
            "required": [],
        },
        "callable": beep_now,
    },
    "buzzer_play_tune": {
        "name": "buzzer_play_tune",
        "description": "Play a melody on the buzzer (GPIO22). Prefer this over exec_code for tunes. melody is a list of [note, beats] pairs. note is a note name (C, D, E, F, G, A, B, C6, R) or Hz integer. beats is length multiplier. beat_seconds is duration of one beat in seconds.",
        "parameters": {
            "type": "object",
            "properties": {
                "melody": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": ["string", "number"]},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                },
                "beat_seconds": {"type": "number"},
                "title": {"type": "string"},
                "duty": {"type": "integer"},
            },
            "required": ["melody"],
        },
        "callable": buzzer_play_tune,
    },
    "exec_code": {
        "name": "exec_code",
        "description": "Execute MicroPython code on the device. Returns stdout or error. IMPORTANT: Do NOT use this for buzzer melodies — the buzzer is wired to GPIO22, not GPIO15. Use buzzer_play_tune instead.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "MicroPython source code to execute"},
            },
            "required": ["code"],
        },
        "callable": exec_code,
    },
    "led_blink_start": {
        "name": "led_blink_start",
        "description": "Start blinking the onboard LED at a given frequency (Hz). IMPORTANT: Use this tool for persistent blinking. Do NOT use exec_code to create timers or threads — they die when exec_code returns. Use Pin('LED') for the onboard LED, not Pin(25).",
        "parameters": {
            "type": "object",
            "properties": {
                "freq_hz": {"type": "number", "description": "Full cycles per second. 0.5 = one full ON+OFF cycle every 2 seconds (1s ON, 1s OFF). 0.25 = 2s ON + 2s OFF."},
            },
            "required": ["freq_hz"],
        },
        "callable": None,
    },
    "start_blink": {
        "name": "start_blink",
        "description": "Start blinking the onboard LED with an explicit period in milliseconds. Use this when the user specifies a duration like 'every 2 seconds'. IMPORTANT: Use this tool for persistent blinking. Do NOT use exec_code to create timers or threads — they die when exec_code returns. Use Pin('LED') for the onboard LED, not Pin(25).",
        "parameters": {
            "type": "object",
            "properties": {
                "period_ms": {"type": "integer", "description": "Time in milliseconds the LED stays in each state. For 'blink every 2 seconds', use 2000 (2s ON, then 2s OFF). For 'blink every 1 second', use 1000 (1s ON, 1s OFF)."},
            },
            "required": ["period_ms"],
        },
        "callable": None,
    },
    "led_blink_stop": {
        "name": "led_blink_stop",
        "description": "Stop the persistent onboard-LED blink and turn the LED off.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "callable": None,
    },
    "led_toggle": {
        "name": "led_toggle",
        "description": "Toggle the onboard LED once.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "callable": None,
    },
    "cron_add": {
        "name": "cron_add",
        "description": "Schedule a recurring GPIO/ADC/DHT monitor that sends status to Telegram. type: gpio, adc, or dht.",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["gpio", "adc", "dht"], "description": "Monitor type"},
                "pin": {"type": "integer", "description": "GPIO/ADC pin number"},
                "interval_ms": {"type": "integer", "description": "Interval in milliseconds (e.g. 5000)"},
                "chat_id": {"type": "integer", "description": "Telegram chat id to send to (optional)"},
                "message": {"type": "string", "description": "Message template; use {value}, {pin}, {type} (optional)"},
            },
            "required": ["type", "pin", "interval_ms"],
        },
        "callable": None,
    },
    "cron_list": {
        "name": "cron_list",
        "description": "List scheduled cron jobs.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "callable": None,
    },
    "cron_remove": {
        "name": "cron_remove",
        "description": "Remove a cron job by id.",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Job id"},
            },
            "required": ["id"],
        },
        "callable": None,
    },
}


def merge_skill_tools(extra_tools):
    """Merge skill-provided tools into the main registry."""
    global TOOL_REGISTRY
    TOOL_REGISTRY.update(extra_tools)


def get_tool_defs():
    """Return OpenAI-compatible tool definitions for the LLM."""
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


def call_tool(name, arguments):
    """Execute a tool by name with the given arguments dict."""
    if name not in TOOL_REGISTRY:
        return f"Error: unknown tool '{name}'"
    fn = TOOL_REGISTRY[name]["callable"]
    if fn is None:
        # Lazy import for tools defined in separate modules
        if name == "led_blink_start":
            from led_blink import start
            return str(start(**arguments))
        if name == "start_blink":
            from led_blink import start_period
            return str(start_period(**arguments))
        if name == "led_blink_stop":
            from led_blink import stop
            return str(stop())
        if name == "led_toggle":
            from led_blink import toggle
            return str(toggle())
        if name == "cron_add":
            from pico_cron import cron_add
            return str(cron_add(**arguments))
        if name == "cron_list":
            from pico_cron import cron_list
            return str(cron_list())
        if name == "cron_remove":
            from pico_cron import cron_remove
            return str(cron_remove(**arguments))
        return "Error: tool not implemented"
    try:
        result = fn(**arguments)
        if result is None:
            return "(tool executed, no output)"
        return str(result)
    except TypeError as e:
        return f"Tool call error (wrong args?): {e}"
    except Exception as e:
        return f"Tool execution error: {e}"
