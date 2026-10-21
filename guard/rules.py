"""
rules.py — deterministic intent/result comparison.
Whitelist logic: any state change NOT explicitly allowed by the intent is blocked.
No model involved here. This is the layer that cannot be fooled.
"""
from dataclasses import dataclass


@dataclass
class Decision:
    verdict: str          # "ALLOW" or "BLOCK"
    reasons: list         # list of strings explaining a block

    @property
    def allowed(self):
        return self.verdict == "ALLOW"


def _norm(addr):
    return addr.lower() if isinstance(addr, str) else addr


def check(intent, diff):
    """
    intent: dict, e.g.
        {
          "allowed_spenders":   [router, ...],   # who may receive approvals
          "allowed_recipients": [user, router],  # who may receive funds
          "max_approval": 100 * 10**6,           # optional cap on approval amount
        }
    diff: a Diff from simulate()
    """
    reasons = []

    allowed_spenders   = {_norm(a) for a in intent.get("allowed_spenders", [])}
    allowed_recipients = {_norm(a) for a in intent.get("allowed_recipients", [])}
    max_approval       = intent.get("max_approval")

    # transaction itself failed -> block (nothing good happened)
    if not diff.success:
        return Decision("BLOCK", [f"transaction failed: {diff.error}"])

    # 1) every new approval must go to an allowed spender
    for ap in diff.new_approvals:
        spender = _norm(ap["spender"])
        if spender not in allowed_spenders:
            reasons.append(f"approval to non-allowed spender {ap['spender']}")
        elif max_approval is not None and ap["amount"] > max_approval:
            reasons.append(
                f"approval amount {ap['amount']} exceeds max {max_approval}")

    # 2) every outgoing token transfer must go to an allowed recipient
    #    token_delta: (token, addr) -> change. A positive delta on a non-user
    #    address means tokens moved TO it.
    for (token, addr), delta in diff.token_delta.items():
        if delta > 0 and _norm(addr) not in allowed_recipients:
            reasons.append(f"tokens moved to non-allowed recipient {addr}")

    # 3) outgoing ETH must go to an allowed recipient
    for addr, delta in diff.eth_delta.items():
        if delta > 0 and _norm(addr) not in allowed_recipients:
            reasons.append(f"ETH moved to non-allowed recipient {addr}")

    if reasons:
        return Decision("BLOCK", reasons)
    return Decision("ALLOW", [])
