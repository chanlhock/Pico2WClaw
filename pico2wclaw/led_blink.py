"""
led_blink.py — Persistent onboard-LED blink helper for Raspberry Pi Pico 2 W.

Uses Pin("LED") so it works through the CYW43 chip on Pico W / Pico 2 W.
A module-scoped Timer keeps blinking even after exec_code() returns.
"""

import machine

_t = None
_state = {"running": False}


def start(freq_hz=1):
    """Start blinking the onboard LED at `freq_hz` (Hz). Use this for persistent blinking."""
    global _t
    stop()
    try:
        led = machine.Pin("LED", machine.Pin.OUT)
    except Exception as e:
        return "Error: onboard LED unavailable (%s)" % e
    _state["running"] = True

    def _toggle(_):
        if not _state["running"]:
            return
        led.value(1 if led.value() == 0 else 0)

    # Clamp frequency so the timer period stays valid and visible
    hz = float(freq_hz)
    if hz <= 0:
        hz = 1.0
    if hz > 50:
        hz = 50.0
    period_ms = int(1000 / hz)
    _t = machine.Timer(-1)
    _t.init(period=period_ms, mode=machine.Timer.PERIODIC, callback=_toggle)
    return "Blinking at %s Hz (period %s ms)" % (hz, period_ms)


def start_period(period_ms=1000):
    """Start blinking the onboard LED with explicit period in ms.
    The LED stays in each state for `period_ms` milliseconds.
    Example: period_ms=2000 means 2s ON, 2s OFF.
    """
    global _t
    stop()
    try:
        led = machine.Pin("LED", machine.Pin.OUT)
    except Exception as e:
        return "Error: onboard LED unavailable (%s)" % e
    _state["running"] = True

    def _toggle(_):
        if not _state["running"]:
            return
        led.value(1 if led.value() == 0 else 0)

    # Clamp to a visible range
    ms = int(period_ms)
    if ms <= 0:
        ms = 1000
    if ms > 10000:
        ms = 10000
    _t = machine.Timer(-1)
    _t.init(period=ms, mode=machine.Timer.PERIODIC, callback=_toggle)
    return "Blinking with period %s ms (%s s ON, %s s OFF)" % (ms, ms // 1000, ms // 1000)


def stop():
    """Stop blinking and turn the LED off."""
    global _t
    _state["running"] = False
    if _t:
        try:
            _t.deinit()
        except Exception:
            pass
        _t = None
    try:
        machine.Pin("LED", machine.Pin.OUT).off()
    except Exception:
        pass
    return "Blink stopped"


def toggle():
    """Single manual toggle."""
    machine.Pin("LED", machine.Pin.OUT).toggle()
    return "toggled"
