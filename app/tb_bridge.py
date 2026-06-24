"""Bridge: forward local telemetry to ThingsBoard Cloud.

Subscribes to the local MQTT telemetry and republishes it to a ThingsBoard
Cloud device, so the same data shows up on a cloud dashboard while the local
stack (Grafana, HMI) keeps working unchanged.

ThingsBoard device MQTT API:
    host  thingsboard.cloud : 1883
    auth  MQTT username = device Access Token (no password)
    topic v1/devices/me/telemetry
    body  {"ts": <ms>, "values": {tag: value, ...}}

Set TB_TOKEN (the device's access token) in your .env to enable it. Without a
token the bridge just idles, so `docker compose up` never fails.

Run:  python -m app.tb_bridge
"""
import json
import time

import paho.mqtt.client as mqtt

from app.bus import make_client
from app.config import (
    TB_HOST, TB_PORT, TB_TOKEN, TB_PERIOD, TOPIC_TELEMETRY, TOPIC_AGENT,
)

TB_TOPIC = "v1/devices/me/telemetry"


def main():
    if not TB_TOKEN:
        print("[tb] TB_TOKEN not set — bridge idle. Put your ThingsBoard device "
              "token in .env (TB_TOKEN=...) and restart this service.", flush=True)
        while True:
            time.sleep(60)

    # --- connection to ThingsBoard Cloud ---------------------------------
    tb = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="wtp-tb-bridge")
    tb.username_pw_set(TB_TOKEN)            # token as username, no password
    tb.connect(TB_HOST, TB_PORT, keepalive=30)
    tb.loop_start()
    print(f"[tb] forwarding to {TB_HOST}:{TB_PORT} every {TB_PERIOD}s", flush=True)

    last_sent = 0.0
    # current AI fault state — included in EVERY telemetry push so the cloud
    # alarm rule always sees a real fault_active (never a stale/default value)
    fault = {"fault_active": 0, "active_fault": "", "fault_severity": "",
             "fault_recommendation": ""}

    def on_message(_c, _u, msg):
        nonlocal last_sent
        now = time.time()
        try:
            payload = json.loads(msg.payload)
            if msg.topic == TOPIC_AGENT:
                # update the latched fault state and push it immediately
                if payload.get("cleared"):
                    fault.update(fault_active=0, active_fault="", fault_recommendation="")
                else:
                    fault.update(
                        fault_active=1,
                        active_fault=payload.get("fault", ""),
                        fault_severity=payload.get("severity", "warning"),
                        fault_recommendation=(payload.get("diagnosis", "") + " | " +
                                              "; ".join(payload.get("actions", []))),
                    )
                tb.publish(TB_TOPIC, json.dumps({"ts": int(now * 1000), "values": dict(fault)}), qos=1)
                print(f"[tb] forwarded fault to cloud: {fault['active_fault']} "
                      f"(fault_active={fault['fault_active']})", flush=True)
                return

            # high-rate telemetry -> throttle to stay within free-tier limits
            if now - last_sent < TB_PERIOD:
                return
            last_sent = now
            values = dict(payload.get("tags", {}))
            values["fault_active"] = fault["fault_active"]      # always present
            values["active_fault"] = fault["active_fault"]
            tb.publish(TB_TOPIC, json.dumps({"ts": int(payload.get("ts", now) * 1000),
                                             "values": values}), qos=0)
        except Exception as exc:  # noqa: BLE001
            print(f"[tb] forward error: {exc}", flush=True)

    local = make_client("wtp-tb-sub")
    local.on_message = on_message
    local.subscribe([(TOPIC_TELEMETRY, 0), (TOPIC_AGENT, 0)])
    local.loop_forever()


if __name__ == "__main__":
    main()
