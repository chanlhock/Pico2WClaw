"""
display.py — OLED + buzzer UI for Pico2WClaw.
Integrates SSD1306 display and buzzer for status feedback.
"""

import machine
import utime
import gc
import framebuf

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

        i2c = machine.I2C(0, sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=200000)
        _oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c)
        _oled.fill(0)
        _oled.text("Pico2WClaw", 0, 0)
#         _oled.text("  Init...", 0, 16)
        _oled.show()
        return True
    except Exception as e:
        print("[display] OLED init failed:", e)
        _oled = None
        return False


# ------------------------------------------------------------------
# Display state (8 lines total: 4 top + 4 bottom)
# ------------------------------------------------------------------
_top_lines = ["", "", "", ""]
_bottom_lines = ["", "", "", ""]


def _render():
    """Render both regions. Retries/reinits OLED instead of crashing."""
    global _oled
    if _oled is None:
        if not _init_display():
            return
    for attempt in range(3):
        try:
            _oled.fill(0)
            y = 0
            for text in (_top_lines + _bottom_lines):
                if text:
                    _oled.text(str(text)[:21], 0, y)
                y += 8
            _oled.show()
            return
        except Exception as e:
            print("[display] render failed:", e)
            print("Recovering through attempt #:", attempt+1)
            print("\n>")  # display back the prompt at serial cli
            if attempt < 2:
                utime.sleep_ms(100)
                _init_display()
            else:
                _disable_display()


def _disable_display():
    global _oled
    _oled = None

def clear():
    if _oled is None:
        return
    try:
        _oled.fill(0)
        _oled.show()
    except Exception as e:
        print("[display] clear failed:", e)
        _disable_display()


def show_text(line1="", line2="", line3="", line4=""):
    """Update the persistent top 4 lines and clear the bottom region."""
    global _top_lines, _bottom_lines
    _top_lines = [str(line1), str(line2), str(line3), str(line4)]
    _bottom_lines = ["", "", "", ""]
    _render()


def show_bottom(line1="", line2="", line3="", line4=""):
    """Update only the transient bottom 4 lines."""
    global _bottom_lines
    _bottom_lines = [str(line1), str(line2), str(line3), str(line4)]
    _render()


def clear_bottom():
    """Clear the transient bottom 4 lines and restore the top region."""
    global _bottom_lines
    _bottom_lines = ["", "", "", ""]
    _render()


def show_status(state, detail=""):
    """Top line = title, bottom = state+detail (top region only)."""
    show_text("Pico2WClaw", state[:16], detail[:16], "")


def show_message(title, body):
    """Show a 2-line message and beep (top region)."""
    show_text(title[:21], body[:21], "", "")
    beep_click()

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
#     if display_ok:
#         for frame in _SPLASH_FRAMES:
#             try:
#                 clear()
#                 _oled.text(frame, 0, 0)
#                 _oled.show()
#             except Exception as e:
#                 print("[display] splash frame failed:", e)
#                 _disable_display()
#                 break
#             utime.sleep_ms(200)
#         beep(500, 0.05)
#     else:
#         beep_error()
        
    if display_ok:
        gc.collect()
        # Display the Raspberry Pi logo on start-up
        #LOGO = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00|?\x00\x01\x86@\x80\x01\x01\x80\x80\x01\x11\x88\x80\x01\x05\xa0\x80\x00\x83\xc1\x00\x00C\xe3\x00\x00~\xfc\x00\x00L'\x00\x00\x9c\x11\x00\x00\xbf\xfd\x00\x00\xe1\x87\x00\x01\xc1\x83\x80\x02A\x82@\x02A\x82@\x02\xc1\xc2@\x02\xf6>\xc0\x01\xfc=\x80\x01\x18\x18\x80\x01\x88\x10\x80\x00\x8c!\x00\x00\x87\xf1\x00\x00\x7f\xf6\x00\x008\x1c\x00\x00\x0c \x00\x00\x03\xc0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

        LOGO = bytearray(b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00|?\x00\x01\x86@\x80\x01\x01\x80\x80\x01\x11\x88\x80\x01\x05\xa0\x80\x00\x83\xc1\x00\x00C\xe3\x00\x00~\xfc\x00\x00L'\x00\x00\x9c\x11\x00\x00\xbf\xfd\x00\x00\xe1\x87\x00\x01\xc1\x83\x80\x02A\x82@\x02A\x82@\x02\xc1\xc2@\x02\xf6>\xc0\x01\xfc=\x80\x01\x18\x18\x80\x01\x88\x10\x80\x00\x8c!\x00\x00\x87\xf1\x00\x00\x7f\xf6\x00\x008\x1c\x00\x00\x0c \x00\x00\x03\xc0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
        #print("LOGO len:", len(LOGO))
        fb = framebuf.FrameBuffer(LOGO,32,32, framebuf.MONO_HLSB)
        #_oled.fill(0)
        _oled.text("Booting", 8, 56)
        for i in range(-64,128,5):
             _oled.blit(fb,i,16)
             if i < -32:  _oled.text(".", 64, 56)
             if i >= -32 and i < 0:  _oled.text(".", 72, 56)
             if i >= 0 and i <32: _oled.text(".", 80, 56)
             if i >= 32 and i <64: _oled.text(".", 88, 56)
             if i >= 64: _oled.text(".", 96, 56)
             _oled.show()
        fb = framebuf.FrameBuffer(LOGO,32,32, framebuf.MONO_HLSB)
        _oled.fill(0)

        # Blit the image from the framebuffer to the oled display
        _oled.blit(fb, 96, 8)
        beep(500, 0.05)
        gc.collect()
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
