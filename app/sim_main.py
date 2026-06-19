"""Entrypoint: run the process + PLC scan loop and publish telemetry.

    raw physics  ->  PLC scan (AUTO logic)  ->  apply operator overrides
    (AUTO/MAN per device, from the HMI)  ->  build tag map  ->  apply sensor
    fault  ->  publish to MQTT (unless the infra fault is suppressing publishes)

Operator devices (each AUTO or MAN):
    P101  inlet pump      P102  outlet pump     P201  chemical doser
    V100  inlet valve     V101  outlet valve

Run:  python -m app.sim_main
"""
import json
import time

from app.bus import make_client, publish_json
from app.config import (
    SCAN_TIME, TOPIC_TELEMETRY, TOPIC_CONTROL, TOPIC_CONTROL_OP,
)
from app.faults import FaultManager
from app.plc import PLC
from app.process import ProcessModel, Actuators, NORMAL_INFLUENT_PH

# Influent pH during a PROCESS_PH_EXCURSION fault. Chosen below the dosing
# authority (dose_gain=4.0) so the PID *cannot* fully recover: at full dose the
# tank settles near 1.5+4.0=5.5 pH, ~1.5 below setpoint -> a real excursion.
EXCURSION_PH = 1.5

DEVICES = ["P101", "P102", "V100", "V101", "P201"]
MAN_DOSE = 0.5   # doser output when in MAN and started


def default_ops():
    # mode AUTO/MAN per device; 'on' only matters in MAN
    return {d: {"mode": "AUTO", "on": d in ("V100", "V101", "P201")} for d in DEVICES}


def main():
    proc = ProcessModel()
    plc = PLC()
    faults = FaultManager()
    ops = default_ops()
    act = Actuators()

    client = make_client("wtp-sim")

    def on_message(_c, _u, msg):
        try:
            cmd = json.loads(msg.payload)
            if msg.topic == TOPIC_CONTROL:                       # fault injection
                if faults.set(cmd["fault"], bool(cmd["active"])):
                    print(f"[sim] fault {cmd['fault']} -> {cmd['active']}", flush=True)
            elif msg.topic == TOPIC_CONTROL_OP:                  # operator device cmd
                dev = cmd.get("device")
                if dev in ops:
                    if cmd.get("mode") in ("AUTO", "MAN"):
                        ops[dev]["mode"] = cmd["mode"]
                    if "cmd" in cmd:
                        ops[dev]["on"] = str(cmd["cmd"]).lower() in ("start", "open", "on", "true", "1")
                    print(f"[sim] op {dev} -> {ops[dev]}", flush=True)
        except Exception as exc:  # noqa: BLE001 - demo robustness
            print(f"[sim] bad control msg: {exc}", flush=True)

    client.on_message = on_message
    client.subscribe([(TOPIC_CONTROL, 1), (TOPIC_CONTROL_OP, 1)])
    client.loop_start()

    def resolve(dev, auto_on):
        o = ops[dev]
        return bool(auto_on) if o["mode"] == "AUTO" else bool(o["on"])

    print(f"[sim] running, scan={SCAN_TIME}s, publishing to {TOPIC_TELEMETRY}", flush=True)
    while True:
        # --- equipment / process faults change the physics inputs ---------
        proc.inlet_blocked = faults.active("EQUIP_PUMP_NO_FLOW")
        proc.influent_ph = EXCURSION_PH if faults.active("PROCESS_PH_EXCURSION") else NORMAL_INFLUENT_PH

        # --- advance physics with last scan's effective actuators ---------
        sensors = proc.step(SCAN_TIME, act)

        # --- run one PLC scan to compute AUTO desired commands -----------
        auto, derived = plc.scan(sensors, SCAN_TIME)

        # --- resolve each device against the operator panel --------------
        p101 = resolve("P101", auto.inlet_pump)
        p102 = resolve("P102", auto.outlet_pump)
        v100 = resolve("V100", auto.inlet_pump)    # AUTO valve follows fill
        v101 = resolve("V101", auto.outlet_pump)   # AUTO valve follows discharge
        if ops["P201"]["mode"] == "AUTO":
            dose = auto.dose
        else:
            dose = MAN_DOSE if ops["P201"]["on"] else 0.0

        # effective flow needs pump running AND its valve open
        act = Actuators(inlet_pump=(p101 and v100),
                        outlet_pump=(p102 and v101),
                        dose=dose)

        # --- assemble the full tag map ------------------------------------
        tags = dict(sensors)
        tags.update(derived)
        tags["P101_inlet_cmd"] = p101
        tags["P101_inlet_run_fb"] = p101     # motor 'runs' even if a fault blocks flow
        tags["P102_outlet_cmd"] = p102
        tags["P102_outlet_run_fb"] = p102
        tags["V100_inlet_open"] = v100
        tags["V101_outlet_open"] = v101
        tags["P201_dose_cmd"] = round(dose, 4)
        tags["LIT101_predicted"] = round(proc.level, 4)
        tags["LIT101_level_pct"] = round(proc.level / proc.level_max * 100.0, 1)
        for d in DEVICES:
            tags[f"{d}_mode"] = ops[d]["mode"]

        # --- sensor-layer fault corrupts what we publish -----------------
        tags = faults.apply_sensor_layer(tags)

        payload = {"ts": time.time(), "tags": tags}

        # --- infra fault: stop publishing -> historian/agent see staleness
        if not faults.active("INFRA_MQTT_STALE"):
            publish_json(client, TOPIC_TELEMETRY, payload)

        time.sleep(SCAN_TIME)


if __name__ == "__main__":
    main()
