"""Soft-PLC control logic.

This single module demonstrates the three control styles required by LO2:
    * on/off control  -> inlet pump filling with hysteresis
    * PID control      -> dosing pump regulating pH to setpoint
    * state machine    -> plant phases  FILLING -> TREATING -> DISCHARGING

A real PLC runs a deterministic *scan cycle*: read inputs, execute logic,
write outputs, repeat at a fixed period. `scan()` is one such cycle.
"""
from app.config import LEVEL_LOW_SP, LEVEL_HIGH_SP, PH_SETPOINT, PH_BAND
from app.process import Actuators


class PID:
    """Textbook PID with output clamping and anti-windup."""
    def __init__(self, kp, ki, kd, out_min=0.0, out_max=1.0):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.out_min, self.out_max = out_min, out_max
        self._i = 0.0
        self._prev_err = None

    def step(self, error, dt):
        p = self.kp * error
        self._i += self.ki * error * dt
        # anti-windup: clamp the integrator to the output range
        self._i = max(self.out_min, min(self.out_max, self._i))
        d = 0.0 if self._prev_err is None else self.kd * (error - self._prev_err) / dt
        self._prev_err = error
        out = p + self._i + d
        return max(self.out_min, min(self.out_max, out))


class PLC:
    """Holds controller state across scans."""
    def __init__(self):
        self.state = "FILLING"
        self.dose_pid = PID(kp=0.4, ki=0.15, kd=0.0)
        self.treat_timer = 0.0
        self.treat_seconds = 15.0
        self.act = Actuators()

    def scan(self, sensors: dict, dt: float):
        level = sensors["LIT101_level"]
        ph = sensors["AIT201_ph"]

        # ----- state machine ------------------------------------------------
        if self.state == "FILLING":
            self.act.inlet_pump = True
            self.act.outlet_pump = False
            if level >= LEVEL_HIGH_SP:
                self.state = "TREATING"
                self.treat_timer = 0.0
        elif self.state == "TREATING":
            self.act.inlet_pump = False
            self.act.outlet_pump = False
            self.treat_timer += dt
            in_band = abs(ph - PH_SETPOINT) <= PH_BAND
            if in_band and self.treat_timer >= self.treat_seconds:
                self.state = "DISCHARGING"
        elif self.state == "DISCHARGING":
            self.act.inlet_pump = False
            self.act.outlet_pump = True
            if level <= LEVEL_LOW_SP:
                self.state = "FILLING"

        # ----- PID dosing (always active so pH stays controlled) -----------
        ph_error = PH_SETPOINT - ph
        self.act.dose = self.dose_pid.step(ph_error, dt)

        # ----- derived tags for detection / display ------------------------
        # numeric state code so dashboards can show the state in panels that
        # only reduce numbers (e.g. a Grafana stat); the string stays too.
        state_code = {"FILLING": 0, "TREATING": 1, "DISCHARGING": 2}[self.state]
        derived = {
            "PLC_state": self.state,
            "PLC_state_code": state_code,
            "PH_error": round(ph_error, 4),
        }
        return self.act, derived
