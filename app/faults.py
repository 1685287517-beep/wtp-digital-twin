"""Fault-injection manager — one fault per Purdue layer (assignment §5).

    SENSOR_LEVEL_STUCK   sensor      level transmitter freezes at last value
    EQUIP_PUMP_NO_FLOW   equipment   inlet pump 'runs' (feedback on) but no flow
    PROCESS_PH_EXCURSION process     influent turns strongly acidic -> pH excursion
    INFRA_MQTT_STALE     infra       sim stops publishing -> data goes stale

Faults are toggled at runtime by publishing to the control topic, e.g.
    {"fault": "EQUIP_PUMP_NO_FLOW", "active": true}
The `inject_fault.py` CLI is the operator panel that sends these.
"""
KNOWN_FAULTS = {
    "SENSOR_LEVEL_STUCK",
    "EQUIP_PUMP_NO_FLOW",
    "PROCESS_PH_EXCURSION",
    "INFRA_MQTT_STALE",
}


class FaultManager:
    def __init__(self):
        self.state = {f: False for f in KNOWN_FAULTS}
        self._stuck_level = None   # remembered value while level sensor is stuck

    def active(self, fault: str) -> bool:
        return self.state.get(fault, False)

    def set(self, fault: str, active: bool):
        if fault in KNOWN_FAULTS:
            self.state[fault] = active
            if fault == "SENSOR_LEVEL_STUCK" and not active:
                self._stuck_level = None
            return True
        return False

    def any_active(self) -> bool:
        return any(self.state.values())

    # --- helpers used by the sim loop --------------------------------------
    def apply_sensor_layer(self, tags: dict) -> dict:
        """Corrupt the *published* sensor values (the field never lies, the
        wire does). Currently only the level transmitter can stick."""
        if self.active("SENSOR_LEVEL_STUCK"):
            if self._stuck_level is None:
                self._stuck_level = tags["LIT101_level"]
            tags["LIT101_level"] = self._stuck_level
        return tags
