"""
agent.py — Core agent loop for PycoClaw-Pico.
Implements a simplified OpenClaw-style agent: prompt → LLM → tools → answer.
"""

import json
import time
from machine import Pin, freq

import config
from memory import Memory
from tools import get_tool_defs, call_tool
from display import set_status, show_message, beep_success, beep_error


class Agent:
    def __init__(self):
        self.memory = Memory()
        self.history = []  # in-memory conversation history
        self.running = False
        self._telegram_offset = 0

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
        system = {
            "role": "system",
            "content": config.SYSTEM_PROMPT
            + "\n\nAvailable tools: "
            + ", ".join(get_tool_defs()[t]["function"]["name"] for t in range(len(get_tool_defs())))
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

    # ------------------------------------------------------------------
    # Serial REPL loop
    # ------------------------------------------------------------------
    def serial_loop(self):
        print("=" * 50)
        print(f"  {config.AGENT_NAME} ready.")
        print("  Type a message and press Enter.")
        print("  Commands: /info, /memory, /clear, /tools")
        print("=" * 50)
        self.running = True
        while self.running:
            try:
                user_input = input("> ").strip()
            except KeyboardInterrupt:
                print("\n[agent] shutting down.")
                self.running = False
                break

            if not user_input:
                continue
            if user_input == "/info":
                from tools import device_info
                print(device_info())
                continue
            if user_input == "/memory":
                for s in self.memory.search(user_input, max_results=10):
                    print("  -", s[:100])
                continue
            if user_input == "/clear":
                self.history = []
                self.memory.documents = []
                self.memory.save()
                print("History and memory cleared.")
                continue
            if user_input == "/tools":
                for t in get_tool_defs():
                    print(f"  {t['function']['name']}: {t['function']['description']}")
                continue

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
            resp = urequests.get(url, timeout=10)
            try:
                data = resp.json()
            except Exception:
                data = {}
            resp.close()
        except Exception as e:
            print("[telegram] poll error:", e)
            return

        updates = data.get("result", [])
        for upd in updates:
            upd_id = upd.get("update_id", 0)
            if upd_id:
                self._telegram_offset = upd_id + 1
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
            reply = self.run_turn(text, source="telegram")
            self.telegram_send(chat_id, reply)
