"""Shared configuration. Everything is overridable through environment
variables so the same image works locally and inside docker-compose."""
import os

# ---- timing -----------------------------------------------------------------
SCAN_TIME = float(os.getenv("SCAN_TIME", "0.5"))        # PLC scan period (s)

# ---- MQTT -------------------------------------------------------------------
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Topic namespace:  plant / site / area / purpose
TOPIC_TELEMETRY  = "plant/wtp/area1/telemetry"      # all live tags, one JSON msg
TOPIC_CONTROL    = "plant/wtp/area1/control/fault"  # operator -> sim fault cmds
TOPIC_CONTROL_OP = "plant/wtp/area1/control/op"     # operator -> sim device cmds (HMI)
TOPIC_AGENT      = "plant/wtp/area1/agent"          # assistant -> operator advice

# ---- InfluxDB ---------------------------------------------------------------
INFLUX_URL    = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN  = os.getenv("INFLUX_TOKEN", "dev-token-please-change")
INFLUX_ORG    = os.getenv("INFLUX_ORG", "wtp")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "telemetry")

# ---- AI assistant -----------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AGENT_MODEL = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")

# ---- ThingsBoard Cloud (optional cloud platform) ---------------------------
TB_HOST   = os.getenv("TB_HOST", "mqtt.thingsboard.cloud")
TB_PORT   = int(os.getenv("TB_PORT", "1883"))
TB_TOKEN  = os.getenv("TB_TOKEN", "")            # device access token (empty = bridge idles)
TB_PERIOD = float(os.getenv("TB_PERIOD", "2.0")) # forward at most every N s (free-tier friendly)

# ---- process setpoints (also used by the PLC) -------------------------------
LEVEL_LOW_SP  = 1.0     # m  - start filling below this
LEVEL_HIGH_SP = 4.0     # m  - stop filling above this
PH_SETPOINT   = 7.0     # target pH during treatment
PH_BAND       = 0.5     # acceptable +/- band before alarm
