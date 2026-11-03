"""
boot.py — Boot script for Pico2WClaw on Raspberry Pi Pico 2 W.
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

    print("\n" + "=" * 90)
    print("  Pico2WClaw booting...")
    print("=" * 90)

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
    try:
        if getattr(agent, "cron", None) is not None:
            print("[boot] cron jobs loaded:", len(agent.cron.list_jobs()))
    except Exception:
        pass

    # Start Telegram polling in a background thread so its HTTP blocking
    # never delays the main loop (serial REPL + timer callbacks).
    if getattr(config, "TELEGRAM_BOT_TOKEN", ""):
        try:
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
            print("[boot] Telegram thread started")
        except (ImportError, OSError) as e:
            print("[boot] Telegram thread unavailable:", e)
            # Fallback: timer-based polling in main loop
            try:
                tg_timer = machine.Timer(-1)
                def _tg_tick(_t):
                    agent._telegram_due = True
                tg_timer.init(period=3000, mode=machine.Timer.PERIODIC, callback=_tg_tick)
                print("[boot] Telegram timer fallback started")
            except Exception as e2:
                print("[boot] Telegram poller failed:", e2)

    agent.serial_loop()


try:
    main()
except Exception as e:
    print("[boot] fatal error:", e)
    import sys
    sys.print_exception(e)
