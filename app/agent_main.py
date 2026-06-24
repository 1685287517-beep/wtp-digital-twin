"""Entrypoint: the AI operator assistant loop.

Subscribes to telemetry, runs the deterministic detector, and on a *new* fault
asks the assistant for a recommendation, which it prints and publishes to the
agent topic (the historian stores it; the operator sees it).

A 'staleness' watchdog ticks even when no telemetry arrives, so the infra fault
is caught within the staleness window.

Run:  python -m app.agent_main
"""
import json
import threading
import time

from app.agent_assistant import recommend, playbook, llm_enabled
from app.agent_detector import Detector
from app.bus import make_client, publish_json
from app.config import TOPIC_TELEMETRY, TOPIC_AGENT

POLL = 1.0   # watchdog tick (s)


def main():
    detector = Detector()
    last_snapshot = {}
    active_faults = set()          # faults we have already announced
    lock = threading.Lock()

    client = make_client("wtp-agent")

    def _build(fault, detail, rec, preliminary):
        return {
            "ts": time.time(), "fault": fault, "detail": detail,
            "preliminary": preliminary,
            "severity": rec.get("severity", "warning"),
            "diagnosis": rec.get("diagnosis", ""),
            "actions": rec.get("actions", []),
            "reasoning": rec.get("reasoning", ""),
            "recommendation": rec.get("diagnosis", "") + " | " +
                              "; ".join(rec.get("actions", [])),
        }

    def announce(fault, detail, snapshot):
        # 1) raise the alarm IMMEDIATELY with the offline playbook (no network),
        #    so the HMI horn/LEDs, cloud and operator see it within detection time
        pb = playbook(fault, detail)
        publish_json(client, TOPIC_AGENT, _build(fault, detail, pb, preliminary=llm_enabled()))
        print(f"\n[AGENT] {pb['severity'].upper()}  fault={fault}  (alarm raised)", flush=True)
        # 2) enrich with the LLM (slower); publish the upgraded recommendation
        if llm_enabled():
            rec = recommend(fault, detail, snapshot)
            out = _build(fault, detail, rec, preliminary=False)
            publish_json(client, TOPIC_AGENT, out)
            print(f"[AGENT] {fault} — AI advice ready:", flush=True)
            print(f"  diagnosis : {out['diagnosis']}", flush=True)
            for a in out["actions"]:
                print(f"    - {a}", flush=True)
            print(f"  reasoning : {out['reasoning']}", flush=True)

    def evaluate_and_announce():
        # Detection runs UNDER the lock so the detector's debounce timers aren't
        # raced by the MQTT thread and the watchdog thread calling it at once.
        # The slow part (the Claude call in announce) stays OUTSIDE the lock, so
        # it still can't freeze telemetry processing.
        with lock:
            snap = dict(last_snapshot)
            if not snap:
                return
            results = detector.evaluate(snap)
            found = {f for f, _ in results}
            details = {f: d for f, d in results}
            new = found - active_faults
            cleared = active_faults - found
            active_faults.clear()
            active_faults.update(found)
        # each new fault gets its recommendation in a background thread, so the
        # LLM call (even if slow) never blocks the detection loop
        for f in new:
            threading.Thread(target=announce, args=(f, details.get(f, ""), snap),
                             daemon=True).start()
        for f in cleared:
            print(f"[AGENT] cleared: {f}", flush=True)
            publish_json(client, TOPIC_AGENT, {"ts": time.time(), "fault": f, "cleared": True})

    def on_message(_c, _u, msg):
        nonlocal last_snapshot
        try:
            payload = json.loads(msg.payload)
            with lock:
                last_snapshot = payload["tags"]
                detector.on_telemetry(payload["tags"])   # detector access serialized
            evaluate_and_announce()
        except Exception as exc:  # noqa: BLE001
            print(f"[agent] msg error: {exc}", flush=True)

    client.on_message = on_message
    client.subscribe(TOPIC_TELEMETRY, qos=0)
    client.loop_start()
    print("[agent] running; watching for faults", flush=True)

    # watchdog: keeps evaluating even with no telemetry (catches staleness)
    while True:
        time.sleep(POLL)
        evaluate_and_announce()


if __name__ == "__main__":
    main()
