"""
guard.py — single entry point. Chains the pieces:

    user instruction --> intent.py   --> frozen intent
    signed tx        --> simulate.py --> diff
    (intent, diff)   --> rules.py    --> ALLOW / BLOCK   (deterministic)
    if rules ALLOW and intent is ambiguous --> judge.py  --> may VETO

judge has veto power only: it can turn a rule-ALLOW into BLOCK, never the
reverse. So even if the judge model is fooled, the deterministic floor holds.
"""
from guard.intent import build_intent
from guard.simulate import Simulator
from guard.rules import check
from guard.judge import needs_judge, judge


class Guard:
    def __init__(self, rpc_url="http://127.0.0.1:8545",
                 watch_addresses=None, watch_tokens=None,
                 model="openai/gpt-4o-mini", use_judge=True):
        self.sim = Simulator(rpc_url)
        self.watch_addresses = watch_addresses or []
        self.watch_tokens = watch_tokens or []
        self.model = model
        self.use_judge = use_judge

    def check_instruction(self, instruction, signed_raw_tx, extra_watch=None):
        # 1) freeze intent from the user's words only
        intent = build_intent(instruction, self.model)

        # 2) simulate what the tx would actually do
        watch = list(self.watch_addresses)
        if extra_watch:
            watch += [a for a in extra_watch if a not in watch]
        diff = self.sim.simulate(signed_raw_tx, watch, self.watch_tokens)

        # 3) deterministic comparison
        decision = check(intent, diff)

        # 4) semantic veto — only when rules allowed AND intent is ambiguous
        decision.judged = False
        if self.use_judge and decision.allowed and needs_judge(intent):
            is_risk, conf, reason = judge(intent, diff)
            decision.judged = True
            decision.judge_conf = conf
            if is_risk:
                decision.verdict = "BLOCK"
                decision.reasons = [f"judge veto ({conf:.2f}): {reason}"]

        decision.intent = intent
        decision.diff = diff
        return decision
