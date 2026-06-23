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

from app.agent_assistant import recommend
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

    def announce(fault, detail):
        rec = recommend(fault, detail, last_snapshot)
        out = {
            "ts": time.time(),
            "fault": fault,
            "detail": detail,
            "severity": rec.get("severity", "warning"),
            "diagnosis": rec.get("diagnosis", ""),
            "actions": rec.get("actions", []),
            "reasoning": rec.get("reasoning", ""),
            # flattened for the historian field
            "recommendation": rec.get("diagnosis", "") + " | " +
                              "; ".join(rec.get("actions", [])),
        }
        publish_json(client, TOPIC_AGENT, out)
        print("\n" + "=" * 70, flush=True)
        print(f"[AGENT] {out['severity'].upper()}  fault={fault}", flush=True)
        print(f"  why detected: {detail}", flush=True)
        print(f"  diagnosis   : {out['diagnosis']}", flush=True)
        for a in out["actions"]:
            print(f"    - {a}", flush=True)
        print(f"  reasoning   : {out['reasoning']}", flush=True)
        print("=" * 70, flush=True)

    def evaluate_and_announce():
        with lock:
            found = {f for f, _ in detector.evaluate(last_snapshot)}
            details = {f: d for f, d in detector.evaluate(last_snapshot)}
            new = found - active_faults
            cleared = active_faults - found
            for f in new:
                announce(f, details.get(f, ""))
            for f in cleared:
                print(f"[AGENT] cleared: {f}", flush=True)
                # tell downstream (e.g. cloud bridge) the fault is gone
                publish_json(client, TOPIC_AGENT,
                             {"ts": time.time(), "fault": f, "cleared": True})
            active_faults.clear()
            active_faults.update(found)

    def on_message(_c, _u, msg):
        nonlocal last_snapshot
        try:
            payload = json.loads(msg.payload)
            with lock:
                last_snapshot = payload["tags"]
            detector.on_telemetry(payload["tags"])
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
