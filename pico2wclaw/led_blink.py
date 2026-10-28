"""
led_blink.py — Persistent onboard-LED blink helper for Raspberry Pi Pico 2 W.

Uses Pin("LED") so it works through the CYW43 chip on Pico W / Pico 2 W.
A module-scoped Timer keeps blinking even after exec_code() returns.

Blink timing is guarded by a minimum-gap check so that occasional delayed
timer callbacks cannot produce visible on-off spikes.
"""

import machine
import time


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

    def start(self, period_ms):
        self.stop()
        try:
            self.led = machine.Pin("LED", machine.Pin.OUT)
        except Exception as e:
            return "Error: onboard LED unavailable (%s)" % e
        self.running = True
        self.period_ms = max(1, min(10000, int(period_ms)))
        self.last_toggle_ms = 0
        try:
            self.t = machine.Timer(0)
        except Exception:
            self.t = machine.Timer(-1)
        self.t.init(period=self.period_ms, mode=machine.Timer.PERIODIC, callback=self._toggle)
        return "Blinking with period %s ms (%s s ON, %s s OFF)" % (
            self.period_ms,
            self.period_ms // 1000,
            self.period_ms // 1000,
        )

    def stop(self):
        self.running = False
        self.last_toggle_ms = 0
        if self.t:
            try:
                self.t.deinit()
            except Exception:
                pass
            self.t = None
        if self.led:
            try:
                self.led.off()
            except Exception:
                pass
            self.led = None
        return "Blink stopped"


_blinker = _Blinker()


def start(freq_hz=1):
    """Start blinking the onboard LED at `freq_hz` (Hz). Use this for persistent blinking."""
    hz = float(freq_hz)
    if hz <= 0:
        hz = 1.0
    if hz > 50:
        hz = 50.0
    period_ms = int(1000 / hz)
    return _blinker.start(period_ms)


def start_period(period_ms=1000):
    """Start blinking the onboard LED with explicit period in ms.
    The LED stays in each state for `period_ms` milliseconds.
    Example: period_ms=2000 means 2s ON, 2s OFF.
    """
    return _blinker.start(period_ms)


def stop():
    """Stop blinking and turn the LED off."""
    return _blinker.stop()


def toggle():
    """Single manual toggle."""
    machine.Pin("LED", machine.Pin.OUT).toggle()
    return "toggled"
