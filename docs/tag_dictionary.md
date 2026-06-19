# Tag Dictionary

Generated from `app/tags.py`. Do not edit by hand.

| Tag | Description | Unit | Type |
|-----|-------------|------|------|
| `LIT101_level` | Treatment tank level | m | float |
| `AIT201_ph` | Tank pH | pH | float |
| `FIT101_inlet_flow` | Influent flow into tank | m3/s | float |
| `FIT102_outlet_flow` | Effluent flow out of tank | m3/s | float |
| `AIT202_influent_ph` | Influent (raw water) pH | pH | float |
| `P101_inlet_cmd` | Inlet pump run command | bool | bool |
| `P101_inlet_run_fb` | Inlet pump running feedback | bool | bool |
| `P102_outlet_cmd` | Outlet pump run command | bool | bool |
| `P102_outlet_run_fb` | Outlet pump running feedback | bool | bool |
| `P201_dose_cmd` | Dosing pump output (PID) | 0-1 | float |
| `PLC_state` | Plant state-machine state | enum | string |
| `LIT101_predicted` | Level predicted from mass balance | m | float |
| `PH_error` | pH setpoint - measurement | pH | float |
