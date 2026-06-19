"""Headless end-to-end demo — no broker, no database, no Docker required.

Wires the twin + PLC + detector + assistant in ONE process and injects each of
the four faults in turn, printing the alarm and the AI recommendation. Use it to
see the whole pipeline work in seconds, and as a fallback if Docker misbehaves
on demo day.

    python -m app.demo_local            # real-time, ~8 s per fault
    python -m app.demo_local 5          # hold each fault 5 s
"""
import sys
import time

from app.process import ProcessModel, Actuators, NORMAL_INFLUENT_PH
from app.plc import PLC
from app.faults import FaultManager
from app.agent_detector import Detector
from app.agent_assistant import recommend
from app.sim_main import EXCURSION_PH

DT = 0.2  # fast scan so the demo moves quickly


def build_tags(sensors, act, level):
    tags = dict(sensors)
    tags["P101_inlet_cmd"] = act.inlet_pump
    tags["P101_inlet_run_fb"] = act.inlet_pump
    tags["P102_outlet_cmd"] = act.outlet_pump
    tags["P102_outlet_run_fb"] = act.outlet_pump
    tags["P201_dose_cmd"] = round(act.dose, 3)
    tags["LIT101_predicted"] = round(level, 4)
    return tags


def print_recommendation(fault, detail, snapshot):
    rec = recommend(fault, detail, snapshot)
    print("\n" + "=" * 72)
    print(f"  ALARM  [{rec.get('severity', '?').upper()}]  {fault}")
    print(f"  detected : {detail}")
    print(f"  diagnosis: {rec.get('diagnosis', '')}")
    for a in rec.get("actions", []):
        print(f"     - {a}")
    print(f"  reasoning: {rec.get('reasoning', '')}")
    print("=" * 72 + "\n")


def main(hold=8.0):
    proc, plc, faults, det = ProcessModel(), PLC(), FaultManager(), Detector()
    act = Actuators()
    announced = set()

    # script: (start_time_s, fault, on/off)
    sequence = [
        (3,  "EQUIP_PUMP_NO_FLOW", True),  (3 + hold,  "EQUIP_PUMP_NO_FLOW", False),
        (3 + hold + 2, "PROCESS_PH_EXCURSION", True), (3 + 2 * hold + 2, "PROCESS_PH_EXCURSION", False),
        (3 + 2 * hold + 4, "SENSOR_LEVEL_STUCK", True), (3 + 3 * hold + 4, "SENSOR_LEVEL_STUCK", False),
        (3 + 3 * hold + 6, "INFRA_MQTT_STALE", True), (3 + 4 * hold + 6, "INFRA_MQTT_STALE", False),
    ]
    end = 3 + 4 * hold + 9
    t0 = time.time()
    last_beat = 0

    print(f"[demo] running headless, DT={DT}s, hold={hold}s/fault. Ctrl-C to stop.\n")
    while True:
        elapsed = time.time() - t0
        if elapsed > end:
            break

        # fire scheduled fault toggles
        while sequence and elapsed >= sequence[0][0]:
            _, f, on = sequence.pop(0)
            faults.set(f, on)
            print(f"\n>>> t={elapsed:5.1f}s  INJECT {f} -> {'ON' if on else 'OFF'}")

        # physics inputs affected by equip/process faults
        proc.inlet_blocked = faults.active("EQUIP_PUMP_NO_FLOW")
        proc.influent_ph = EXCURSION_PH if faults.active("PROCESS_PH_EXCURSION") else NORMAL_INFLUENT_PH

        sensors = proc.step(DT, act)
        act, derived = plc.scan(sensors, DT)
        tags = build_tags(sensors, act, proc.level)
        tags.update(derived)
        tags = faults.apply_sensor_layer(tags)

        # the infra fault stops telemetry reaching the detector
        if not faults.active("INFRA_MQTT_STALE"):
            det.on_telemetry(tags)

        current = {f for f, _ in det.evaluate(tags)}
        details = {f: d for f, d in det.evaluate(tags)}
        for f in current - announced:
            print_recommendation(f, details.get(f, ""), tags)
        for f in announced - current:
            print(f"    (cleared: {f})")
        announced = current

        # heartbeat once per second
        if int(elapsed) != last_beat:
            last_beat = int(elapsed)
            print(f"  t={elapsed:5.1f}s  state={tags['PLC_state']:<11} "
                  f"level={tags['LIT101_level']:.2f}m  pH={tags['AIT201_ph']:.2f}  "
                  f"inflow={tags['FIT101_inlet_flow']:.3f}  dose={tags['P201_dose_cmd']:.2f}")

        time.sleep(DT)

    print("\n[demo] done.")


if __name__ == "__main__":
    h = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    main(h)
