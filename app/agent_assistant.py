"""The agentic AI operator assistant (LO5).

Given a detected fault and a snapshot of recent process data, it produces a
plain-language recommendation *with reasoning*. Design principles for the viva:

  * Advise, never actuate. The agent recommends; a human operator decides.
  * Always explain *why*, grounded in the data it was given.
  * Degrade gracefully: if no API key / no network, fall back to a built-in
    playbook so the live demo still works.

We use the Anthropic SDK with a tight system prompt and ask for strict JSON.
"""
import json

from app.config import ANTHROPIC_API_KEY, AGENT_MODEL

SYSTEM_PROMPT = """You are an operator assistant for a water-treatment plant SCADA system.
You receive a detected fault and a snapshot of recent tag values.
Your job: briefly diagnose, then recommend the safe operator actions.

Rules:
- You ADVISE ONLY. Never claim to have changed any setpoint or actuator.
- Ground every statement in the data provided. If unsure, say so.
- Prefer safe, reversible actions; escalate to a human for anything risky.
- Be concise: an operator reads this under stress.

Respond as strict JSON:
{"severity": "info|warning|critical",
 "diagnosis": "one or two sentences",
 "actions": ["step 1", "step 2", ...],
 "reasoning": "why, referencing the tags"}"""

# Built-in fallback playbook (used when the LLM is unavailable).
PLAYBOOK = {
    "SENSOR_LEVEL_STUCK": {
        "severity": "warning",
        "diagnosis": "Level transmitter LIT101 appears frozen.",
        "actions": ["Cross-check with mass-balance prediction LIT101_predicted",
                    "Switch level control to the predicted value",
                    "Dispatch instrumentation tech to inspect LIT101"],
        "reasoning": "Reading is flat while pumps move water; trust the model, not the sensor.",
    },
    "EQUIP_PUMP_NO_FLOW": {
        "severity": "critical",
        "diagnosis": "Inlet pump P101 runs but delivers no flow (likely loss of prime / closed suction).",
        "actions": ["Stop P101 to avoid dry-run damage",
                    "Check suction valve and prime",
                    "Verify FIT101 flow transmitter"],
        "reasoning": "P101_inlet_cmd and run feedback are ON but FIT101 ~0.",
    },
    "PROCESS_PH_EXCURSION": {
        "severity": "critical",
        "diagnosis": "Tank pH has excursed outside the control band.",
        "actions": ["Hold discharge (do not release off-spec water)",
                    "Verify dosing pump P201 and reagent supply",
                    "Increase treatment time before discharge"],
        "reasoning": "AIT201 deviates from setpoint beyond the alarm band.",
    },
    "INFRA_MQTT_STALE": {
        "severity": "warning",
        "diagnosis": "Telemetry has gone stale — a data-path outage, not necessarily a process alarm.",
        "actions": ["Treat last values as UNRELIABLE",
                    "Check MQTT broker and network link",
                    "Do not trust dashboard trends until data resumes"],
        "reasoning": "No telemetry received within the staleness window.",
    },
}


def recommend(fault: str, detail: str, snapshot: dict) -> dict:
    """Return a recommendation dict; fall back to the playbook on any failure."""
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            # short timeout + no long retry storm: a hung/throttled call fails
            # fast and falls back to the playbook instead of freezing the agent
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=20.0, max_retries=1)
            user = (f"Detected fault: {fault}\nDetector detail: {detail}\n"
                    f"Recent tag snapshot:\n{json.dumps(snapshot, indent=2)}")
            msg = client.messages.create(
                model=AGENT_MODEL,
                max_tokens=600,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user}],
            )
            text = msg.content[0].text.strip()
            # be tolerant of markdown fences
            if text.startswith("```"):
                text = text.strip("`").split("\n", 1)[1]
            return json.loads(text)
        except Exception as exc:  # noqa: BLE001 - demo must keep running
            print(f"[assistant] LLM unavailable ({exc}); using playbook", flush=True)

    return PLAYBOOK.get(fault, {
        "severity": "warning",
        "diagnosis": f"Unrecognised fault {fault}.",
        "actions": ["Notify a senior operator"],
        "reasoning": detail,
    })
