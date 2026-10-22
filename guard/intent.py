"""
intent.py — turn the user's instruction into a frozen intent schema.

SECURITY: the ONLY input is the user's original instruction. Never feed
on-chain data (token names, tool results) here. The intent is the anchor
of the whole defense; if it is poisoned at creation, everything downstream
is meaningless.

Design: the LLM produces only the SEMANTIC part (action, tokens, amount).
Addresses (allowed_spenders / allowed_recipients) are filled in by
deterministic code from a trusted config, never by the LLM. So even if the
LLM is misled, it cannot insert a malicious address.
"""
import os
import json
from openai import OpenAI

# --- trusted config: known-good addresses, NOT chosen by the LLM ---
USER_ADDRESS = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
# trusted routers per action (stand-in for now; real routers go here later)
TRUSTED_ROUTERS = ["0x1111111111111111111111111111111111111111"]

TOKENS = {  # symbol -> (address, decimals)
    "USDC": ("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6),
    "ETH":  ("native", 18),
}

_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
)

SYSTEM = """You convert a crypto wallet user's instruction into a strict JSON object.
Output ONLY JSON, no prose. Schema:
{
  "action": "swap" | "transfer" | "unknown",
  "sell": {"token": "<SYMBOL>", "max_amount": <number, human units>} | null,
  "buy":  {"token": "<SYMBOL>"} | null,
  "transfer": {"token": "<SYMBOL>", "amount": <number>, "to": "<recipient as the user named it>"} | null
}
Use null for fields that do not apply. Do not invent addresses. Amounts in human units (e.g. 100 for 100 USDC)."""


def _llm_semantic(instruction, model="openai/gpt-4o-mini"):
    resp = _client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": instruction}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def build_intent(instruction, model="openai/gpt-4o-mini"):
    """user instruction -> full frozen intent schema (semantic from LLM, addresses from config)."""
    sem = _llm_semantic(instruction, model)
    action = sem.get("action", "unknown")

    intent = {"action": action, "raw": sem,
              "allowed_spenders": [], "allowed_recipients": [USER_ADDRESS]}

    if action == "swap" and sem.get("sell"):
        token, dec = TOKENS[sem["sell"]["token"]]
        raw_amt = sem["sell"].get("max_amount")
        # empty amount stays empty -> becomes a blind spot for JEV to judge
        max_amount = int(raw_amt * 10**dec) if raw_amt is not None else None
        intent["sell"] = {"token": sem["sell"]["token"], "max_amount": max_amount}
        intent["buy"] = sem.get("buy")
        # a swap needs to approve the router -> allow trusted routers only
        intent["allowed_spenders"] = list(TRUSTED_ROUTERS)
        # funds come back to the user; router may hold them transiently
        intent["allowed_recipients"] = [USER_ADDRESS] + list(TRUSTED_ROUTERS)

    return intent
