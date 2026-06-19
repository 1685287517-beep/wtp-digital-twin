"""Deterministic fault detection — the fast, explainable first line.

The detector runs on every telemetry message and decides *whether* something is
wrong, using only sensor cross-checks and trends (never the injected fault flag,
which it cannot see). When it raises a fault the agent runner asks the LLM for a
plain-language recommendation. Keeping detection rule-based guarantees the
"<=60 s" demo requirement even if the LLM is slow or offline.

Each detector returns a fault key or None.
"""
import time
from collections import deque

# detection thresholds (documented in faults/catalog.md)
STALE_SECONDS   = 5.0     # no telemetry for this long -> infra fault
STUCK_WINDOW    = 12      # samples to judge "frozen" level
STUCK_EPS       = 1e-4    # measured level variation below this == frozen
STUCK_PRED_MOVE = 0.02    # predicted level must move at least this (m) to call it stuck
PH_BAND_ALARM   = 1.0     # |pH - setpoint| beyond this -> process fault
PH_SETPOINT     = 7.0
FLOW_EPS        = 1e-4    # flow below this == "no flow"
NOFLOW_SECONDS  = 3.0     # pump commanded+running but no flow for this long


class Detector:
    def __init__(self):
        self.level_hist = deque(maxlen=STUCK_WINDOW)
        self.pred_hist = deque(maxlen=STUCK_WINDOW)
        self.last_msg_ts = None         # wall-clock of last telemetry seen
        self._noflow_since = None
        self._ph_since = None

    def on_telemetry(self, tags: dict):
        self.last_msg_ts = time.time()
        self.level_hist.append(tags.get("LIT101_level"))
        self.pred_hist.append(tags.get("LIT101_predicted"))

    # --- individual checks, each returns (fault, detail) or None -----------
    def check_staleness(self):
        if self.last_msg_ts is None:
            return None
        age = time.time() - self.last_msg_ts
        if age > STALE_SECONDS:
            return ("INFRA_MQTT_STALE",
                    f"No telemetry for {age:.1f}s (> {STALE_SECONDS}s).")
        return None

    def check_level_stuck(self, tags):
        if len(self.level_hist) < self.level_hist.maxlen:
            return None
        meas_spread = max(self.level_hist) - min(self.level_hist)
        pred_spread = max(self.pred_hist) - min(self.pred_hist)
        # Analytical redundancy: the transmitter is stuck only if the *measured*
        # level is dead-flat while the mass-balance *prediction* keeps moving.
        # (If both are flat, water simply isn't moving -- not a stuck sensor.
        # This is what separates SENSOR_LEVEL_STUCK from EQUIP_PUMP_NO_FLOW.)
        if meas_spread < STUCK_EPS and pred_spread > STUCK_PRED_MOVE:
            return ("SENSOR_LEVEL_STUCK",
                    f"Level frozen at {tags['LIT101_level']:.3f} m while the "
                    f"mass-balance prediction moved {pred_spread:.3f} m.")
        return None

    def check_pump_no_flow(self, tags):
        running = tags.get("P101_inlet_cmd") and tags.get("P101_inlet_run_fb")
        no_flow = tags.get("FIT101_inlet_flow", 0.0) < FLOW_EPS
        now = time.time()
        if running and no_flow:
            self._noflow_since = self._noflow_since or now
            if now - self._noflow_since > NOFLOW_SECONDS:
                return ("EQUIP_PUMP_NO_FLOW",
                        "Inlet pump commanded ON and feedback RUNNING, but "
                        "inlet flow ~0 (command-vs-feedback divergence).")
        else:
            self._noflow_since = None
        return None

    def check_ph_excursion(self, tags):
        err = abs(tags.get("AIT201_ph", PH_SETPOINT) - PH_SETPOINT)
        now = time.time()
        if err > PH_BAND_ALARM:
            self._ph_since = self._ph_since or now
            if now - self._ph_since > 2.0:
                return ("PROCESS_PH_EXCURSION",
                        f"pH {tags['AIT201_ph']:.2f} deviates {err:.2f} from "
                        f"setpoint {PH_SETPOINT} beyond band {PH_BAND_ALARM}.")
        else:
            self._ph_since = None
        return None

    def evaluate(self, tags):
        """Return a list of (fault, detail) currently detected."""
        results = []
        for check in (
            self.check_staleness,
            lambda: self.check_level_stuck(tags),
            lambda: self.check_pump_no_flow(tags),
            lambda: self.check_ph_excursion(tags),
        ):
            r = check()
            if r:
                results.append(r)
        return results
