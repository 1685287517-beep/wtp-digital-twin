"""Telegram alarm notifier.

Subscribes to the AI assistant's fault events and pushes each new fault — with
its diagnosis and recommended actions — to a Telegram chat, so an operator gets
the alarm on their phone. Sends a short "cleared" note when the fault clears.

Set TG_BOT_TOKEN (from @BotFather) and TG_CHAT_ID in your .env to enable it.
Without them the service just idles, so `docker compose up` never fails.

Run:  python -m app.telegram_notify
"""
import json
import time
import urllib.parse
import urllib.request

from app.bus import make_client
from app.config import TG_BOT_TOKEN, TG_CHAT_ID, TOPIC_AGENT

SEV_ICON = {"critical": "🔴", "warning": "🟠", "info": "🔵"}


def send(text: str):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": TG_CHAT_ID, "text": text, "disable_web_page_preview": "true"}
    ).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=10) as r:
            r.read()
    except Exception as exc:  # noqa: BLE001
        print(f"[tg] send error: {exc}", flush=True)


def format_fault(p: dict) -> str:
    icon = SEV_ICON.get(p.get("severity", ""), "⚠️")
    lines = [f"{icon} PLANT ALARM — {p.get('severity', '').upper()}",
             f"Fault: {p.get('fault', '')}",
             ""]
    if p.get("diagnosis"):
        lines += [f"Diagnosis: {p['diagnosis']}", ""]
    if p.get("actions"):
        lines.append("Recommended actions:")
        lines += [f"• {a}" for a in p["actions"]]
    return "\n".join(lines)


def main():
    if not (TG_BOT_TOKEN and TG_CHAT_ID):
        print("[tg] TG_BOT_TOKEN / TG_CHAT_ID not set — notifier idle. Add them to "
              ".env and restart this service.", flush=True)
        while True:
            time.sleep(60)

    def on_message(_c, _u, msg):
        try:
            p = json.loads(msg.payload)
            if p.get("preliminary"):
                return  # wait for the enriched LLM message; send one good alert
            if p.get("cleared"):
                send(f"✅ CLEARED — {p.get('fault', '')} is back to normal.")
            else:
                send(format_fault(p))
        except Exception as exc:  # noqa: BLE001
            print(f"[tg] msg error: {exc}", flush=True)

    client = make_client("wtp-telegram")
    client.on_message = on_message
    client.subscribe(TOPIC_AGENT, qos=0)
    print("[tg] running; alarms will be pushed to Telegram", flush=True)
    send("🟢 WTP alarm bot connected — you will receive plant alarms here.")
    client.loop_forever()


if __name__ == "__main__":
    main()
