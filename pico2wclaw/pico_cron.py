"""
pico_cron.py — Lightweight interval scheduler for Pico2WClaw.

Persists jobs in /cron/jobs.txt using the same line-based format as pico_memory
(no JSON, to stay MicroPython-safe). Runs only from the main loop (never from
an ISR or background thread) so urequests/pin access stay safe.
"""

import os
import time

_CRON_DIR = "/cron"
_JOBS_FILE = "/cron/jobs.txt"

_store = None


def set_store(s):
    global _store
    _store = s


def _ensure_dirs():
    try:
        os.listdir(_CRON_DIR)
        return
    except OSError:
        pass
    parts = _CRON_DIR.strip("/").split("/")
    path = ""
    for part in parts:
        path = path + "/" + part if path else "/" + part
        try:
            os.mkdir(path)
        except OSError:
            pass


class CronStore:
    def __init__(self, agent):
        self.agent = agent
        self.jobs = []
        self._next_id = 1
        _ensure_dirs()
        self.load()

    def _parse_line(self, line):
        # id|type|pin|interval_ms|chat_id|enabled|template
        parts = line.split("|", 6)
        if len(parts) < 6:
            return None
        try:
            jid = int(parts[0])
        except Exception:
            return None
        try:
            pin = int(parts[2]) if parts[2].strip() != "" else None
        except Exception:
            pin = None
        try:
            interval = int(parts[3])
        except Exception:
            interval = 1000
        if interval <= 0:
            interval = 1000
        chat_raw = parts[4].strip()
        if chat_raw == "" or chat_raw.lower() == "none":
            chat_id = None
        else:
            try:
                chat_id = int(chat_raw)
            except Exception:
                chat_id = chat_raw
        enabled = parts[5].strip().lower() in ("1", "true", "yes", "on")
        template = parts[6] if len(parts) >= 7 else "{value}"
        job = {
            "id": jid,
            "type": parts[1].strip().lower(),
            "pin": pin,
            "interval_ms": interval,
            "chat_id": chat_id,
            "enabled": enabled,
            "template": template if template != "" else "{value}",
            "last_run": 0,
        }
        return job

    def load(self):
        self.jobs = []
        maxid = 0
        try:
            with open(_JOBS_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    job = self._parse_line(line)
                    if job is not None:
                        self.jobs.append(job)
                        if job["id"] > maxid:
                            maxid = job["id"]
        except OSError:
            pass
        self._next_id = maxid + 1

    def save(self):
        try:
            with open(_JOBS_FILE, "w") as f:
                for job in self.jobs:
                    chat = "" if job["chat_id"] is None else str(job["chat_id"])
                    enabled = "1" if job.get("enabled", True) else "0"
                    pin = "" if job["pin"] is None else str(job["pin"])
                    f.write("{0}|{1}|{2}|{3}|{4}|{5}|{6}\n".format(
                        job["id"], job["type"], pin, job["interval_ms"],
                        chat, enabled, job.get("template", "{value}"),
                    ))
        except OSError as e:
            print("[cron] save error:", e)

    def list_jobs(self):
        return list(self.jobs)

    def add_job(self, jtype, pin, interval_ms, chat_id=None, template=None):
        if chat_id is None:
            try:
                import config
                dci = getattr(config, "CRON_DEFAULT_CHAT_ID", None)
                if dci is not None:
                    chat_id = dci
                else:
                    users = getattr(config, "TELEGRAM_ALLOWED_USERS", None)
                    if users:
                        chat_id = users[0]
            except Exception:
                pass
        if template is None or template == "":
            template = "{value}"
        try:
            interval_ms = int(interval_ms)
        except Exception:
            interval_ms = 1000
        if interval_ms <= 0:
            interval_ms = 1000
        try:
            pin = int(pin) if pin is not None else None
        except Exception:
            pin = None
        job = {
            "id": self._next_id,
            "type": (jtype or "").strip().lower(),
            "pin": pin,
            "interval_ms": interval_ms,
            "chat_id": chat_id,
            "enabled": True,
            "template": template,
            "last_run": 0,
        }
        self._next_id += 1
        self.jobs.append(job)
        self.save()
        return job["id"]

    def remove_job(self, jid):
        for i, job in enumerate(self.jobs):
            if job["id"] == jid:
                del self.jobs[i]
                self.save()
                return True
        return False

    def set_enabled(self, jid, enabled):
        for job in self.jobs:
            if job["id"] == jid:
                job["enabled"] = bool(enabled)
                self.save()
                return True
        return False

    def _read_value(self, job):
        jtype = job["type"]
        if jtype == "gpio":
            from tools import gpio_read
            return gpio_read(job["pin"])
        if jtype == "adc":
            from tools import adc_read
            return adc_read(job["pin"])
        return "unknown type: %s" % jtype

    def run_job(self, job):
        try:
            value = self._read_value(job)
            template = job.get("template") or "{value}"
            msg = template.replace("{value}", str(value))
            msg = msg.replace("{pin}", str(job["pin"]))
            msg = msg.replace("{type}", str(job["type"]))
            if job["chat_id"] is not None and getattr(self.agent, "telegram_send", None):
                try:
                    self.agent.telegram_send(job["chat_id"], msg)
                except Exception as e:
                    print("[cron] send error:", e)
            else:
                print("[cron]", msg)
        except Exception as e:
            print("[cron] job", job["id"], "error:", e)

    def tick(self, now_ms):
        for job in self.jobs:
            if not job.get("enabled", True):
                continue
            last = job.get("last_run", 0)
            if last == 0:
                # Baseline on first tick; first real fire after one interval.
                job["last_run"] = now_ms
                continue
            if time.ticks_diff(now_ms, last) >= job["interval_ms"]:
                job["last_run"] = now_ms
                self.run_job(job)
                # Only one job per tick to bound latency.
                break


# Module-level helpers used by tools.py (lazy dispatch)
def cron_add(type="gpio", pin=0, interval_ms=1000, chat_id=None, message=None):
    if _store is None:
        return "cron unavailable"
    template = message if message else "{value}"
    jid = _store.add_job(type, pin, interval_ms, chat_id, template)
    return "Added cron job #{0}".format(jid)


def cron_list():
    if _store is None:
        return "cron unavailable"
    jobs = _store.list_jobs()
    if not jobs:
        return "No cron jobs."
    lines = []
    for j in jobs:
        lines.append("#{0} {1} pin={2} every {3}ms chat={4} {5}".format(
            j["id"], j["type"], j["pin"], j["interval_ms"],
            j["chat_id"], "ON" if j["enabled"] else "OFF"))
    return "\n".join(lines)


def cron_remove(id=0):
    if _store is None:
        return "cron unavailable"
    if _store.remove_job(int(id)):
        return "Removed job #{0}".format(id)
    return "Job #{0} not found.".format(id)
