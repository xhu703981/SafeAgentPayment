# guard/simulate.py
"""
simulate a trade in a forked chain, and return the diff of balances and approvals
"""

from dataclasses import dataclass, field
from web3 import Web3


ERC20_ABI = [
    {"name": "balanceOf", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "o", "type": "address"}],
     "outputs": [{"type": "uint256"}]},
    {"name": "allowance", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "o", "type": "address"}, {"name": "s", "type": "address"}],
     "outputs": [{"type": "uint256"}]},
    {"name": "symbol", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "string"}]},
    {"anonymous": False, "name": "Approval", "type": "event",
     "inputs": [
         {"indexed": True, "name": "owner", "type": "address"},
         {"indexed": True, "name": "spender", "type": "address"},
         {"indexed": False, "name": "value", "type": "uint256"}]},
]


@dataclass
class Diff:
    success: bool                       # is successful
    eth_delta: dict = field(default_factory=dict)      # address -> wei change
    token_delta: dict = field(default_factory=dict)    # (token, address) -> change
    new_approvals: list = field(default_factory=list)  # {token, owner, spender, amount}
    error: str = ""


class Simulator:
    def __init__(self, rpc_url="http://127.0.0.1:8545"):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

    # snapshot/revert
    def _snapshot(self):
        return self.w3.provider.make_request("evm_snapshot", [])["result"]

    def _revert(self, snap_id):
        self.w3.provider.make_request("evm_revert", [snap_id])

    def simulate(self, signed_raw_tx, watch_addresses, watch_tokens):
        """
        signed_raw_tx : signed raw transaction bytes
        watch_addresses: addresses to watch
        watch_tokens   : tokens to watch
        """
        w3 = self.w3
        snap = self._snapshot()
        try:
            # --- 1.read the state before execution ---
            eth_before = {a: w3.eth.get_balance(a) for a in watch_addresses}
            bal_before, allow_before = self._read_tokens(watch_tokens, watch_addresses)

            # --- 2. send the transaction and wait for receipt ---
            try:
                tx_hash = w3.eth.send_raw_transaction(signed_raw_tx)
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
            except Exception as e:
                return Diff(success=False, error=str(e))

            if receipt.status != 1:
                return Diff(success=False, error="transaction reverted")

            # --- 3. read the state after execution ---
            eth_after = {a: w3.eth.get_balance(a) for a in watch_addresses}
            bal_after, allow_after = self._read_tokens(watch_tokens, watch_addresses)

            # --- 4. compute the diff ---
            diff = Diff(success=True)
            for a in watch_addresses:
                d = eth_after[a] - eth_before[a]
                if d != 0:
                    diff.eth_delta[a] = d
            for key in bal_after:
                d = bal_after[key] - bal_before[key]
                if d != 0:
                    diff.token_delta[key] = d
            for key, amt in allow_after.items():
                if amt != allow_before.get(key, 0):
                    token, owner, spender = key
                    diff.new_approvals.append(
                        {"token": token, "owner": owner,
                         "spender": spender, "amount": amt})
            return diff
        finally:
            # --- 5. revert the chain state ---
            self._revert(snap)

    def _read_tokens(self, tokens, addresses):
        """read the balances and approvals of tokens for the given addresses"""
        bal, allow = {}, {}
        for t in tokens:
            c = self.w3.eth.contract(address=t, abi=ERC20_ABI)
            for a in addresses:
                bal[(t, a)] = c.functions.balanceOf(a).call()
            for owner in addresses:
                for spender in addresses:
                    if owner != spender:
                        allow[(t, owner, spender)] = \
                            c.functions.allowance(owner, spender).call()
        return bal, allow