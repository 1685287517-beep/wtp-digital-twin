"""Physical process model — the 'twin' of the water-treatment tank.

State variables integrated with a simple explicit Euler step:
    level (m)   tank water level
    ph          tank pH

A first-order model is intentional: it is stable, easy to explain in the viva,
and good enough to make the control loops and faults behave realistically.
"""
from dataclasses import dataclass

NORMAL_INFLUENT_PH = 5.8     # raw water is mildly acidic -> needs dosing up


@dataclass
class Actuators:
    inlet_pump: bool = False     # P101
    outlet_pump: bool = False    # P102
    dose: float = 0.0            # P201, 0..1


class ProcessModel:
    def __init__(self):
        # --- true internal state (what the dashboard would never see directly)
        self.level = 2.0          # m
        self.ph = NORMAL_INFLUENT_PH
        # --- geometry / coefficients
        self.area = 2.0           # m^2 tank cross-section
        self.level_max = 5.0      # m
        self.inlet_flow = 0.020   # m^3/s when inlet pump on
        self.outlet_flow = 0.025  # m^3/s when outlet pump on
        self.dose_gain = 4.0      # pH units of authority at full dosing
        self.ph_tau = 8.0         # s, pH first-order time constant
        # --- fault hooks set from outside each scan
        self.inlet_blocked = False          # EQUIP fault: pump runs, no flow
        self.influent_ph = NORMAL_INFLUENT_PH  # PROCESS fault shifts this

    def step(self, dt: float, act: Actuators) -> dict:
        """Advance the physics by dt seconds and return the *raw* sensor values."""
        # --- flows --------------------------------------------------------
        qin = self.inlet_flow if (act.inlet_pump and not self.inlet_blocked) else 0.0
        qout = self.outlet_flow if act.outlet_pump else 0.0

        # --- level (mass balance on volume) -------------------------------
        self.level += (qin - qout) / self.area * dt
        self.level = max(0.0, min(self.level_max, self.level))

        # --- pH (first-order lag toward an equilibrium set by dosing) -----
        # equilibrium pH = influent pH lifted by the dosing output
        ph_eq = self.influent_ph + self.dose_gain * act.dose
        self.ph += (ph_eq - self.ph) / self.ph_tau * dt

        return {
            "LIT101_level": round(self.level, 4),
            "AIT201_ph": round(self.ph, 4),
            "FIT101_inlet_flow": round(qin, 5),
            "FIT102_outlet_flow": round(qout, 5),
            "AIT202_influent_ph": round(self.influent_ph, 4),
        }
