"""The tag dictionary (a.k.a. tag namespace / point list).

In a real plant every measurable or commandable value is a *tag* with a stable
name, an engineering unit and a data type. The historian, dashboard and AI
agent all refer to these names. Keep this file as the single source of truth –
the README's tag dictionary is generated from it.

Naming convention (ISA-style):  <loop-letter><number>_<meaning>
    LIT101  Level Indicating Transmitter, loop 101
    AIT201  Analytical Indicating Transmitter (pH), loop 201
    P101    Pump 101,  XV101 = on/off valve
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Tag:
    name: str
    desc: str
    unit: str
    dtype: str   # "float" | "bool" | "int" | "string"


TAGS = [
    # ---- field measurements (sensors) -------------------------------------
    Tag("LIT101_level",       "Treatment tank level",            "m",      "float"),
    Tag("AIT201_ph",          "Tank pH",                         "pH",     "float"),
    Tag("FIT101_inlet_flow",  "Influent flow into tank",         "m3/s",   "float"),
    Tag("FIT102_outlet_flow", "Effluent flow out of tank",       "m3/s",   "float"),
    Tag("AIT202_influent_ph", "Influent (raw water) pH",         "pH",     "float"),
    # ---- actuator commands & feedback (equipment) -------------------------
    Tag("P101_inlet_cmd",     "Inlet pump run command",          "bool",   "bool"),
    Tag("P101_inlet_run_fb",  "Inlet pump running feedback",     "bool",   "bool"),
    Tag("P102_outlet_cmd",    "Outlet pump run command",         "bool",   "bool"),
    Tag("P102_outlet_run_fb", "Outlet pump running feedback",    "bool",   "bool"),
    Tag("P201_dose_cmd",      "Dosing pump output (PID)",        "0-1",    "float"),
    # ---- controller / derived (process) -----------------------------------
    Tag("PLC_state",          "Plant state-machine state",       "enum",   "string"),
    Tag("LIT101_predicted",   "Level predicted from mass balance","m",     "float"),
    Tag("PH_error",           "pH setpoint - measurement",       "pH",     "float"),
]

TAG_INDEX = {t.name: t for t in TAGS}
