"""Operator panel CLI: inject or clear a fault by publishing to the control topic.

Usage:
    python -m app.inject_fault EQUIP_PUMP_NO_FLOW on
    python -m app.inject_fault EQUIP_PUMP_NO_FLOW off
    python -m app.inject_fault list
"""
import sys
import time

from app.bus import make_client, publish_json
from app.config import TOPIC_CONTROL
from app.faults import KNOWN_FAULTS


def main(argv):
    if not argv or argv[0] == "list":
        print("Known faults:")
        for f in sorted(KNOWN_FAULTS):
            print("  ", f)
        return

    fault = argv[0]
    active = (len(argv) > 1 and argv[1].lower() in ("on", "true", "1"))
    if fault not in KNOWN_FAULTS:
        print(f"Unknown fault {fault!r}. Use 'list' to see options.")
        sys.exit(1)

    client = make_client("wtp-injector")
    client.loop_start()
    publish_json(client, TOPIC_CONTROL, {"fault": fault, "active": active})
    time.sleep(0.3)   # let the message flush before we exit
    client.loop_stop()
    print(f"sent: {fault} -> {'ON' if active else 'OFF'}")


if __name__ == "__main__":
    main(sys.argv[1:])
