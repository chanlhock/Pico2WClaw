"""
agent.py — Core agent loop for Pico2WClaw.
Implements a simplified OpenClaw-style agent: prompt → LLM → tools → answer.
"""

import json
import sys
import time
from machine import Pin, freq

import config
from pico_memory import Memory
from tools import get_tool_defs, call_tool
from display import set_status, show_message, beep_success, beep_error


class Agent:
    def __init__(self):
        self.memory = Memory()
        self.history = []  # in-memory conversation history
        self.running = False
        self._telegram_offset = 0
        # Persist offset across reboots so stale updates (e.g. /exit) are
        # not re-processed after a restart.
        try:
            with open("/telegram_offset.txt", "r") as f:
                self._telegram_offset = int(f.read().strip() or 0)
        except Exception:
            self._telegram_offset = 0
        self._telegram_due = False
        self._prompt_printed = True  # shared with telegram_loop for prompt restore
        self._skill_instrs = []
        self._skill_namespaces = {}
        # Shutdown coordination (used by /exit)
        self._telegram_running = True
        self._telegram_alive = False
        self._tg_timer = None
        try:
            from skills_loader import load_skills, get_skill_namespaces
            _extra_tools, self._skill_instrs = load_skills()
            if _extra_tools:
                from tools import merge_skill_tools
                merge_skill_tools(_extra_tools)
            self._skill_namespaces = get_skill_namespaces()
        except Exception as e:
            print("[skills] init failed:", e)

        # Cron scheduler (interval-based monitoring -> Telegram)
        self.cron = None
        self._cron_last_tick = time.ticks_ms()
        try:
            from pico_cron import CronStore, set_store
            self.cron = CronStore(self)
            set_store(self.cron)
        except Exception as e:
            print("[cron] init failed:", e)

    # ------------------------------------------------------------------
    # LLM API client (OpenAI-compatible)
    # ------------------------------------------------------------------
    def _call_llm(self, messages, tools=None, stream=False):
        import urequests

        url = config.LLM_BASE_URL.rstrip("/") + "/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + config.LLM_API_KEY,
        }
        payload = {
            "model": config.LLM_MODEL,
            "messages": messages,
            "max_tokens": config.MAX_RESPONSE_TOKENS,
            "temperature": 0.7,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        print("[agent] LLM request ->", url)
        try:
            resp = urequests.post(url, headers=headers, json=payload, timeout=30)
            try:
                data = resp.json()
            except Exception:
                data = {"choices": [{"message": {"content": f"LLM error: HTTP {resp.status_code} — {resp.text[:200]}"}}]}
            resp.close()
            return data
        except Exception as e:
            print("[agent] LLM error:", e)
            if "YOUR_API_KEY" in config.LLM_API_KEY:
                return {"choices": [{"message": {"content": "Error: LLM_API_KEY is not set in config.py. Edit config.py and add your real API key."}}]}
            return None

    # ------------------------------------------------------------------
    # Memory-augmented context builder
    # ------------------------------------------------------------------
    def _build_messages(self, user_message):
        # 1. System prompt
        skill_block = ""
        if self._skill_instrs:
            skill_block = "\n\n[Loaded skills]\n" + "\n".join(self._skill_instrs)
        system = {
            "role": "system",
            "content": config.SYSTEM_PROMPT
            + "\n\nAvailable tools: "
            + ", ".join(get_tool_defs()[t]["function"]["name"] for t in range(len(get_tool_defs())))
            + skill_block
            + "\nUse tools when the user asks to interact with hardware, sensors, or code.",
        }

        # 2. Memory snippets
        snippets = self.memory.search(
            user_message,
            max_results=config.MEMORY_MAX_SNIPPETS,
            max_chars=config.MEMORY_MAX_CHARS,
        )
        memory_block = ""
        if snippets:
            memory_block = "\n\n[Relevant memory]\n" + "\n".join(snippets)

        # 3. Recent history
        recent = self.history[-10:] if len(self.history) > 10 else self.history[:]

        messages = [system]
        for turn in recent:
            messages.append(turn)
        messages.append(
            {"role": "user", "content": user_message + memory_block}
        )
        return messages

    # ------------------------------------------------------------------
    # Single agent turn (handles recursive tool calling)
    # ------------------------------------------------------------------
    def run_turn(self, user_message, source="serial"):
        print(f"[agent] turn from {source}: {user_message[:60]}...")
        self.memory.add("user", user_message)
        self.history.append({"role": "user", "content": user_message})
        set_status("thinking")

        tools = get_tool_defs()
        messages = self._build_messages(user_message)

        rounds = 0
        final_answer = ""

        while rounds < config.TOOL_CALL_MAX_ROUNDS:
            rounds += 1
            data = self._call_llm(messages, tools=tools)
            if not data or "choices" not in data:
                final_answer = "Error: no response from LLM."
                set_status("llm_fail", beep_type="error")
                break

            choice = data["choices"][0]
            msg = choice.get("message", {})
            role = msg.get("role", "assistant")
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls") or []

            # Record assistant message
            assistant_msg = {"role": role, "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            if not tool_calls:
                # Final answer
                final_answer = content or "(no content)"
                # If the model returned nothing, retry once before giving up
                if not content and rounds == 1:
                    messages.append({"role": "user", "content": "(Please provide a concise answer.)"})
                    continue
                beep_success()
                set_status("llm_ok")
                break

            # Execute each tool call
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args_raw = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_raw)
                except Exception:
                    args = {}

                set_status("tool")
                print(f"[agent] tool call: {name}({args})")
                result = call_tool(name, args)
                print(f"[agent] tool result: {result[:80]}...")

                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": result,
                }
                messages.append(tool_msg)

        # Persist and return
        self.memory.add("assistant", final_answer)
        self.history.append({"role": "assistant", "content": final_answer})
        self.memory.save()
        set_status("ready", beep_type="click")
        return final_answer

    def stop(self):
        """Signal the agent (main loop + Telegram worker) to stop."""
        self.running = False
        self._telegram_running = False
        t = getattr(self, "_tg_timer", None)
        if t is not None:
            try:
                t.deinit()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Serial REPL loop (short-blocking input — input() blocks the main
    # thread and prevents hardware timer callbacks from firing on time,
    # which stretches LED blink periods and causes spikes.)
    # ------------------------------------------------------------------
    def serial_loop(self):
        print("=" * 90)
        print(f"  {config.AGENT_NAME} ready.")
        print("  Type a message and press Enter.")
        print("  Commands: /info, /memory, /clear, /tools, /help, /cron, /exit, /skills, /skill_read <name>")
        print("=" * 90)
        self.running = True

        # Use a short blocking timeout. Zero-timeout reads are unreliable
        # on some MicroPython builds and can return None for real
        # keystrokes/newlines. A 20 ms timeout keeps the loop responsive
        # enough for timer callbacks to stay on schedule.
        # Non-blocking stdin wait so the main loop (cron tick, Telegram
        # fallback) keeps running even when no key is pressed. MicroPython's
        # sys.stdin.settimeout() is not reliably honored on all ports, which
        # previously starved the loop and prevented cron from firing on idle.
        _stdin_poller = None
        try:
            import uselect
            _stdin_poller = uselect.poll()
            _stdin_poller.register(sys.stdin, uselect.POLLIN)
        except Exception:
            _stdin_poller = None

        _line = ""
        print("> ", end="")
        _last_char_ms = time.ticks_ms()
        while self.running:
            # Cron tick (main thread only; gated to avoid per-iteration cost)
            try:
                import config as _cfg
                if self.cron is not None and getattr(_cfg, "CRON_ENABLED", False):
                    now_ms = time.ticks_ms()
                    if time.ticks_diff(now_ms, self._cron_last_tick) >= getattr(_cfg, "CRON_TICK_MS", 1000):
                        self._cron_last_tick = now_ms
                        self.cron.tick(now_ms)
            except Exception as e:
                print("[cron] tick error:", e)

            # Telegram check (timer fallback path)
            if self._telegram_due:
                self._telegram_due = False
                self._prompt_printed = False
                try:
                    self.telegram_loop()
                except Exception as e:
                    print("[agent] telegram loop error:", e)

            # If Telegram output ran and the user isn't typing, restore the prompt.
            if not _line and not self._prompt_printed:
                print("> ", end="")
                self._prompt_printed = True

            # Short-blocking character read
            ch = None
            try:
                if _stdin_poller is not None:
                    if _stdin_poller.poll(50):
                        ch = sys.stdin.read(1)
                        if ch == "":
                            ch = None
                else:
                    # Fallback for builds without uselect (status quo).
                    try:
                        sys.stdin.settimeout(0.02)
                    except AttributeError:
                        try:
                            sys.stdin.buffer.settimeout(0.02)
                        except Exception:
                            pass
                    ch = sys.stdin.read(1)
                    if ch == "":
                        ch = None
            except (EOFError, OSError):
                ch = None
            except Exception:
                ch = None

            if ch is None:
                # No character this pass. If the user stopped typing and
                # we have an unfinished line, process it so we don't hang
                # waiting for a newline that this build may never deliver.
                if _line and time.ticks_diff(time.ticks_ms(), _last_char_ms) > 300:
                    user_input = _line.strip()
                    _line = ""
                    self._process_serial_input(user_input)
                    print("> ", end="")
                    self._prompt_printed = True
                time.sleep_ms(5)
                continue

            _last_char_ms = time.ticks_ms()

            if ch in ("\r", "\n"):
                print()
                user_input = _line.strip()
                _line = ""
                if not user_input:
                    print("> ", end="")
                    self._prompt_printed = True
                    continue
                self._process_serial_input(user_input)
                print("> ", end="")
                self._prompt_printed = True

            elif ch == "\x08" or ch == "\x7f":  # backspace
                if _line:
                    _line = _line[:-1]
                    print("\b \b", end="")
            elif ch == "\x03":  # Ctrl+C
                print("\n[agent] shutting down.")
                self.running = False
                break
            else:
                _line += ch
                self._prompt_printed = False
                print(ch, end="")

    def _process_serial_input(self, user_input):
        """Process a completed serial CLI command."""
        try:
            if user_input == "/info":
                from tools import device_info
                print(device_info())
                return
            if user_input == "/help":
                print(
                    "Commands:\n"
                    "  /info   - hardware info (CPU, RAM, flash, temp, WiFi, MicroPython)\n"
                    "  /tools  - list available tools\n"
                    "  /memory - search memory\n"
                    "  /clear  - wipe history and memory\n"
                    "  /skills - list loaded skills\n"
                    "  /skill_read <name> - read a skill's instructions\n"
                    "  /cron   - manage cron jobs (list/add/del/on/off)\n"
                    "  /exit   - stop the agent\n"
                    "  /help   - show this help\n"
                    "Or type a question/request and press Enter to chat with the agent."
                )
                return
            if user_input == "/exit":
                print("[agent] stopping...")
                self.stop()
                return
            if user_input == "/skills":
                names = sorted(self._skill_namespaces.keys())
                if not names:
                    print("No skills loaded.")
                    return
                for name in names:
                    ns = self._skill_namespaces[name]
                    instr = ns.get("SKILL_INSTR", "(no instructions)")
                    tools = ns.get("TOOLS", {})
                    tool_names = ", ".join(tools.keys()) if tools else "no tools"
                    print("- {0}: {1} (tools: {2})".format(name, instr, tool_names))
                return
            if user_input.startswith("/skill_read "):
                name = user_input[len("/skill_read "):].strip()
                ns = self._skill_namespaces.get(name)
                if not ns:
                    print("Skill '{0}' not found.".format(name))
                    return
                instr = ns.get("SKILL_INSTR", "(no instructions)")
                print("[{0}]\n{1}".format(name, instr))
                return
            if user_input == "/memory":
                for s in self.memory.search(user_input, max_results=10):
                    print("  -", s[:100])
                return
            if user_input == "/clear":
                self.history = []
                self.memory.documents = []
                self.memory.save()
                print("History and memory cleared.")
                return
            if user_input == "/tools":
                for t in get_tool_defs():
                    print(
                        f"  {t['function']['name']}: {t['function']['description']}"
                    )
                return
            if user_input == "/cron" or user_input == "/cron list":
                if self.cron is None:
                    print("Cron unavailable.")
                    return
                jobs = self.cron.list_jobs()
                if not jobs:
                    print("No cron jobs.")
                    return
                for j in jobs:
                    print("  #{0} {1} pin={2} every {3}ms chat={4} {5}".format(
                        j["id"], j["type"], j["pin"], j["interval_ms"],
                        j["chat_id"], "ON" if j["enabled"] else "OFF"))
                return
            if user_input.startswith("/cron add "):
                if self.cron is None:
                    print("Cron unavailable.")
                    return
                parts = user_input[len("/cron add "):].split()
                if len(parts) < 3:
                    print("Usage: /cron add <gpio|adc> <pin> <interval_ms> [chat_id] [message...]")
                    return
                jtype = parts[0]
                try:
                    pin = int(parts[1])
                    interval = int(parts[2])
                except ValueError:
                    print("pin and interval must be integers")
                    return
                chat_id = None
                msg_parts = parts[3:]
                if msg_parts:
                    try:
                        chat_id = int(msg_parts[0])
                        msg_parts = msg_parts[1:]
                    except ValueError:
                        pass
                template = " ".join(msg_parts) if msg_parts else "{value}"
                jid = self.cron.add_job(jtype, pin, interval, chat_id, template)
                print("Added cron job #{0}".format(jid))
                return
            if user_input.startswith("/cron del "):
                if self.cron is None:
                    print("Cron unavailable.")
                    return
                try:
                    jid = int(user_input[len("/cron del "):].strip())
                except ValueError:
                    print("Usage: /cron del <id>")
                    return
                if self.cron.remove_job(jid):
                    print("Removed job #{0}".format(jid))
                else:
                    print("Job #{0} not found.".format(jid))
                return
            if user_input.startswith("/cron on ") or user_input.startswith("/cron off "):
                if self.cron is None:
                    print("Cron unavailable.")
                    return
                on = user_input.startswith("/cron on ")
                try:
                    tail = user_input[9:].strip() if on else user_input[10:].strip()
                    jid = int(tail)
                except ValueError:
                    print("Usage: /cron on|off <id>")
                    return
                if self.cron.set_enabled(jid, on):
                    print("Job #{0} {1}".format(jid, "enabled" if on else "disabled"))
                else:
                    print("Job #{0} not found.".format(jid))
                return
        except Exception as e:
            import sys as _sys
            _sys.print_exception(e)
            return

        reply = self.run_turn(user_input, source="serial")
        print(f"\n{config.AGENT_NAME}: {reply}\n")

    # ------------------------------------------------------------------
    # Telegram Bot polling loop (optional)
    # ------------------------------------------------------------------
    def telegram_send(self, chat_id, text):
        """Send a text message to a Telegram chat."""
        import urequests
        url = "https://api.telegram.org/bot%s/sendMessage" % config.TELEGRAM_BOT_TOKEN
        payload = {"chat_id": chat_id, "text": text}
        try:
            resp = urequests.post(url, json=payload, timeout=15)
            resp.close()
            return True
        except Exception as e:
            print("[telegram] send error:", e)
            return False

    def telegram_loop(self):
        """Poll Telegram for new messages and process them."""
        if not config.TELEGRAM_BOT_TOKEN:
            return
        import urequests
        url = "https://api.telegram.org/bot%s/getUpdates?offset=%s&timeout=5" % (
            config.TELEGRAM_BOT_TOKEN, self._telegram_offset
        )
        try:
            resp = urequests.get(url, timeout=2)
            try:
                data = resp.json()
            except Exception:
                data = {}
            resp.close()
        except Exception as e:
            # Suppress expected network timeout noise; show other errors
            try:
                import errno
                if isinstance(e, OSError) and e.args and e.args[0] in (errno.ETIMEDOUT, errno.ECONNRESET, errno.EHOSTUNREACH):
                    return
            except Exception:
                pass
            print("[telegram] poll error:", e)
            self._prompt_printed = False
            return

        updates = data.get("result", [])
        processed_any = False
        for upd in updates:
            upd_id = upd.get("update_id", 0)
            if upd_id:
                self._telegram_offset = upd_id + 1
                try:
                    with open("/telegram_offset.txt", "w") as f:
                        f.write(str(self._telegram_offset))
                except Exception:
                    pass
            msg = upd.get("message") or upd.get("channel_post")
            if not msg:
                continue
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text", "")
            if not text or not chat_id:
                continue
            if config.TELEGRAM_ALLOWED_USERS and chat_id not in config.TELEGRAM_ALLOWED_USERS:
                print("[telegram] ignored unauthorized chat:", chat_id)
                continue

            print("[telegram] message from", chat_id, ":", text[:60])
            processed_any = True
            try:
                if text == "/info":
                    from tools import device_info
                    reply = device_info()
                elif text == "/help":
                    reply = (
                        "Commands:\n"
                        "  /info   - hardware info (CPU, RAM, flash, temp, WiFi, MicroPython)\n"
                        "  /tools  - list available tools\n"
                        "  /memory - search memory\n"
                        "  /clear  - wipe history and memory\n"
                        "  /skills - list loaded skills\n"
                        "  /skill_read <name> - read a skill's instructions\n"
                        "  /cron   - manage cron jobs (list/add/del/on/off)\n"
                        "  /exit   - stop the agent\n"
                        "  /help   - show this help\n"
                        "Or send a question/request and I'll process it."
                    )
                elif text == "/tools":
                    from tools import get_tool_defs
                    lines = []
                    for t in get_tool_defs():
                        lines.append(f"{t['function']['name']}: {t['function']['description']}")
                    reply = "\n".join(lines)
                elif text == "/cron" or text == "/cron list":
                    if self.cron is None:
                        reply = "Cron unavailable."
                    else:
                        jobs = self.cron.list_jobs()
                        if not jobs:
                            reply = "No cron jobs."
                        else:
                            lines = []
                            for j in jobs:
                                lines.append("#{0} {1} pin={2} every {3}ms chat={4} {5}".format(
                                    j["id"], j["type"], j["pin"], j["interval_ms"],
                                    j["chat_id"], "ON" if j["enabled"] else "OFF"))
                            reply = "\n".join(lines)
                elif text.startswith("/cron add "):
                    if self.cron is None:
                        reply = "Cron unavailable."
                    else:
                        parts = text[len("/cron add "):].split()
                        if len(parts) < 3:
                            reply = "Usage: /cron add <gpio|adc> <pin> <interval_ms> [chat_id] [message...]"
                        else:
                            try:
                                pin = int(parts[1])
                                interval = int(parts[2])
                            except ValueError:
                                reply = "pin and interval must be integers"
                                parts = []
                            if parts:
                                jtype = parts[0]
                                chat_id = None
                                msg_parts = parts[3:]
                                if msg_parts:
                                    try:
                                        chat_id = int(msg_parts[0])
                                        msg_parts = msg_parts[1:]
                                    except ValueError:
                                        pass
                                template = " ".join(msg_parts) if msg_parts else "{value}"
                                jid = self.cron.add_job(jtype, pin, interval, chat_id, template)
                                reply = "Added cron job #{0}".format(jid)
                elif text.startswith("/cron del "):
                    if self.cron is None:
                        reply = "Cron unavailable."
                    else:
                        try:
                            jid = int(text[len("/cron del "):].strip())
                            if self.cron.remove_job(jid):
                                reply = "Removed job #{0}".format(jid)
                            else:
                                reply = "Job #{0} not found.".format(jid)
                        except ValueError:
                            reply = "Usage: /cron del <id>"
                elif text.startswith("/cron on ") or text.startswith("/cron off "):
                    if self.cron is None:
                        reply = "Cron unavailable."
                    else:
                        on = text.startswith("/cron on ")
                        try:
                            tail = text[9:].strip() if on else text[10:].strip()
                            jid = int(tail)
                            if self.cron.set_enabled(jid, on):
                                reply = "Job #{0} {1}".format(jid, "enabled" if on else "disabled")
                            else:
                                reply = "Job #{0} not found.".format(jid)
                        except ValueError:
                            reply = "Usage: /cron on|off <id>"
                elif text == "/exit":
                    self.stop()
                    reply = "Stopping agent."
                elif text == "/memory":
                    snippets = self.memory.search(text, max_results=10)
                    reply = "\n".join(f"- {s[:100]}" for s in snippets) if snippets else "(memory empty)"
                elif text == "/skills":
                    names = sorted(self._skill_namespaces.keys())
                    if not names:
                        reply = "No skills loaded."
                    else:
                        lines = []
                        for name in names:
                            ns = self._skill_namespaces[name]
                            instr = ns.get("SKILL_INSTR", "(no instructions)")
                            tools = ns.get("TOOLS", {})
                            tool_names = ", ".join(tools.keys()) if tools else "no tools"
                            lines.append("- {0}: {1} (tools: {2})".format(name, instr, tool_names))
                        reply = "\n".join(lines)
                elif text.startswith("/skill_read "):
                    name = text[len("/skill_read "):].strip()
                    ns = self._skill_namespaces.get(name)
                    if not ns:
                        reply = "Skill '{0}' not found.".format(name)
                    else:
                        instr = ns.get("SKILL_INSTR", "(no instructions)")
                        reply = "[{0}]\n{1}".format(name, instr)
                elif text == "/clear":
                    self.history = []
                    self.memory.documents = []
                    self.memory.save()
                    reply = "History and memory cleared."
                else:
                    reply = self.run_turn(text, source="telegram")
                self.telegram_send(chat_id, reply)
            except Exception as e:
                self._prompt_printed = False
                print("[telegram] handler error:", e)
                try:
                    self.telegram_send(chat_id, "Error: %s" % e)
                except Exception:
                    pass
        return processed_any
