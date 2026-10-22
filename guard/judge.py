"""
judge.py — semantic fallback for the BLIND SPOTS of the deterministic rules.

Principle: any field left empty in the intent schema is a dimension the rules
cannot judge. Those empty fields are handed to JEV (TypeSafe's decision model),
which estimates whether the transaction is a risk. VETO power only: may turn a
rule-ALLOW into BLOCK, never the reverse. Fed structured fields only.

Backend: JEV via OpenRouter's /api/alpha/decisions endpoint. JEV is a decision
model (returns calibrated label probabilities), not a chat model.
"""
import os
import json
import requests

JEV_MODEL = "typesafe/jev-1.14"
JEV_URL = "https://openrouter.ai/api/alpha/decisions"
RISK_THRESHOLD = 0.5   # noul >= this -> treat as risk -> block

# which intent fields, when empty, are blind spots the judge should cover
_CHECKED_FIELDS = {
    "sell.max_amount": lambda i: (i.get("sell") or {}).get("max_amount"),
    "buy.token":       lambda i: (i.get("buy") or {}).get("token"),
    "max_approval":    lambda i: i.get("max_approval"),
}


def blind_spots(intent):
    spots = []
    for name, getter in _CHECKED_FIELDS.items():
        if getter(intent) in (None, "", []):
            spots.append(name)
    return spots


def needs_judge(intent):
    """Judge runs iff the intent has at least one blind spot."""
    return len(blind_spots(intent)) > 0


def _state(intent, diff):
    """Build a clean, structured description for JEV. No raw on-chain strings."""
    effects = {
        "eth_delta": {a: int(v) for a, v in diff.eth_delta.items()},
        "token_delta": {f"{t}:{a}": int(v) for (t, a), v in diff.token_delta.items()},
        "new_approvals": [{"spender": ap["spender"], "amount": int(ap["amount"])}
                          for ap in diff.new_approvals],
    }
    intent_view = {k: intent.get(k) for k in ("action", "sell", "buy", "max_approval")}
    return (
        "User intent (fields left empty mean 'unspecified by user'): "
        + json.dumps(intent_view)
        + "\nIntent fields the user did NOT specify: " + json.dumps(blind_spots(intent))
        + "\nSimulated transaction effects: " + json.dumps(effects)
    )


def judge(intent, diff, model=JEV_MODEL):
    """Ask JEV whether the tx is a risk. Returns (is_risk, confidence, reason)."""
    payload = {
        "model": model,
        "state": _state(intent, diff),
        "questions": {
            "is_risk": {
                "type": "noul",
                "instructions": (
                    "A wallet is about to execute this transaction for the user. "
                    "Judge it the way a careful human would: look at whether the "
                    "transaction grants any power over the user's assets (e.g. an "
                    "approval that lets another address move the user's tokens, or a "
                    "transfer out). If it grants such power, ask: did the user's "
                    "instruction clearly require this? Granting someone the ability to "
                    "move your funds when the user never asked for it is dangerous by "
                    "default. It is only acceptable when it is an obviously necessary "
                    "step of what the user explicitly asked to do (for example, a swap "
                    "genuinely requires approving the swap contract). Is this transaction "
                    "a RISK?"
                ),
                "criteria": {
                    "true": "It grants power over the user's funds (an approval or outgoing transfer) that the user did not ask for and that is not an obviously necessary step of their stated task; or the amount/recipient goes beyond what the task needs.",
                    "false": "Any power granted is an obviously necessary, proportional step of exactly what the user asked to do.",
                },
            }
        },
    }
    r = requests.post(
        JEV_URL,
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                 "Content-Type": "application/json"},
        data=json.dumps(payload), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f'JEV {r.status_code}: {r.text}\nSTATE WAS:\n' + payload['state'])
    noul = r.json()["answers"]["is_risk"]["noul"]   # P(risk)
    is_risk = noul >= RISK_THRESHOLD
    return is_risk, noul, f"JEV risk probability {noul:.2f}"
