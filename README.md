# Water Treatment Plant — Digital Twin

Group assignment for **TUMA206 Modern Developments in Industry**. A working
digital twin of a water-treatment tank, instrumented through a full industrial
stack — field → PLC → MQTT → historian → dashboard — with an agentic AI
assistant that detects faults and recommends operator actions in plain language.

> ⚠️ **Viva note (AI use policy §8):** every team member must be able to explain
> any line of this code. This README and the inline comments are written to help
> you *understand*, not to substitute for understanding. Read the code.

## Architecture

```
 ┌─────────────┐   sensors   ┌──────────┐  commands
 │ ProcessModel│────────────▶│   PLC    │───────────┐
 │ (the twin)  │◀────────────│ on/off + │           │
 │ tank·pumps· │  actuators  │ PID +    │           │
 │ valve·pH    │             │ state m. │           │
 └─────────────┘             └──────────┘           │
        ▲ fault hooks              │ tag map         │
        │                          ▼                 │
        │                  ┌───────────────┐         │
   inject_fault ──────────▶│  sim_main     │  publish JSON
   (operator panel)        │  loop         │────────────────┐
                           └───────────────┘                ▼
                                                     ┌───────────────┐
                                                     │   MQTT broker │  plant/wtp/area1/telemetry
                                                     │  (Mosquitto)  │
                                                     └───────────────┘
                                              ┌───────────┴───────────┐
                                              ▼                       ▼
                                      ┌───────────────┐       ┌───────────────┐
                                      │  historian    │       │  agent_main   │
                                      │ MQTT→InfluxDB │       │ detect→Claude │
                                      └───────┬───────┘       └───────┬───────┘
                                              ▼                       │ publish advice
                                      ┌───────────────┐               │
                                      │   InfluxDB    │◀──────────────┘
                                      └───────┬───────┘   (agent_events)
                                              ▼
                                      ┌───────────────┐
                                      │   Grafana     │  live trends + alarms
                                      └───────────────┘
```

## Stack & justification (LO6)

| Layer | Choice | Why |
|-------|--------|-----|
| Process + PLC | Python (single deterministic scan loop) | Transparent, easy to reason about and defend in the viva; PID/state-machine logic is plain code. |
| Messaging | **MQTT** (Eclipse Mosquitto) | Lightweight pub/sub, the de-facto IIoT transport; decouples field from upstream services. |
| Historian | **InfluxDB 2.7** | Purpose-built time-series DB; native Grafana integration; retention/downsampling out of the box. |
| Dashboard | **Grafana** | No frontend code; provisioned trends + alarm thresholds. |
| AI assistant | **Claude** (`claude-sonnet-4-6`), via Anthropic SDK | Strong agentic reasoning; produces safe, *explained* recommendations. Falls back to a built-in playbook offline so the demo never fails. |
| Orchestration | **docker-compose** | One command brings up the entire stack = reproducible demo. |

Trade-offs we accept: a first-order physics model (not CFD) — enough to make
control and faults realistic; MQTT over OPC-UA — simpler, though OPC-UA carries
richer typed metadata; InfluxDB over a plain SQL store — better fit for tags.

## Repository layout

```
app/
  config.py          shared, env-driven configuration
  tags.py            the tag dictionary (single source of truth)
  process.py         physical model: level + pH dynamics
  plc.py             PID, on/off, state machine, scan cycle
  faults.py          fault-injection manager (4 layers)
  bus.py             MQTT helpers
  sim_main.py        ► run twin + PLC, publish telemetry
  historian.py       ► MQTT -> InfluxDB
  agent_detector.py  deterministic rule-based detection
  agent_assistant.py Claude-backed recommendations (+ offline playbook)
  agent_main.py      ► detect, recommend, publish advice
  inject_fault.py    operator panel CLI
faults/catalog.md    the four chosen faults + detection methods
docs/                tag dictionary (+ generator)
grafana/             provisioned datasource + dashboard
docker-compose.yml   the whole stack
```

## Run it

### Quickest: headless end-to-end (no broker, DB or Docker)

Proves the whole pipeline — twin → PLC → detection → AI advice — in one process,
injecting all four faults in sequence. Great first run, and a fallback if Docker
misbehaves on demo day. Needs no pip installs beyond the standard library.

```bash
python -m app.demo_local        # ~8 s per fault
python -m app.demo_local 5      # hold each fault 5 s
```

### Everything in Docker (recommended for the demo)

```bash
cp .env.example .env          # optional: add ANTHROPIC_API_KEY for the real LLM
docker compose up --build
```

- Grafana: http://localhost:3000  (anonymous admin; dashboard "Water Treatment Plant — Live")
- InfluxDB: http://localhost:8086  (admin / admin12345)

Watch the AI assistant's output:

```bash
docker compose logs -f agent
```

Inject faults from another terminal:

```bash
docker compose run --rm agent python -m app.inject_fault EQUIP_PUMP_NO_FLOW on
docker compose run --rm agent python -m app.inject_fault EQUIP_PUMP_NO_FLOW off
```

### Locally without Docker (for development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# you need an MQTT broker + InfluxDB running; then in separate shells:
python -m app.sim_main
python -m app.historian
python -m app.agent_main
python -m app.inject_fault list
```

## The four faults

See [`faults/catalog.md`](faults/catalog.md). Summary: `SENSOR_LEVEL_STUCK`,
`EQUIP_PUMP_NO_FLOW`, `PROCESS_PH_EXCURSION`, `INFRA_MQTT_STALE` — each detected
within the 60 s window and answered by the AI assistant.

## Tag dictionary

See [`docs/tag_dictionary.md`](docs/tag_dictionary.md) (regenerate with
`python docs/gen_tag_dictionary.py`).

## AI assistant design (LO5)

- **Detect first, deterministically.** `agent_detector.py` raises faults from
  sensor cross-checks and trends — fast and explainable, independent of the LLM.
- **Then advise, with reasoning.** On a *new* fault the assistant gets the fault
  and a recent tag snapshot and returns `{severity, diagnosis, actions,
  reasoning}` as JSON.
- **Safety:** the agent **advises only**, never actuates; a human operator
  decides. It must ground claims in the data it was shown.
- **Graceful degradation:** no API key / no network → built-in playbook, so the
  live demo always produces a recommendation.

## Team

| Name | Matriculation | Cohort | Area of ownership |
|------|---------------|--------|-------------------|
| _TODO_ | | | Process model + PLC |
| _TODO_ | | | MQTT + historian + Grafana |
| _TODO_ | | | AI agent |
| _TODO_ | | | Fault injection + integration |
| _TODO_ | | | Docs + presentation |
