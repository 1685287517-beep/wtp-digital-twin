"""Operator HMI backend — serves the SCADA mimic page and bridges it to MQTT.

    browser  --(poll)-->  GET /api/state    latest tags + recent AI alarms
    browser  --(click)--> POST /api/control  device cmd -> MQTT op topic
    browser  --(click)--> POST /api/fault    inject/clear a fault -> MQTT

It keeps the latest telemetry and a short alarm history in memory, fed by MQTT.

Run:  uvicorn app.hmi:app --host 0.0.0.0 --port 8090
"""
import json
import os
import threading

import paho.mqtt.client as mqtt
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse

from app.config import (
    MQTT_HOST, MQTT_PORT, TOPIC_TELEMETRY, TOPIC_AGENT,
    TOPIC_CONTROL_OP, TOPIC_CONTROL,
)

app = FastAPI()
HERE = os.path.dirname(os.path.abspath(__file__))

_state = {"tags": {}, "ts": 0}
_alarms = []          # most-recent-first
_lock = threading.Lock()

mc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="wtp-hmi")


def _on_message(_c, _u, msg):
    global _state
    try:
        payload = json.loads(msg.payload)
        if msg.topic == TOPIC_TELEMETRY:
            with _lock:
                _state = payload
        elif msg.topic == TOPIC_AGENT:
            with _lock:
                _alarms.insert(0, payload)
                del _alarms[30:]
    except Exception:  # noqa: BLE001
        pass


mc.on_message = _on_message
mc.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
mc.subscribe([(TOPIC_TELEMETRY, 0), (TOPIC_AGENT, 0)])
mc.loop_start()


_NO_CACHE = {"Cache-Control": "no-store, max-age=0"}


@app.get("/")
def index():
    # no-cache so HMI tweaks always show on refresh (we live-edit the page)
    return FileResponse(os.path.join(HERE, "static", "index.html"), headers=_NO_CACHE)


@app.get("/api/state")
def state():
    with _lock:
        return {"tags": _state.get("tags", {}), "ts": _state.get("ts", 0),
                "alarms": list(_alarms)}


@app.post("/api/control")
async def control(req: Request):
    body = await req.json()
    mc.publish(TOPIC_CONTROL_OP, json.dumps(body))
    return {"ok": True}


@app.post("/api/fault")
async def fault(req: Request):
    body = await req.json()
    mc.publish(TOPIC_CONTROL, json.dumps(body))
    return {"ok": True}
