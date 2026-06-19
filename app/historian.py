"""Entrypoint: subscribe to telemetry + agent topics and write to InfluxDB.

This is the 'historian' — the time-series store of record. Numeric tags become
fields on the `telemetry` measurement; agent advice is stored on `agent_events`.

Run:  python -m app.historian
"""
import json

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from app.bus import make_client
from app.config import (
    INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET,
    TOPIC_TELEMETRY, TOPIC_AGENT,
)


def main():
    influx = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = influx.write_api(write_options=SYNCHRONOUS)

    def write_telemetry(payload):
        ts_ns = int(payload["ts"] * 1e9)
        point = Point("telemetry")
        for name, value in payload["tags"].items():
            if isinstance(value, bool):
                point.field(name, 1.0 if value else 0.0)
            elif isinstance(value, (int, float)):
                point.field(name, float(value))
            else:  # strings (e.g. PLC_state) -> string *field*, never a tag.
                # A tag would join the series key and split every numeric
                # series whenever the state changes; a field keeps them whole.
                point.field(name, str(value))
        point.time(ts_ns)
        write_api.write(bucket=INFLUX_BUCKET, record=point)

    def write_agent(payload):
        point = (
            Point("agent_events")
            .tag("fault", payload.get("fault", "unknown"))
            .tag("severity", payload.get("severity", "info"))
            .field("recommendation", payload.get("recommendation", ""))
            .field("active", 1.0)
        )
        write_api.write(bucket=INFLUX_BUCKET, record=point)

    def on_message(_c, _u, msg):
        try:
            payload = json.loads(msg.payload)
            if msg.topic == TOPIC_TELEMETRY:
                write_telemetry(payload)
            elif msg.topic == TOPIC_AGENT:
                write_agent(payload)
        except Exception as exc:  # noqa: BLE001
            print(f"[historian] write error: {exc}", flush=True)

    client = make_client("wtp-historian")
    client.on_message = on_message
    client.subscribe([(TOPIC_TELEMETRY, 0), (TOPIC_AGENT, 0)])
    print(f"[historian] writing to {INFLUX_URL} bucket={INFLUX_BUCKET}", flush=True)
    client.loop_forever()


if __name__ == "__main__":
    main()
