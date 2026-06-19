# Fault Catalog

One fault per Purdue/ISA-95 layer (assignment §5). Each is injected at runtime
from the operator panel (`app.inject_fault`) and detected by `app.agent_detector`
within the 60-second demo window.

| Layer | Fault key | What happens | Detection signal | Threshold |
|-------|-----------|--------------|------------------|-----------|
| Sensor | `SENSOR_LEVEL_STUCK` | LIT101 freezes at its last value | Published level is flat for N samples while a pump is moving water; cross-check vs `LIT101_predicted` (mass balance) | flat < 1e-4 m over 12 samples |
| Equipment | `EQUIP_PUMP_NO_FLOW` | Inlet pump P101 runs (feedback ON) but delivers no flow | Command + run-feedback ON while FIT101 ≈ 0 (command-vs-feedback / flow divergence) | flow < 1e-4 m³/s for > 3 s |
| Process | `PROCESS_PH_EXCURSION` | Influent turns strongly acidic; pH leaves the band | `|AIT201 − setpoint|` exceeds the alarm band; PID cannot recover fast enough | dev > 1.0 pH for > 2 s |
| Infrastructure | `INFRA_MQTT_STALE` | Simulator stops publishing (stand-in for broker death / network loss) | Telemetry staleness watchdog: no message for > window. Distinguished from a process alarm because *all* tags stop, not one signal | no telemetry > 5 s |

## Demo script

```bash
# inlet pump dead-heads
python -m app.inject_fault EQUIP_PUMP_NO_FLOW on
#   ... observe alarm + AI recommendation within 60 s, then clear:
python -m app.inject_fault EQUIP_PUMP_NO_FLOW off

# repeat for each fault key
python -m app.inject_fault SENSOR_LEVEL_STUCK on
python -m app.inject_fault PROCESS_PH_EXCURSION on
python -m app.inject_fault INFRA_MQTT_STALE on
```

## Why these detection methods (viva notes)

- **Sensor**: never trust a single transmitter. A second, independent estimate
  (the mass-balance prediction) exposes a stuck reading. This is *analytical
  redundancy*.
- **Equipment**: a running contactor does not prove the process effect. Comparing
  *command* to *measured effect* (flow) catches mechanical failures the motor
  feedback cannot.
- **Process**: setpoint-vs-measurement deviation with a debounce timer avoids
  false alarms on transient noise.
- **Infrastructure**: staleness is detected on *time*, not value. Because every
  tag goes quiet at once, we classify it as a data-path outage rather than a
  process alarm — operators must not chase a phantom process problem.
