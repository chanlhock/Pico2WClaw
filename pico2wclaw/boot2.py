"""
boot.py — Boot script for Pico2WClaw on Raspberry Pi Pico 2 W.
Runs on power-up / reset. Connects to WiFi and starts the agent serial loop.
"""

import os
import time
import machine
from machine import Pin

import config

# Capture the on-device config.py text so /exit can rewrite watchdog flags.

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
    # ---- Watchdog ----
    def _wdt_feed_timer(t):
        if config.WDT is not None and config.WATCHDOG_ENABLED:
            try:
                config.WDT.feed()
            except Exception:
                pass

    if config.WATCHDOG_ENABLED:
        config.WDT = machine.WDT(timeout=config.WATCHDOG_TIMEOUT_MS)
        _wdt_timer = machine.Timer(-1)
        config._wdt_timer = _wdt_timer
        _wdt_timer.init(period=config.WATCHDOG_FEED_INTERVAL_MS, mode=machine.Timer.PERIODIC, callback=_wdt_feed_timer)

    # Record reset cause as early as possible
    config._wdt_reset_cause = machine.reset_cause()
    # ---- End watchdog ----
    # ---- Watchdog logging ----

    def _log_wdt_reset():
        """Log a WDT overflow reset to /wdt.log using UTC+8 local time."""
        if config._wdt_reset_cause != machine.WDT_RESET:
            return
        try:
            # Only log if we have a usable NTP time
            if time.time() <= 0:
                return
        except Exception:
            return
        try:
            # MicroPython time.time() is UTC epoch; localtime() gives UTC
            t = time.localtime()
            # Convert to UTC+8
            t8 = (t[0], t[1], t[2],
                  (t[3] + 8) % 24,
                  t[4], t[5], t[6], t[7], t[8])
            stamp = time.strftime("%Y-%m-%d %H:%M:%S+0800", t8)
        except Exception:
            stamp = "unknown-time"
        entry = "WDT_RESET|{0}\n".format(stamp)
        try:
            with open(config.WATCHDOG_LOG_FILE, "r") as f:
                lines = f.readlines()
        except Exception:
            lines = []
        lines.append(entry)
        try:
            max_lines = config.WATCHDOG_LOG_MAX_LINES
        except Exception:
            max_lines = 20
        if max_lines:
            lines = lines[-max_lines:]
        try:
            with open(config.WATCHDOG_LOG_FILE, "w") as f:
                f.write("".join(lines))
        except Exception as e:
            print("[wdt] log write failed:", e)

    config._wdt_reset_cause = machine.reset_cause()
    # ---- End watchdog logging ----

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

    # Log a WDT reset if this boot was caused by the watchdog
    _log_wdt_reset()

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
            agent._telegram_alive = True
            def _tg_worker():
                try:
                    while getattr(agent, "_telegram_running", True):
                        try:
                            had_work = agent.telegram_loop()
                            if had_work:
                                print("> ", end="")
                        except Exception as e:
                            print("[telegram] thread error:", e)
                        time.sleep(1)
                finally:
                    agent._telegram_alive = False
            _thread.start_new_thread(_tg_worker, ())
            print("[boot] Telegram thread started")
        except (ImportError, OSError) as e:
            print("[boot] Telegram thread unavailable:", e)
            # Fallback: timer-based polling in main loop
            try:
                tg_timer = machine.Timer(-1)
                agent._tg_timer = tg_timer
                def _tg_tick(_t):
                    if getattr(agent, "_telegram_running", True):
                        agent._telegram_due = True
                tg_timer.init(period=3000, mode=machine.Timer.PERIODIC, callback=_tg_tick)
                print("[boot] Telegram timer fallback started")
            except Exception as e2:
                print("[boot] Telegram poller failed:", e2)

    agent.serial_loop()
    agent.stop()
    # Wait briefly for the Telegram worker thread to actually exit.
    for _ in range(80):
        if not getattr(agent, "_telegram_alive", False):
            break
        time.sleep(0.1)
    print("[agent] stopped.")


try:
    main()
except Exception as e:
    print("[boot] fatal error:", e)
    import sys
    sys.print_exception(e)
