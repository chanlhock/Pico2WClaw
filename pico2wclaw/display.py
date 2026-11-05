"""
display.py — OLED + buzzer UI for Pico2WClaw.
Integrates SSD1306 display and buzzer for status feedback.
"""

import machine
import utime

# ---------------------------------------------------------------------------
# Hardware config (matches your existing ble.py wiring)
# ---------------------------------------------------------------------------
I2C_SDA = 20
I2C_SCL = 21
BUZZER_PIN = 22
OLED_WIDTH = 128
OLED_HEIGHT = 64

# ---------------------------------------------------------------------------
# Buzzer
# ---------------------------------------------------------------------------
_buzzer = None


def _init_buzzer():
    global _buzzer
    try:
        _buzzer = machine.PWM(machine.Pin(BUZZER_PIN))
        _buzzer.duty_u16(0)
    except Exception as e:
        print("[display] buzzer init failed:", e)
        _buzzer = None


def beep(freq=1000, duration=0.1):
    """Short single beep."""
    if _buzzer is None:
        return
    try:
        _buzzer.freq(freq)
        _buzzer.duty_u16(32768)
        utime.sleep(duration)
        _buzzer.duty_u16(0)
    except Exception:
        pass


def beep_success():
    """Ascending tone for success."""
    if _buzzer is None:
        return
    for f in (440, 660, 880):
        beep(f, 0.08)


def beep_error():
    """Descending tone for error."""
    if _buzzer is None:
        return
    for f in (880, 660, 440):
        beep(f, 0.1)


def beep_click():
    """Very short tick for UI feedback."""
    beep(2000, 0.03)


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
_oled = None


def _init_display():
    global _oled
    try:
        from ssd1306 import SSD1306_I2C

        i2c = machine.I2C(0, sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=400000)
        _oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c)
        _oled.fill(0)
        _oled.text("Pico2WClaw", 0, 0)
        _oled.text("  Init...", 0, 16)
        _oled.show()
        return True
    except Exception as e:
        print("[display] OLED init failed:", e)
        _oled = None
        return False


def clear():
    if _oled is None:
        return
    try:
        _oled.fill(0)
        _oled.show()
    except Exception as e:
        print("[display] clear failed:", e)
        _disable_display()


def _disable_display():
    global _oled
    _oled = None


def show_text(line1="", line2="", line3="", line4=""):
    """Draw up to 4 lines (max 16 chars each at default font)."""
    if _oled is None:
        return
    try:
        _oled.fill(0)
        y = 0
        for text in (line1, line2, line3, line4):
            if text:
                _oled.text(text[:21], 0, y)
            y += 16
        _oled.show()
    except Exception as e:
        print("[display] show_text failed:", e)
        _disable_display()


def show_status(state, detail=""):
    """Top line = title, bottom = state+detail."""
    show_text("Pico2WClaw", state[:16], detail[:16])


# ---------------------------------------------------------------------------
# Boot splash
# ---------------------------------------------------------------------------
_SPLASH_FRAMES = [
    "Pico2WClaw",
    " Booting",
    "  Booting.",
    "   Booting..",
    "    Booting...",
]


def boot_splash():
    _init_buzzer()
    display_ok = _init_display()
    if display_ok:
        for frame in _SPLASH_FRAMES:
            try:
                clear()
                _oled.text(frame, 0, 0)
                _oled.show()
            except Exception as e:
                print("[display] splash frame failed:", e)
                _disable_display()
                break
            utime.sleep_ms(200)
        beep(500, 0.05)
    else:
        beep_error()


# ---------------------------------------------------------------------------
# Agent UI helpers
# ---------------------------------------------------------------------------
_STATUS_LINES = {
    "ready": ("Ready", "awaiting input"),
    "thinking": ("Thinking", "calling LLM..."),
    "tool": ("Tool", "executing..."),
    "error": ("Error", "check serial"),
    "wifi_ok": ("WiFi", "connected"),
    "wifi_fail": ("WiFi", "FAILED"),
    "llm_ok": ("LLM", "response OK"),
    "llm_fail": ("LLM", "FAILED"),
}


def set_status(key, beep_type=None):
    line1, line2 = _STATUS_LINES.get(key, (key, ""))
    show_status(line1, line2)
    if beep_type == "success":
        beep_success()
    elif beep_type == "error":
        beep_error()
    elif beep_type == "click":
        beep_click()


def show_message(title, body):
    """Show a 2-line message and beep."""
    show_text(title[:21], body[:21])
    beep_click()


def deinit(self_only=False):
    """Tear down peripherals."""
    global _oled, _buzzer
    if _buzzer is not None:
        try:
            _buzzer.duty_u16(0)
            if self_only:
                _buzzer.deinit()
        except Exception:
            pass
    if not self_only:
        _oled = None
        _buzzer = None
