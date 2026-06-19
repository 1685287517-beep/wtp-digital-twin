"""Water Treatment Plant digital twin — application package.

Modules:
    config           shared configuration (env-driven)
    tags             the tag dictionary / namespace
    process          physical process model (tanks, pumps, valves, pH)
    plc              soft-PLC control logic (on/off, PID, state machine)
    faults           fault-injection manager (4 layers)
    bus              MQTT helpers
    sim_main         entrypoint: run process + PLC + publish telemetry
    historian        entrypoint: MQTT -> InfluxDB writer
    agent_detector   deterministic rule-based fault detection
    agent_assistant  Claude-backed operator assistant
    agent_main       entrypoint: detect faults, ask the assistant, publish advice
    inject_fault     CLI to inject/clear faults (the operator panel)
"""
