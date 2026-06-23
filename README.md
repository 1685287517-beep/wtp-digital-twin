# Water Treatment Plant — Digital Twin

Group assignment for **TUMA206 Modern Developments in Industry** (group 03). A
working digital twin of a clearwell / water-treatment tank, instrumented through
a full industrial stack — field → PLC → MQTT → historian → dashboards — with an
**agentic AI assistant** (Claude) that detects faults and recommends operator
actions in plain language, surfaced through **three alarm channels**: an animated
SCADA HMI, a ThingsBoard Cloud dashboard, and Telegram push notifications.


## Architecture

```
                          ┌──────────────┐  sensors  ┌──────────────┐
   operator (HMI/CLI) ───▶│ Digital twin │──────────▶│   Soft PLC   │
   fault injection        │ tank·pumps·  │◀──────────│ on/off · PID │
   device control         │ valves·pH    │  commands │ state machine│
                          └──────────────┘           └──────┬───────┘
                                                            │ publish tags (JSON)
                                                            ▼
                                            ┌───────────────────────────┐
                                            │   MQTT broker (Mosquitto)  │
                                            └───────────────┬───────────┘
        ┌───────────────┬───────────────────┬──────────────┼───────────────┐
        ▼               ▼                   ▼              ▼                ▼
 ┌────────────┐  ┌────────────┐     ┌──────────────┐ ┌───────────┐  ┌──────────────┐
 │ historian  │  │  AI agent  │     │  SCADA HMI   │ │ tb_bridge │  │  telegram    │
 │ →InfluxDB  │  │ detect →   │     │ (FastAPI +   │ │ → Things- │  │  notifier    │
 │            │  │ Claude     │     │ animated SVG)│ │ Board     │  │  (phone push)│
 └─────┬──────┘  └─────┬──────┘     │ + controls + │ │ Cloud ☁️  │  └──────────────┘
       ▼               │ advice     │ sound alarm  │ └───────────┘
   ┌─────────┐         │            └──────────────┘
   │ Grafana │◀────────┘ (agent_events)
   └─────────┘
```

Everything is decoupled through MQTT: adding a new consumer (cloud bridge,
Telegram, a second dashboard) needs **no change** to any existing service.

## Stack & justification (LO6)

| Layer | Choice | Why |
|-------|--------|-----|
| Process + PLC | Python (single deterministic scan loop) | Transparent control logic; easy to defend in the viva. |
| Messaging | **MQTT** (Eclipse Mosquitto) | Lightweight pub/sub; de-facto IIoT transport; decouples field from IT. |
| Historian | **InfluxDB 2.7** | Purpose-built time-series DB; native Grafana integration. |
| Dashboard | **Grafana** | Provisioned trends, KPI row, P&ID canvas, alarm table. |
| Operator HMI | **FastAPI + animated SVG** | Real SCADA mimic with AUTO/MAN device control + audible alarm. |
| AI assistant | **Claude** (`claude-sonnet-4-6`) | Live reasoning over the data snapshot; safe, explained advice; offline playbook fallback. |
| Cloud platform | **ThingsBoard Cloud** | Hosted IoT platform: cloud dashboard + rule-engine alarms. |
| Notifications | **Telegram bot** | Pushes alarms (with AI advice) to an operator's phone. |
| Orchestration | **docker-compose** | One command brings up the whole stack. |

## Repository layout

```
app/
  config.py          shared, env-driven configuration
  tags.py            the tag dictionary (single source of truth)
  process.py         physical model: level + pH dynamics
  plc.py             PID, on/off, state machine, scan cycle
  faults.py          fault-injection manager (4 layers)
  bus.py             MQTT helpers
  sim_main.py        ► twin + PLC + operator overrides, publish telemetry
  historian.py       ► MQTT -> InfluxDB
  agent_detector.py  deterministic rule-based fault detection
  agent_assistant.py Claude-backed recommendations (+ offline playbook)
  agent_main.py      ► detect, recommend (async), publish advice
  hmi.py             ► FastAPI HMI backend (state + control API)
  static/index.html  animated SCADA mimic (controls + sound alarm)
  tb_bridge.py       ► forward telemetry + AI alarms to ThingsBoard Cloud
  telegram_notify.py ► push alarms to Telegram
  inject_fault.py    operator CLI for fault injection
  demo_local.py      headless end-to-end demo (no broker/DB needed)
faults/catalog.md    the four chosen faults + detection methods
docs/                tag dictionary, deck, system explainer
grafana/             provisioned datasource + dashboard
docker-compose.yml   the whole stack
```

## Run it

### Everything in Docker (recommended)

```bash
cp .env.example .env     # add ANTHROPIC_API_KEY (live AI), TB_TOKEN (cloud), TG_* (Telegram)
docker compose up --build
```

- **SCADA HMI**: http://localhost:8090  ← the main operator screen
- **Grafana**: http://localhost:3000/d/wtp-live
- **InfluxDB**: http://localhost:8086  (admin / admin12345)

Inject faults from the HMI **ALARMS** tab, or the CLI:

```bash
docker compose exec agent python -m app.inject_fault PROCESS_PH_EXCURSION on
docker compose exec agent python -m app.inject_fault PROCESS_PH_EXCURSION off
```

### Quickest: headless demo (no broker, DB or Docker)

```bash
python -m app.demo_local        # runs twin+PLC+detection+AI, injects all 4 faults
```

## The four faults (LO4)

See [`faults/catalog.md`](faults/catalog.md). One per Purdue layer:
`SENSOR_LEVEL_STUCK`, `EQUIP_PUMP_NO_FLOW`, `PROCESS_PH_EXCURSION`,
`INFRA_MQTT_STALE` — each detected within 60 s and answered by the AI assistant.

## AI assistant design (LO5)

- **Detect first, deterministically.** `agent_detector.py` raises faults from
  sensor cross-checks and trends — fast, explainable, independent of the LLM, so
  the ≤60 s requirement holds even if the model is slow.
- **Then advise, with reasoning.** Claude receives the fault + a live tag
  snapshot and returns `{severity, diagnosis, actions, reasoning}` — grounding
  its advice in the actual current values (it will even flag inconsistent
  readings, e.g. a flow of 0 while the pump runs and level rises).
- **Non-blocking + resilient.** The LLM call runs in a background thread with a
  timeout; on any failure it falls back to a built-in playbook, so the demo
  always produces a recommendation.
- **Safety:** the agent **advises only**, never actuates; a human decides.

## Alarm channels

| Channel | What it shows |
|---------|---------------|
| **SCADA HMI** | Red LEDs + audible horn + ACK/Silence; AI advice list with timestamps. |
| **ThingsBoard Cloud** | Rule-engine alarm (`AI Detected Fault`) + telemetry incl. `fault_recommendation`. |
| **Telegram** | Phone push with the fault, Claude's diagnosis and recommended actions. |

## Cloud & notifications setup

- **ThingsBoard**: create a device, set `TB_TOKEN` in `.env`; `tb_bridge`
  forwards telemetry + AI faults. A device **Alarm rule** (`fault_active equal 1`)
  turns them into cloud alarms.
- **Telegram**: create a bot with @BotFather, set `TG_BOT_TOKEN` and `TG_CHAT_ID`.

## Team

| Name | Matriculation | Cohort | Area of ownership |
|------|---------------|--------|-------------------|
| _TODO_ | | | Process model + PLC |
| _TODO_ | | | MQTT + historian + Grafana |
| _TODO_ | | | AI agent + HMI |
| _TODO_ | | | Cloud (ThingsBoard) + Telegram |
| _TODO_ | | | Fault injection + docs + presentation |
