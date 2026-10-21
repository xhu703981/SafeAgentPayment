"""
guard.py — the single entry point. Chains the three pieces:

    user instruction --> intent.py  --> frozen intent
    signed tx        --> simulate.py --> diff
    (intent, diff)   --> rules.py   --> ALLOW / BLOCK

This is what an agent calls before letting a transaction reach the chain.
"""
from guard.intent import build_intent
from guard.simulate import Simulator
from guard.rules import check


class Guard:
    def __init__(self, rpc_url="http://127.0.0.1:8545",
                 watch_addresses=None, watch_tokens=None,
                 model="deepseek/deepseek-chat"):
        self.sim = Simulator(rpc_url)
        self.watch_addresses = watch_addresses or []
        self.watch_tokens = watch_tokens or []
        self.model = model

    def check_instruction(self, instruction, signed_raw_tx, extra_watch=None):
        """
        instruction   : the user's original words (intent is built from this ONLY)
        signed_raw_tx : the transaction the agent wants to send
        returns       : Decision (.allowed, .verdict, .reasons) plus .intent/.diff attached
        """
        # 1) freeze intent from the user's words (no on-chain data here)
        intent = build_intent(instruction, self.model)

        # 2) simulate what the tx would actually do
        watch = list(self.watch_addresses)
        if extra_watch:
            watch += [a for a in extra_watch if a not in watch]
        diff = self.sim.simulate(signed_raw_tx, watch, self.watch_tokens)

        # 3) deterministic comparison
        decision = check(intent, diff)

        # attach for inspection / logging
        decision.intent = intent
        decision.diff = diff
        return decision
