"""
boot.py — Boot script for PycoClaw-Pico on Raspberry Pi Pico 2 W.
Runs on power-up / reset. Connects to WiFi and starts the agent serial loop.
"""

import time
import machine
from machine import Pin

import config

# ------------------------------------------------------------------
# WiFi connection
# ------------------------------------------------------------------
def connect_wifi(ssid, password, timeout=20):
    import network
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        print("[wifi] already connected:", wlan.ifconfig())
        return wlan

    print(f"[wifi] connecting to {ssid} ...")
    wlan.connect(ssid, password)

    for i in range(timeout):
        if wlan.isconnected():
            print("[wifi] connected:", wlan.ifconfig())
            return wlan
        time.sleep(1)
        print(f"[wifi] waiting... ({i+1}/{timeout})")

    print("[wifi] FAILED to connect")
    return wlan


# ------------------------------------------------------------------
# Main entry
# ------------------------------------------------------------------
def main():
    # Onboard LED (GPIO25 on Pico 2 W)
    led = Pin("LED", Pin.OUT)
    led.on()

    # Initialise display + buzzer (non-fatal if missing)
    from display import boot_splash, set_status
    boot_splash()

    print("\n" + "=" * 50)
    print("  PycoClaw-Pico booting...")
    print("=" * 50)

    wlan = connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD)

    if not wlan.isconnected():
        print("[boot] WiFi failed. Serial mode only (no LLM).")
        set_status("wifi_fail", beep_type="error")
    else:
        set_status("wifi_ok", beep_type="success")
        # Sync time via NTP (best-effort, ignore failure)
        try:
            import ntptime
            ntptime.settime()
            print("[boot] time synced via NTP")
        except Exception as e:
            print("[boot] NTP skipped:", e)

    led.off()

    # Start agent
    from agent import Agent
    agent = Agent()
    set_status("ready", beep_type="click")

    # Start Telegram polling (optional, every 3 s)
    if getattr(config, "TELEGRAM_BOT_TOKEN", ""):
        try:
            tg_timer = machine.Timer(-1)
            tg_timer.init(period=3000, mode=machine.Timer.PERIODIC, callback=lambda t: agent.telegram_loop())
            print("[boot] Telegram polling started")
        except Exception as e:
            print("[boot] Telegram poller failed:", e)

    agent.serial_loop()


try:
    main()
except Exception as e:
    print("[boot] fatal error:", e)
    import sys
    sys.print_exception(e)
