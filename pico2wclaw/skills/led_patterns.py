"""
skills/led_patterns.py — LED pattern skill for Pico2WClaw.

Provides a richer set of LED behaviors beyond simple on/off/blink.
Use this skill when the user asks for blinking patterns, SOS, heartbeat,
or other LED signaling.
"""

import time

SKILL_INSTR = (
    "LED pattern skill. Use led_pattern when the user asks for "
    "SOS, heartbeat, candle, or any repeated LED pattern. "
    "For simple on/off/blink, use led_toggle/start_blink instead."
)


def _sos():
    """SOS Morse: ... --- ..."""
    from led_blink import start_period, stop
    stop()
    dots = 3
    dash = 3
    # S: dot dot dot
    for _ in range(dots):
        start_period(period_ms=150)
        time.sleep(0.15)
        stop()
        time.sleep(0.15)
    # gap
    time.sleep(0.3)
    # O: dash dash dash
    for _ in range(dash):
        start_period(period_ms=450)
        time.sleep(0.45)
        stop()
        time.sleep(0.15)
    # gap
    time.sleep(0.3)
    # S: dot dot dot
    for _ in range(dots):
        start_period(period_ms=150)
        time.sleep(0.15)
        stop()
        time.sleep(0.15)
    return "SOS pattern played"


def _heartbeat():
    """Two quick pulses like a heartbeat."""
    from led_blink import start_period, stop
    stop()
    for _ in range(2):
        start_period(period_ms=120)
        time.sleep(0.12)
        stop()
        time.sleep(0.12)
    time.sleep(0.6)
    return "Heartbeat pattern played"


def _candle():
    """Random flicker-like toggles for a short period."""
    import random
    from led_blink import start_period, stop
    stop()
    start_time = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start_time) < 3000:
        if random.getrandbits(1):
            start_period(period_ms=40)
            time.sleep_ms(40)
            stop()
        time.sleep_ms(random.randint(30, 120))
    return "Candle flicker played for 3s"


def led_pattern(pattern="sos"):
    """Play a named LED pattern.

    pattern: 'sos', 'heartbeat', 'candle'
    """
    p = str(pattern).lower().strip()
    if p == "sos":
        return _sos()
    if p == "heartbeat":
        return _heartbeat()
    if p == "candle":
        return _candle()
    return "Unknown pattern: {0}".format(p)


TOOLS = {
    "led_pattern": {
        "name": "led_pattern",
        "description": "Play a named LED pattern (sos, heartbeat, candle) on the onboard LED.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "enum": ["sos", "heartbeat", "candle"],
                    "description": "Pattern name to play.",
                }
            },
            "required": ["pattern"],
        },
        "callable": led_pattern,
    }
}
