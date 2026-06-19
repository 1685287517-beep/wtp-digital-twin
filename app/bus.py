"""Thin MQTT helpers shared by every service."""
import json
import paho.mqtt.client as mqtt

from app.config import MQTT_HOST, MQTT_PORT


def make_client(client_id: str) -> mqtt.Client:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=client_id
    )
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    return client


def publish_json(client: mqtt.Client, topic: str, payload: dict):
    client.publish(topic, json.dumps(payload), qos=0, retain=False)
